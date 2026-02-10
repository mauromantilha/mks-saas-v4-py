from datetime import date, timedelta

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.forms.models import model_to_dict
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ledger.services import append_ledger_entry
from operational.address import lookup_cep
from operational.ai import (
    apply_cnpj_profile_to_customer,
    apply_cnpj_profile_to_lead,
    generate_commercial_insights,
    lookup_cnpj_profile,
    sanitize_cnpj,
)
from operational.models import (
    Apolice,
    CommercialActivity,
    Customer,
    Endosso,
    Installment,
    Lead,
    Opportunity,
    PolicyRequest,
    ProposalOption,
    SalesGoal,
)
from commission.models import (
    CommissionAccrual,
    CommissionPayoutBatch,
    CommissionPlanScope,
    InsurerSettlementBatch,
)
from operational.serializers import (
    AIInsightRequestSerializer,
    ApoliceSerializer,
    CNPJEnrichmentRequestSerializer,
    CommercialActivitySerializer,
    CommissionAccrualSerializer,
    CommissionPayoutBatchCreateSerializer,
    CommissionPayoutBatchSerializer,
    CommissionPlanScopeSerializer,
    CustomerSerializer,
    EndossoSerializer,
    InsurerSettlementBatchCreateSerializer,
    InsurerSettlementBatchSerializer,
    LeadConvertSerializer,
    LeadHistorySerializer,
    LeadSerializer,
    PolicyRequestSerializer,
    OpportunityHistorySerializer,
    OpportunityStageUpdateSerializer,
    OpportunitySerializer,
    ProposalOptionSerializer,
    SalesGoalSerializer,
    SalesMetricsSerializer,
)
from operational.services import (
    approve_commission_payout_batch,
    approve_insurer_settlement_batch,
    create_commission_payout_batch,
    create_insurer_settlement_batch,
)
from tenancy.permissions import IsTenantRoleAllowed


class TenantScopedAPIViewMixin:
    permission_classes = [IsTenantRoleAllowed]
    model = None
    ordering = ()

    def dispatch(self, request, *args, **kwargs):
        """Validate tenant context is present before processing request."""
        if not hasattr(request, 'company') or request.company is None:
            return Response(
                {"detail": "Tenant context not found or invalid"},
                status=403
            )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        """Filter queryset by current tenant company (SECURITY: prevent cross-tenant data access)."""
        company = getattr(self.request, "company", None)
        if company is None:
            # Return empty queryset if tenant context is missing
            return self.model.objects.none()
        
        queryset = self.model.objects.filter(company=company)
        if self.ordering:
            return queryset.order_by(*self.ordering)
        return queryset

    def _ledger_resource_label(self) -> str:
        model = getattr(self, "model", None)
        if model is None:
            return self.__class__.__name__
        return model._meta.label

    def _append_ledger(self, action: str, instance, *, before=None, after=None, metadata=None):
        metadata_payload = {}
        if isinstance(metadata, dict):
            metadata_payload.update(metadata)
        resource_key = getattr(self, "tenant_resource_key", "")
        if resource_key:
            metadata_payload.setdefault("tenant_resource_key", resource_key)

        append_ledger_entry(
            scope="TENANT",
            company=getattr(self.request, "company", None),
            actor=getattr(self.request, "user", None),
            action=action,
            resource_label=self._ledger_resource_label(),
            resource_pk=str(getattr(instance, "pk", "")),
            request=self.request,
            data_before=before,
            data_after=after,
            metadata=metadata_payload,
        )

    def perform_create(self, serializer):
        instance = serializer.save(company=self.request.company)
        self._append_ledger(
            "CREATE",
            instance,
            after=_instance_payload(instance),
        )
        return instance

    def perform_update(self, serializer):
        instance = self.get_object()
        before = _instance_payload(instance)
        updated = serializer.save()
        self._append_ledger(
            "UPDATE",
            updated,
            before=before,
            after=_instance_payload(updated),
        )
        return updated

    def perform_destroy(self, instance):
        before = _instance_payload(instance)
        self._append_ledger("DELETE", instance, before=before)
        instance.delete()


def _score_label_from_qualification_score(score: int | None) -> str:
    if score is None:
        return ""
    if score < 40:
        return Lead.SCORE_COLD
    if score < 70:
        return Lead.SCORE_WARM
    return Lead.SCORE_HOT


def _append_ai_insights(instance, insights: dict, *, extra_update_fields: list[str] | None = None):
    current_ai = instance.ai_insights if isinstance(instance.ai_insights, dict) else {}
    history = list(current_ai.get("history", []))
    history.append(insights)
    history = history[-5:]
    instance.ai_insights = {**current_ai, "latest": insights, "history": history}

    update_fields = ["ai_insights", "updated_at"]
    if extra_update_fields:
        update_fields.extend(extra_update_fields)
    instance.save(update_fields=tuple(sorted(set(update_fields))))


def _auto_populate_lead_intelligence(lead: Lead):
    """Auto-enrich CNPJ and compute AI scoring for a newly created lead.

    This keeps lead ingestion low-effort, while remaining safe: if the external CNPJ
    endpoint is not configured, enrichment is skipped.
    """

    cnpj_profile = None
    cnpj = sanitize_cnpj(getattr(lead, "cnpj", ""))
    if cnpj:
        profile = lookup_cnpj_profile(cnpj)
        if profile.get("success"):
            cnpj_profile = profile
            apply_cnpj_profile_to_lead(lead, profile)
            lead.refresh_from_db()

    insights = generate_commercial_insights(
        entity_type="LEAD",
        payload=_instance_payload(lead),
        focus="auto",
        cnpj_profile=cnpj_profile,
    )

    extra_fields = []
    qualification_score = insights.get("qualification_score")
    if qualification_score is not None:
        lead.qualification_score = int(qualification_score)
        extra_fields.append("qualification_score")
        lead.lead_score_label = _score_label_from_qualification_score(lead.qualification_score)
        extra_fields.append("lead_score_label")

    _append_ai_insights(lead, insights, extra_update_fields=extra_fields)


def _auto_populate_customer_intelligence(customer: Customer):
    cnpj_profile = None
    cnpj = sanitize_cnpj(getattr(customer, "cnpj", "")) or sanitize_cnpj(
        getattr(customer, "document", "")
    )
    if cnpj:
        profile = lookup_cnpj_profile(cnpj)
        if profile.get("success"):
            cnpj_profile = profile
            apply_cnpj_profile_to_customer(customer, profile)
            customer.refresh_from_db()

    insights = generate_commercial_insights(
        entity_type="CUSTOMER",
        payload=_instance_payload(customer),
        focus="auto",
        cnpj_profile=cnpj_profile,
    )
    _append_ai_insights(customer, insights)


class CustomerListCreateAPIView(TenantScopedAPIViewMixin, generics.ListCreateAPIView):
    """
    Isolamento por tenant via manager padrão.
    RBAC por método HTTP via IsTenantRoleAllowed.
    """

    model = Customer
    serializer_class = CustomerSerializer
    ordering = ("name",)
    tenant_resource_key = "customers"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("contacts")

    def perform_create(self, serializer):
        customer = super().perform_create(serializer)
        _auto_populate_customer_intelligence(customer)


class CustomerDetailAPIView(TenantScopedAPIViewMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Customer
    serializer_class = CustomerSerializer
    tenant_resource_key = "customers"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("contacts")


class CepLookupAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "customers"

    def get(self, request, cep: str):
        result = lookup_cep(cep)
        if not result.get("success"):
            detail = result.get("error") or "CEP lookup failed."
            if detail == "Invalid CEP.":
                status_code = status.HTTP_400_BAD_REQUEST
            elif detail == "CEP not found.":
                status_code = status.HTTP_404_NOT_FOUND
            else:
                status_code = status.HTTP_424_FAILED_DEPENDENCY
            return Response({"detail": detail, "cep_lookup": result}, status=status_code)

        return Response(
            {
                "zip_code": result.get("zip_code", ""),
                "street": result.get("street", ""),
                "neighborhood": result.get("neighborhood", ""),
                "city": result.get("city", ""),
                "state": result.get("state", ""),
                "provider": result.get("provider", "cep_lookup"),
            }
        )


class LeadListCreateAPIView(TenantScopedAPIViewMixin, generics.ListCreateAPIView):
    model = Lead
    serializer_class = LeadSerializer
    ordering = ("-created_at",)
    tenant_resource_key = "leads"

    def perform_create(self, serializer):
        lead = super().perform_create(serializer)
        _auto_populate_lead_intelligence(lead)


class LeadDetailAPIView(TenantScopedAPIViewMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Lead
    serializer_class = LeadSerializer
    tenant_resource_key = "leads"


class OpportunityListCreateAPIView(TenantScopedAPIViewMixin, generics.ListCreateAPIView):
    model = Opportunity
    serializer_class = OpportunitySerializer
    ordering = ("-created_at",)
    tenant_resource_key = "opportunities"


class OpportunityDetailAPIView(
    TenantScopedAPIViewMixin, generics.RetrieveUpdateDestroyAPIView
):
    model = Opportunity
    serializer_class = OpportunitySerializer
    tenant_resource_key = "opportunities"


class ProposalOptionListCreateAPIView(TenantScopedAPIViewMixin, generics.ListCreateAPIView):
    model = ProposalOption
    serializer_class = ProposalOptionSerializer
    ordering = ("-is_recommended", "-ranking_score", "annual_premium", "-created_at")
    tenant_resource_key = "proposal_options"


class ProposalOptionDetailAPIView(
    TenantScopedAPIViewMixin, generics.RetrieveUpdateDestroyAPIView
):
    model = ProposalOption
    serializer_class = ProposalOptionSerializer
    tenant_resource_key = "proposal_options"


class PolicyRequestListCreateAPIView(TenantScopedAPIViewMixin, generics.ListCreateAPIView):
    model = PolicyRequest
    serializer_class = PolicyRequestSerializer
    ordering = ("status", "issue_deadline_at", "-created_at")
    tenant_resource_key = "policy_requests"


class PolicyRequestDetailAPIView(
    TenantScopedAPIViewMixin, generics.RetrieveUpdateDestroyAPIView
):
    model = PolicyRequest
    serializer_class = PolicyRequestSerializer
    tenant_resource_key = "policy_requests"


class ApoliceListCreateAPIView(TenantScopedAPIViewMixin, generics.ListCreateAPIView):
    model = Apolice
    serializer_class = ApoliceSerializer
    ordering = ("-created_at",)
    tenant_resource_key = "apolices"


class ApoliceDetailAPIView(TenantScopedAPIViewMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Apolice
    serializer_class = ApoliceSerializer
    tenant_resource_key = "apolices"


class EndossoListCreateAPIView(TenantScopedAPIViewMixin, generics.ListCreateAPIView):
    model = Endosso
    serializer_class = EndossoSerializer
    ordering = ("-created_at",)
    tenant_resource_key = "endossos"


class EndossoDetailAPIView(TenantScopedAPIViewMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Endosso
    serializer_class = EndossoSerializer
    tenant_resource_key = "endossos"


class SalesGoalListCreateAPIView(TenantScopedAPIViewMixin, generics.ListCreateAPIView):
    model = SalesGoal
    serializer_class = SalesGoalSerializer
    ordering = ("-year", "-month", "-created_at")
    tenant_resource_key = "sales_goals"


class SalesGoalDetailAPIView(TenantScopedAPIViewMixin, generics.RetrieveUpdateDestroyAPIView):
    model = SalesGoal
    serializer_class = SalesGoalSerializer
    tenant_resource_key = "sales_goals"


class LeadQualifyAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "leads"

    def post(self, request, pk):
        lead = get_object_or_404(Lead.objects.filter(company=request.company), pk=pk)
        before = _instance_payload(lead)
        try:
            lead.transition_status("QUALIFIED")
        except ValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)

        append_ledger_entry(
            scope="TENANT",
            company=request.company,
            actor=request.user,
            action="UPDATE",
            resource_label=Lead._meta.label,
            resource_pk=str(lead.pk),
            request=request,
            event_type="Lead.QUALIFY",
            data_before=before,
            data_after=_instance_payload(lead),
            metadata={"tenant_resource_key": "leads"},
        )
        return Response(LeadSerializer(lead).data)


class LeadDisqualifyAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "leads"

    def post(self, request, pk):
        lead = get_object_or_404(Lead.objects.filter(company=request.company), pk=pk)
        before = _instance_payload(lead)
        try:
            lead.transition_status("DISQUALIFIED")
        except ValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)

        append_ledger_entry(
            scope="TENANT",
            company=request.company,
            actor=request.user,
            action="UPDATE",
            resource_label=Lead._meta.label,
            resource_pk=str(lead.pk),
            request=request,
            event_type="Lead.DISQUALIFY",
            data_before=before,
            data_after=_instance_payload(lead),
            metadata={"tenant_resource_key": "leads"},
        )
        return Response(LeadSerializer(lead).data)


def _build_customer_from_lead(lead: Lead, company) -> Customer | None:
    customer_email = lead.best_customer_email()
    if not customer_email:
        return None

    customer_name = lead.best_customer_name()
    customer, _ = Customer.all_objects.get_or_create(
        company=company,
        email=customer_email,
        defaults={
            "name": customer_name,
            "legal_name": lead.company_name,
            "trade_name": lead.company_name,
            "phone": lead.phone,
            "whatsapp": lead.whatsapp,
            "document": lead.cnpj,
            "cnpj": lead.cnpj,
            "website": lead.website,
            "linkedin_url": lead.linkedin_url,
            "instagram_url": lead.instagram_url,
            "contact_name": lead.full_name,
            "contact_role": lead.job_title,
            "lead_source": lead.source,
            "industry": lead.company_size_estimate,
            "lifecycle_stage": Customer.STAGE_PROSPECT,
            "notes": lead.notes,
        },
    )
    return customer


def _sync_customer_from_lead(customer: Customer, lead: Lead) -> None:
    changed_fields = []

    if not customer.name:
        customer.name = lead.best_customer_name()
        changed_fields.append("name")
    if not customer.legal_name and lead.company_name:
        customer.legal_name = lead.company_name
        changed_fields.append("legal_name")
    if not customer.trade_name and lead.company_name:
        customer.trade_name = lead.company_name
        changed_fields.append("trade_name")
    if not customer.phone and lead.phone:
        customer.phone = lead.phone
        changed_fields.append("phone")
    if not customer.whatsapp and lead.whatsapp:
        customer.whatsapp = lead.whatsapp
        changed_fields.append("whatsapp")
    if not customer.cnpj and lead.cnpj:
        customer.cnpj = lead.cnpj
        changed_fields.append("cnpj")
    if not customer.document and lead.cnpj:
        customer.document = lead.cnpj
        changed_fields.append("document")
    if not customer.website and lead.website:
        customer.website = lead.website
        changed_fields.append("website")
    if not customer.linkedin_url and lead.linkedin_url:
        customer.linkedin_url = lead.linkedin_url
        changed_fields.append("linkedin_url")
    if not customer.instagram_url and lead.instagram_url:
        customer.instagram_url = lead.instagram_url
        changed_fields.append("instagram_url")
    if not customer.contact_name and lead.full_name:
        customer.contact_name = lead.full_name
        changed_fields.append("contact_name")
    if not customer.contact_role and lead.job_title:
        customer.contact_role = lead.job_title
        changed_fields.append("contact_role")
    if not customer.lead_source and lead.source:
        customer.lead_source = lead.source
        changed_fields.append("lead_source")

    if customer.lifecycle_stage != Customer.STAGE_CUSTOMER:
        customer.lifecycle_stage = Customer.STAGE_CUSTOMER
        changed_fields.append("lifecycle_stage")

    if changed_fields:
        customer.save(update_fields=tuple(sorted(set(changed_fields + ["updated_at"]))))


class LeadConvertAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "leads"

    def post(self, request, pk):
        lead = get_object_or_404(Lead.objects.filter(company=request.company).select_related("customer"), pk=pk)
        lead_before = _instance_payload(lead)
        serializer = LeadConvertSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        if lead.status != "QUALIFIED":
            return Response(
                {"detail": "Lead must be QUALIFIED before conversion."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        requested_customer = serializer.validated_data.get("customer")
        create_customer_if_missing = serializer.validated_data.get(
            "create_customer_if_missing",
            True,
        )
        create_policy_request = serializer.validated_data.get("create_policy_request", True)
        customer = lead.customer or requested_customer
        if lead.customer_id and requested_customer and requested_customer.id != lead.customer_id:
            return Response(
                {"detail": "Lead already linked to another customer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        customer_created = False
        customer_before = _instance_payload(customer) if customer is not None else None

        if customer is None and create_customer_if_missing:
            customer = _build_customer_from_lead(lead, request.company)
            customer_created = customer is not None
            customer_before = None

        if customer is None:
            return Response(
                {
                    "detail": (
                        "Unable to create customer from lead. "
                        "Send customer ID or provide lead email before conversion."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        title = serializer.validated_data.get("title", "").strip()
        if not title:
            title = f"Opportunity from lead #{lead.id}"

        opportunity = None
        policy_request = None
        with transaction.atomic():
            if lead.customer_id is None:
                lead.customer = customer
                lead.save(update_fields=("customer", "updated_at"))
            _sync_customer_from_lead(customer, lead)
            opportunity = Opportunity.objects.create(
                company=request.company,
                customer=customer,
                source_lead=lead,
                title=title,
                stage=serializer.validated_data.get("stage", "QUALIFICATION"),
                product_line=lead.product_line,
                amount=serializer.validated_data.get("amount", 0),
                expected_close_date=serializer.validated_data.get("expected_close_date"),
                needs_payload=lead.needs_payload or {},
            )
            if create_policy_request:
                policy_request = PolicyRequest.objects.create(
                    company=request.company,
                    opportunity=opportunity,
                    customer=customer,
                    source_lead=lead,
                    product_line=lead.product_line,
                    issue_deadline_at=timezone.now() + timedelta(days=2),
                )
            lead.transition_status("CONVERTED")

            # Ledger: tenant-safe, append-only auditing of the conversion chain.
            append_ledger_entry(
                scope="TENANT",
                company=request.company,
                actor=request.user,
                action="UPDATE",
                resource_label=Lead._meta.label,
                resource_pk=str(lead.pk),
                request=request,
                event_type="Lead.CONVERT",
                data_before=lead_before,
                data_after=_instance_payload(lead),
                metadata={
                    "tenant_resource_key": "leads",
                    "customer_id": customer.id,
                    "customer_created": customer_created,
                    "opportunity_id": opportunity.id,
                    "policy_request_id": policy_request.id if policy_request else None,
                },
            )
            append_ledger_entry(
                scope="TENANT",
                company=request.company,
                actor=request.user,
                action="CREATE",
                resource_label=Opportunity._meta.label,
                resource_pk=str(opportunity.pk),
                request=request,
                event_type="Opportunity.CREATE_FROM_LEAD",
                data_before=None,
                data_after=_instance_payload(opportunity),
                metadata={"tenant_resource_key": "opportunities", "source_lead_id": lead.id},
            )
            if policy_request is not None:
                append_ledger_entry(
                    scope="TENANT",
                    company=request.company,
                    actor=request.user,
                    action="CREATE",
                    resource_label=PolicyRequest._meta.label,
                    resource_pk=str(policy_request.pk),
                    request=request,
                    event_type="PolicyRequest.CREATE_FROM_LEAD",
                    data_before=None,
                    data_after=_instance_payload(policy_request),
                    metadata={"tenant_resource_key": "policy_requests", "opportunity_id": opportunity.id},
                )
            if customer is not None:
                append_ledger_entry(
                    scope="TENANT",
                    company=request.company,
                    actor=request.user,
                    action="UPDATE" if not customer_created else "CREATE",
                    resource_label=Customer._meta.label,
                    resource_pk=str(customer.pk),
                    request=request,
                    event_type="Customer.SYNC_FROM_LEAD" if not customer_created else "Customer.CREATE_FROM_LEAD",
                    data_before=customer_before,
                    data_after=_instance_payload(customer),
                    metadata={"tenant_resource_key": "customers", "source_lead_id": lead.id},
                )

        return Response(
            {
                "lead": LeadSerializer(lead).data,
                "customer": CustomerSerializer(customer).data,
                "customer_created": customer_created,
                "opportunity": OpportunitySerializer(opportunity).data,
                "policy_request": (
                    PolicyRequestSerializer(policy_request).data
                    if policy_request is not None
                    else None
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class OpportunityStageUpdateAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "opportunities"

    def post(self, request, pk):
        opportunity = get_object_or_404(
            Opportunity.objects.select_related("customer"),
            pk=pk,
        )
        before = _instance_payload(opportunity)
        serializer = OpportunityStageUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_stage = serializer.validated_data["stage"]
        try:
            opportunity.transition_stage(target_stage)
        except ValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)

        if target_stage == "WON":
            with transaction.atomic():
                # Ensure the customer is promoted to "CUSTOMER" on a won deal.
                customer = opportunity.customer
                customer_before = _instance_payload(customer)
                if customer.lifecycle_stage != Customer.STAGE_CUSTOMER:
                    customer.lifecycle_stage = Customer.STAGE_CUSTOMER
                    customer.save(update_fields=("lifecycle_stage", "updated_at"))
                    append_ledger_entry(
                        scope="TENANT",
                        company=request.company,
                        actor=request.user,
                        action="UPDATE",
                        resource_label=Customer._meta.label,
                        resource_pk=str(customer.pk),
                        request=request,
                        event_type="Customer.PROMOTE_TO_CUSTOMER",
                        data_before=customer_before,
                        data_after=_instance_payload(customer),
                        metadata={"tenant_resource_key": "customers", "opportunity_id": opportunity.id},
                    )

                # Auto-create the handover object if it doesn't exist yet.
                if not hasattr(opportunity, "policy_request"):
                    policy_request = PolicyRequest.objects.create(
                        company=request.company,
                        opportunity=opportunity,
                        customer=customer,
                        source_lead=opportunity.source_lead,
                        product_line=opportunity.product_line,
                        issue_deadline_at=timezone.now() + timedelta(days=2),
                    )
                    append_ledger_entry(
                        scope="TENANT",
                        company=request.company,
                        actor=request.user,
                        action="CREATE",
                        resource_label=PolicyRequest._meta.label,
                        resource_pk=str(policy_request.pk),
                        request=request,
                        event_type="PolicyRequest.AUTO_CREATE_ON_WON",
                        data_before=None,
                        data_after=_instance_payload(policy_request),
                        metadata={"tenant_resource_key": "policy_requests", "opportunity_id": opportunity.id},
                    )

        append_ledger_entry(
            scope="TENANT",
            company=request.company,
            actor=request.user,
            action="UPDATE",
            resource_label=Opportunity._meta.label,
            resource_pk=str(opportunity.pk),
            request=request,
            event_type="Opportunity.STAGE_CHANGE",
            data_before=before,
            data_after=_instance_payload(opportunity),
            metadata={"tenant_resource_key": "opportunities", "target_stage": target_stage},
        )

        return Response(OpportunitySerializer(opportunity).data)


class TenantDashboardSummaryAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "dashboard"

    def get(self, request):
        today = timezone.localdate()
        start_of_year = date(today.year, 1, 1)
        start_of_month = date(today.year, today.month, 1)

        endossos_ytd = Endosso.objects.filter(data_emissao__gte=start_of_year)
        endossos_mtd = Endosso.objects.filter(data_emissao__gte=start_of_month)

        ytd_totals = endossos_ytd.aggregate(
            premium_total=Sum("premio_total"),
            commission_total=Sum("valor_comissao"),
        )
        mtd_totals = endossos_mtd.aggregate(
            premium_total=Sum("premio_total"),
            commission_total=Sum("valor_comissao"),
        )

        renewals_due_next_30d = Apolice.objects.filter(
            status="ATIVA",
            fim_vigencia__gte=today,
            fim_vigencia__lte=today + timedelta(days=30),
        ).count()
        renewals_mtd = endossos_mtd.filter(tipo="RENOVACAO").count()

        customers_total = Customer.objects.filter(
            lifecycle_stage=Customer.STAGE_CUSTOMER
        ).count()

        # Goals: month and year-to-date.
        month_goal = SalesGoal.objects.filter(year=today.year, month=today.month).first()
        sales_goal_id_mtd = int(month_goal.id) if month_goal is not None else None
        premium_goal_mtd = float(getattr(month_goal, "premium_goal", 0) or 0)
        commission_goal_mtd = float(getattr(month_goal, "commission_goal", 0) or 0)
        new_customers_goal_mtd = int(getattr(month_goal, "new_customers_goal", 0) or 0)

        ytd_goals = SalesGoal.objects.filter(
            year=today.year,
            month__lte=today.month,
        ).aggregate(
            premium_goal=Sum("premium_goal"),
            commission_goal=Sum("commission_goal"),
            new_customers_goal=Sum("new_customers_goal"),
        )
        premium_goal_ytd = float(ytd_goals.get("premium_goal") or 0)
        commission_goal_ytd = float(ytd_goals.get("commission_goal") or 0)
        new_customers_goal_ytd = int(ytd_goals.get("new_customers_goal") or 0)

        premium_ytd = float(ytd_totals.get("premium_total") or 0)
        commission_ytd = float(ytd_totals.get("commission_total") or 0)
        premium_mtd = float(mtd_totals.get("premium_total") or 0)
        commission_mtd = float(mtd_totals.get("commission_total") or 0)

        def pct(realized: float, goal: float) -> float:
            if goal <= 0:
                return 0.0
            return round((realized / goal) * 100.0, 2)

        # Series for charts.
        daily_rows = (
            endossos_mtd.values("data_emissao")
            .annotate(
                premium_total=Sum("premio_total"),
                commission_total=Sum("valor_comissao"),
            )
            .order_by("data_emissao")
        )
        daily_map = {
            row["data_emissao"]: {
                "premium_total": float(row["premium_total"] or 0),
                "commission_total": float(row["commission_total"] or 0),
            }
            for row in daily_rows
        }
        daily_series = []
        cursor = start_of_month
        while cursor <= today:
            day_values = daily_map.get(cursor, {"premium_total": 0.0, "commission_total": 0.0})
            daily_series.append(
                {
                    "date": cursor.isoformat(),
                    "premium_total": day_values["premium_total"],
                    "commission_total": day_values["commission_total"],
                }
            )
            cursor += timedelta(days=1)

        monthly_rows = (
            endossos_ytd.values("data_emissao__month")
            .annotate(
                premium_total=Sum("premio_total"),
                commission_total=Sum("valor_comissao"),
            )
            .order_by("data_emissao__month")
        )
        monthly_map = {
            int(row["data_emissao__month"]): {
                "premium_total": float(row["premium_total"] or 0),
                "commission_total": float(row["commission_total"] or 0),
            }
            for row in monthly_rows
            if row.get("data_emissao__month") is not None
        }
        monthly_series = []
        for month in range(1, today.month + 1):
            values = monthly_map.get(month, {"premium_total": 0.0, "commission_total": 0.0})
            monthly_series.append(
                {
                    "month": month,
                    "premium_total": values["premium_total"],
                    "commission_total": values["commission_total"],
                }
            )

        payload = {
            "tenant_code": request.company.tenant_code,
            "generated_at": timezone.now().isoformat(),
            "period": {
                "as_of": today.isoformat(),
                "year": today.year,
                "month": today.month,
            },
            "kpis": {
                "production_premium_ytd": premium_ytd,
                "commission_ytd": commission_ytd,
                "production_premium_mtd": premium_mtd,
                "commission_mtd": commission_mtd,
                "renewals_due_next_30d": renewals_due_next_30d,
                "renewals_mtd": renewals_mtd,
                "customers_total": customers_total,
                # Placeholder until receivables/installments are modeled.
                "delinquency_open_total": 0.0,
            },
            "goals": {
                "sales_goal_id_mtd": sales_goal_id_mtd,
                "premium_goal_mtd": premium_goal_mtd,
                "commission_goal_mtd": commission_goal_mtd,
                "new_customers_goal_mtd": new_customers_goal_mtd,
                "premium_goal_ytd": premium_goal_ytd,
                "commission_goal_ytd": commission_goal_ytd,
                "new_customers_goal_ytd": new_customers_goal_ytd,
            },
            "progress": {
                "premium_mtd_pct": pct(premium_mtd, premium_goal_mtd),
                "commission_mtd_pct": pct(commission_mtd, commission_goal_mtd),
                "premium_ytd_pct": pct(premium_ytd, premium_goal_ytd),
                "commission_ytd_pct": pct(commission_ytd, commission_goal_ytd),
            },
            "series": {
                "daily_mtd": daily_series,
                "monthly_ytd": monthly_series,
            },
        }
        return Response(payload)


class CommercialActivityListCreateAPIView(
    TenantScopedAPIViewMixin, generics.ListCreateAPIView
):
    model = CommercialActivity
    serializer_class = CommercialActivitySerializer
    ordering = ("status", "due_at", "-created_at")
    tenant_resource_key = "activities"

    def perform_create(self, serializer):
        activity = serializer.save(
            company=self.request.company,
            created_by=self.request.user,
        )
        self._append_ledger(
            "CREATE",
            activity,
            after=_instance_payload(activity),
            metadata={"created_by_user_id": self.request.user.id},
        )
        return activity


class CommercialActivityDetailAPIView(
    TenantScopedAPIViewMixin, generics.RetrieveUpdateDestroyAPIView
):
    model = CommercialActivity
    serializer_class = CommercialActivitySerializer
    tenant_resource_key = "activities"


class CommercialActivityCompleteAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "activities"

    def post(self, request, pk):
        activity = get_object_or_404(CommercialActivity.objects.filter(company=request.company), pk=pk)
        before = _instance_payload(activity)
        activity.mark_done()
        append_ledger_entry(
            scope="TENANT",
            company=request.company,
            actor=request.user,
            action="UPDATE",
            resource_label=CommercialActivity._meta.label,
            resource_pk=str(activity.pk),
            request=request,
            event_type="CommercialActivity.COMPLETE",
            data_before=before,
            data_after=_instance_payload(activity),
            metadata={"tenant_resource_key": "activities"},
        )
        return Response(CommercialActivitySerializer(activity).data)


class CommercialActivityReopenAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "activities"

    def post(self, request, pk):
        activity = get_object_or_404(CommercialActivity.objects.filter(company=request.company), pk=pk)
        before = _instance_payload(activity)
        activity.reopen()
        append_ledger_entry(
            scope="TENANT",
            company=request.company,
            actor=request.user,
            action="UPDATE",
            resource_label=CommercialActivity._meta.label,
            resource_pk=str(activity.pk),
            request=request,
            event_type="CommercialActivity.REOPEN",
            data_before=before,
            data_after=_instance_payload(activity),
            metadata={"tenant_resource_key": "activities"},
        )
        return Response(CommercialActivitySerializer(activity).data)


class CommercialActivityRemindersAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "activities"

    def get(self, request):
        now = timezone.now()
        reminders = (
            CommercialActivity.objects.filter(
                status=CommercialActivity.STATUS_PENDING,
                reminder_sent=False,
                reminder_at__isnull=False,
                reminder_at__lte=now,
            )
            .select_related("assigned_to", "created_by")
            .order_by("reminder_at", "priority")
        )
        serializer = CommercialActivitySerializer(reminders, many=True)
        return Response(serializer.data)


class CommercialActivityMarkRemindedAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "activities"

    def post(self, request, pk):
        activity = get_object_or_404(CommercialActivity.objects.filter(company=request.company), pk=pk)
        before = _instance_payload(activity)
        activity.reminder_sent = True
        activity.save(update_fields=("reminder_sent", "updated_at"))
        append_ledger_entry(
            scope="TENANT",
            company=request.company,
            actor=request.user,
            action="UPDATE",
            resource_label=CommercialActivity._meta.label,
            resource_pk=str(activity.pk),
            request=request,
            event_type="CommercialActivity.MARK_REMINDED",
            data_before=before,
            data_after=_instance_payload(activity),
            metadata={"tenant_resource_key": "activities"},
        )
        return Response(CommercialActivitySerializer(activity).data)


class LeadHistoryAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "leads"

    def get(self, request, pk):
        lead = get_object_or_404(Lead.objects.filter(company=request.company), pk=pk)
        activities = CommercialActivity.objects.filter(lead=lead).select_related(
            "assigned_to", "created_by"
        )
        opportunities = Opportunity.objects.filter(source_lead=lead)
        payload = LeadHistorySerializer(
            {
                "lead": lead,
                "activities": activities,
                "converted_opportunities": opportunities,
            }
        ).data
        return Response(payload)


class OpportunityHistoryAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "opportunities"

    def get(self, request, pk):
        opportunity = get_object_or_404(Opportunity.objects.filter(company=request.company), pk=pk)
        activities = CommercialActivity.objects.filter(opportunity=opportunity).select_related(
            "assigned_to", "created_by"
        )
        payload = OpportunityHistorySerializer(
            {"opportunity": opportunity, "activities": activities}
        ).data
        return Response(payload)


def _instance_payload(instance) -> dict:
    fields = [
        field.name
        for field in instance._meta.fields
        if field.name not in {"company", "ai_insights"}
    ]
    payload = model_to_dict(instance, fields=fields)
    if isinstance(instance, Customer):
        payload["contacts"] = list(
            instance.contacts.all()
            .order_by("-is_primary", "id")
            .values(
                "id",
                "name",
                "email",
                "phone",
                "role",
                "is_primary",
                "notes",
            )
        )
    return payload


class BaseCommercialAIInsightsAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    model = None
    tenant_resource_key = None
    entity_type = "ENTITY"
    select_related = ()

    def get_queryset(self):
        queryset = self.model.objects.all()
        if self.select_related:
            queryset = queryset.select_related(*self.select_related)
        return queryset

    def _extract_cnpj(self, instance) -> str:
        if hasattr(instance, "cnpj"):
            return sanitize_cnpj(getattr(instance, "cnpj", ""))
        if hasattr(instance, "cliente_cpf_cnpj"):
            return sanitize_cnpj(getattr(instance, "cliente_cpf_cnpj", ""))
        if isinstance(instance, PolicyRequest):
            if instance.customer_id:
                return sanitize_cnpj(getattr(instance.customer, "cnpj", ""))
            if instance.source_lead_id:
                return sanitize_cnpj(getattr(instance.source_lead, "cnpj", ""))
        if isinstance(instance, ProposalOption):
            return sanitize_cnpj(getattr(instance.opportunity.customer, "cnpj", ""))
        if isinstance(instance, Opportunity):
            return sanitize_cnpj(getattr(instance.customer, "cnpj", ""))
        if isinstance(instance, Endosso):
            return sanitize_cnpj(getattr(instance.apolice, "cliente_cpf_cnpj", ""))
        return ""

    def _apply_cnpj_profile(self, instance, cnpj_profile: dict) -> list[str]:
        if isinstance(instance, Lead):
            return apply_cnpj_profile_to_lead(instance, cnpj_profile)
        if isinstance(instance, Customer):
            return apply_cnpj_profile_to_customer(instance, cnpj_profile)
        return []

    def post(self, request, pk):
        insight_serializer = AIInsightRequestSerializer(data=request.data or {})
        insight_serializer.is_valid(raise_exception=True)

        instance = get_object_or_404(self.get_queryset(), pk=pk)
        include_cnpj_enrichment = insight_serializer.validated_data.get(
            "include_cnpj_enrichment",
            True,
        )
        focus = insight_serializer.validated_data.get("focus", "").strip()

        cnpj_profile = None
        cnpj = self._extract_cnpj(instance)
        if include_cnpj_enrichment and cnpj:
            cnpj_profile = lookup_cnpj_profile(cnpj)

        payload = _instance_payload(instance)
        insights = generate_commercial_insights(
            entity_type=self.entity_type,
            payload=payload,
            focus=focus,
            cnpj_profile=cnpj_profile,
        )

        updated_fields = []
        if cnpj_profile and cnpj_profile.get("success"):
            updated_fields = self._apply_cnpj_profile(instance, cnpj_profile)
            instance.refresh_from_db()

        current_ai = instance.ai_insights if isinstance(instance.ai_insights, dict) else {}
        history = list(current_ai.get("history", []))
        history.append(insights)
        history = history[-5:]
        instance.ai_insights = {**current_ai, "latest": insights, "history": history}

        model_update_fields = ["ai_insights", "updated_at"]
        if isinstance(instance, Lead) and insights.get("qualification_score") is not None:
            instance.qualification_score = insights["qualification_score"]
            model_update_fields.append("qualification_score")
        instance.save(update_fields=tuple(sorted(set(model_update_fields))))

        return Response(
            {
                "tenant_code": request.company.tenant_code,
                "entity_type": self.entity_type,
                "entity_id": instance.id,
                "insights": insights,
                "cnpj_profile": cnpj_profile,
                "updated_fields": updated_fields,
            }
        )


class CommissionPlanScopeListCreateAPIView(
    TenantScopedAPIViewMixin, generics.ListCreateAPIView
):
    model = CommissionPlanScope
    serializer_class = CommissionPlanScopeSerializer
    ordering = ("-priority", "-created_at")
    tenant_resource_key = "commission_plans"


class CommissionPlanScopeDetailAPIView(
    TenantScopedAPIViewMixin, generics.RetrieveUpdateDestroyAPIView
):
    model = CommissionPlanScope
    serializer_class = CommissionPlanScopeSerializer
    tenant_resource_key = "commission_plans"


class CommissionAccrualListAPIView(TenantScopedAPIViewMixin, generics.ListAPIView):
    model = CommissionAccrual
    serializer_class = CommissionAccrualSerializer
    ordering = ("-created_at",)
    tenant_resource_key = "commission_accruals"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("recipient")
        
        # Filters
        period_start = self.request.query_params.get("period_start")
        period_end = self.request.query_params.get("period_end")
        producer_id = self.request.query_params.get("producer_id")
        policy_id = self.request.query_params.get("policy_id")

        if period_start:
            queryset = queryset.filter(created_at__date__gte=period_start)
        if period_end:
            queryset = queryset.filter(created_at__date__lte=period_end)
        if producer_id:
            queryset = queryset.filter(recipient_id=producer_id)
        
        if policy_id:
            # Complex filter: Accruals linked to Endosso or Installment of the Policy
            endosso_ct = ContentType.objects.get_for_model(Endosso)
            installment_ct = ContentType.objects.get_for_model(Installment)
            
            endosso_ids = Endosso.objects.filter(
                company=self.request.company, apolice_id=policy_id
            ).values_list("id", flat=True)
            
            installment_ids = Installment.objects.filter(
                company=self.request.company, endosso__apolice_id=policy_id
            ).values_list("id", flat=True)

            queryset = queryset.filter(
                Q(content_type=endosso_ct, object_id__in=endosso_ids) |
                Q(content_type=installment_ct, object_id__in=installment_ids)
            )

        return queryset


class CommissionPayoutBatchListCreateAPIView(
    TenantScopedAPIViewMixin, generics.ListCreateAPIView
):
    model = CommissionPayoutBatch
    serializer_class = CommissionPayoutBatchSerializer
    ordering = ("-created_at",)
    tenant_resource_key = "commission_payouts"

    def create(self, request, *args, **kwargs):
        serializer = CommissionPayoutBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        batch = create_commission_payout_batch(
            company=request.company,
            period_from=serializer.validated_data["period_start"],
            period_to=serializer.validated_data["period_end"],
            created_by=request.user,
            producer_id=serializer.validated_data.get("producer_id"),
        )

        if not batch:
            return Response(
                {"detail": "No eligible accruals found for this period."},
                status=status.HTTP_400_BAD_REQUEST
            )

        self._append_ledger(
            "CREATE",
            batch,
            after=_instance_payload(batch),
            metadata={"tenant_resource_key": "commission_payouts"},
        )
        return Response(
            CommissionPayoutBatchSerializer(batch).data,
            status=status.HTTP_201_CREATED
        )


class CommissionPayoutBatchDetailAPIView(
    TenantScopedAPIViewMixin, generics.RetrieveDestroyAPIView
):
    model = CommissionPayoutBatch
    serializer_class = CommissionPayoutBatchSerializer
    tenant_resource_key = "commission_payouts"


class CommissionPayoutBatchApproveAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "commission_payouts"

    def post(self, request, pk):
        try:
            approve_commission_payout_batch(pk, request.user, request.company)
        except (ValidationError, PermissionDenied) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        
        batch = get_object_or_404(CommissionPayoutBatch, pk=pk, company=request.company)
        return Response(CommissionPayoutBatchSerializer(batch).data)


class InsurerSettlementBatchListCreateAPIView(
    TenantScopedAPIViewMixin, generics.ListCreateAPIView
):
    model = InsurerSettlementBatch
    serializer_class = InsurerSettlementBatchSerializer
    ordering = ("-created_at",)
    tenant_resource_key = "insurer_settlements"

    def create(self, request, *args, **kwargs):
        serializer = InsurerSettlementBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        batch = create_insurer_settlement_batch(
            company=request.company,
            insurer_name=serializer.validated_data["insurer_name"],
            period_start=serializer.validated_data["period_start"],
            period_end=serializer.validated_data["period_end"],
            created_by=request.user,
        )

        if not batch:
            return Response(
                {"detail": "No eligible settlements found for this insurer/period."},
                status=status.HTTP_400_BAD_REQUEST
            )

        self._append_ledger(
            "CREATE",
            batch,
            after=_instance_payload(batch),
            metadata={"tenant_resource_key": "insurer_settlements"},
        )
        return Response(
            InsurerSettlementBatchSerializer(batch).data,
            status=status.HTTP_201_CREATED
        )


class InsurerSettlementBatchDetailAPIView(
    TenantScopedAPIViewMixin, generics.RetrieveDestroyAPIView
):
    model = InsurerSettlementBatch
    serializer_class = InsurerSettlementBatchSerializer
    tenant_resource_key = "insurer_settlements"


class InsurerSettlementBatchApproveAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "insurer_settlements"

    def post(self, request, pk):
        try:
            approve_insurer_settlement_batch(pk, request.user, request.company)
        except (ValidationError, PermissionDenied) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        
        batch = get_object_or_404(InsurerSettlementBatch, pk=pk, company=request.company)
        return Response(InsurerSettlementBatchSerializer(batch).data)


class LeadAIInsightsAPIView(BaseCommercialAIInsightsAPIView):
    model = Lead
    tenant_resource_key = "leads"
    entity_type = "LEAD"
    select_related = ("customer",)


class CustomerAIInsightsAPIView(BaseCommercialAIInsightsAPIView):
    model = Customer
    tenant_resource_key = "customers"
    entity_type = "CUSTOMER"


class OpportunityAIInsightsAPIView(BaseCommercialAIInsightsAPIView):
    model = Opportunity
    tenant_resource_key = "opportunities"
    entity_type = "OPPORTUNITY"
    select_related = ("customer", "source_lead")


class ApoliceAIInsightsAPIView(BaseCommercialAIInsightsAPIView):
    model = Apolice
    tenant_resource_key = "apolices"
    entity_type = "APOLICE"


class EndossoAIInsightsAPIView(BaseCommercialAIInsightsAPIView):
    model = Endosso
    tenant_resource_key = "endossos"
    entity_type = "ENDOSSO"
    select_related = ("apolice",)


class CommercialActivityAIInsightsAPIView(BaseCommercialAIInsightsAPIView):
    model = CommercialActivity
    tenant_resource_key = "activities"
    entity_type = "COMMERCIAL_ACTIVITY"
    select_related = ("lead", "opportunity", "assigned_to")


class ProposalOptionAIInsightsAPIView(BaseCommercialAIInsightsAPIView):
    model = ProposalOption
    tenant_resource_key = "proposal_options"
    entity_type = "PROPOSAL_OPTION"
    select_related = ("opportunity",)


class PolicyRequestAIInsightsAPIView(BaseCommercialAIInsightsAPIView):
    model = PolicyRequest
    tenant_resource_key = "policy_requests"
    entity_type = "POLICY_REQUEST"
    select_related = ("opportunity", "customer", "source_lead")


class BaseCNPJEnrichmentAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    model = None
    tenant_resource_key = None

    def get_queryset(self):
        return self.model.objects.all()

    def _extract_default_cnpj(self, instance) -> str:
        if hasattr(instance, "cnpj"):
            return sanitize_cnpj(getattr(instance, "cnpj", ""))
        if hasattr(instance, "document"):
            return sanitize_cnpj(getattr(instance, "document", ""))
        return ""

    def _apply_profile(self, instance, profile: dict) -> list[str]:
        return []

    def post(self, request, pk):
        instance = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = CNPJEnrichmentRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        cnpj = sanitize_cnpj(serializer.validated_data.get("cnpj", "")) or self._extract_default_cnpj(
            instance
        )
        if not cnpj:
            return Response(
                {"detail": "CNPJ not informed in payload or resource data."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = lookup_cnpj_profile(cnpj)
        if not profile.get("success"):
            return Response(
                {
                    "detail": profile.get("error", "CNPJ lookup failed."),
                    "cnpj_profile": profile,
                },
                status=status.HTTP_424_FAILED_DEPENDENCY,
            )

        updated_fields = self._apply_profile(instance, profile)
        return Response(
            {
                "tenant_code": request.company.tenant_code,
                "entity_id": instance.id,
                "cnpj_profile": profile,
                "updated_fields": updated_fields,
            }
        )


class LeadCNPJEnrichmentAPIView(BaseCNPJEnrichmentAPIView):
    model = Lead
    tenant_resource_key = "leads"

    def _apply_profile(self, instance, profile: dict) -> list[str]:
        return apply_cnpj_profile_to_lead(instance, profile)


class CustomerCNPJEnrichmentAPIView(BaseCNPJEnrichmentAPIView):
    model = Customer
    tenant_resource_key = "customers"

    def _apply_profile(self, instance, profile: dict) -> list[str]:
        return apply_cnpj_profile_to_customer(instance, profile)


class SalesMetricsAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "metrics"

    def _parse_filters(self, request):
        from_raw = request.query_params.get("from", "").strip()
        to_raw = request.query_params.get("to", "").strip()
        assigned_to_raw = request.query_params.get("assigned_to", "").strip()

        from_date = parse_date(from_raw) if from_raw else None
        to_date = parse_date(to_raw) if to_raw else None
        if from_raw and from_date is None:
            return None, Response(
                {"detail": "Invalid 'from' date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if to_raw and to_date is None:
            return None, Response(
                {"detail": "Invalid 'to' date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if from_date and to_date and from_date > to_date:
            return None, Response(
                {"detail": "'from' date cannot be greater than 'to' date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assigned_to_user_id = None
        if assigned_to_raw:
            try:
                assigned_to_user_id = int(assigned_to_raw)
            except ValueError:
                return None, Response(
                    {"detail": "Invalid 'assigned_to'. Send a numeric user ID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return (
            {
                "from_date": from_date,
                "to_date": to_date,
                "assigned_to_user_id": assigned_to_user_id,
            },
            None,
        )

    def get(self, request):
        filters, error_response = self._parse_filters(request)
        if error_response is not None:
            return error_response

        from_date = filters["from_date"]
        to_date = filters["to_date"]
        assigned_to_user_id = filters["assigned_to_user_id"]

        leads_qs = Lead.objects.all()
        opportunities_qs = Opportunity.objects.all()
        policy_requests_qs = PolicyRequest.objects.all()
        activities_qs = CommercialActivity.objects.filter(
            status=CommercialActivity.STATUS_PENDING
        )
        if from_date:
            leads_qs = leads_qs.filter(created_at__date__gte=from_date)
            opportunities_qs = opportunities_qs.filter(created_at__date__gte=from_date)
            policy_requests_qs = policy_requests_qs.filter(created_at__date__gte=from_date)
            activities_qs = activities_qs.filter(created_at__date__gte=from_date)
        if to_date:
            leads_qs = leads_qs.filter(created_at__date__lte=to_date)
            opportunities_qs = opportunities_qs.filter(created_at__date__lte=to_date)
            policy_requests_qs = policy_requests_qs.filter(created_at__date__lte=to_date)
            activities_qs = activities_qs.filter(created_at__date__lte=to_date)
        if assigned_to_user_id is not None:
            activities_qs = activities_qs.filter(assigned_to_id=assigned_to_user_id)

        lead_counts = {
            row["status"]: row["total"]
            for row in leads_qs.values("status")
            .annotate(total=Count("id"))
            .order_by()
        }
        opportunity_counts = {
            row["stage"]: row["total"]
            for row in opportunities_qs.values("stage")
            .annotate(total=Count("id"))
            .order_by()
        }
        policy_request_counts = {
            row["status"]: row["total"]
            for row in policy_requests_qs.values("status")
            .annotate(total=Count("id"))
            .order_by()
        }

        now = timezone.now()
        activities_info = {
            "open_total": activities_qs.count(),
            "overdue_total": activities_qs.filter(due_at__lt=now).count(),
            "due_today_total": activities_qs.filter(due_at__date=now.date()).count(),
            "reminders_due_total": activities_qs.filter(
                reminder_sent=False,
                reminder_at__isnull=False,
                reminder_at__lte=now,
            ).count(),
            "sla_breached_total": activities_qs.filter(sla_due_at__lt=now).count(),
        }
        activities_by_priority = {
            "LOW": activities_qs.filter(priority=CommercialActivity.PRIORITY_LOW).count(),
            "MEDIUM": activities_qs.filter(priority=CommercialActivity.PRIORITY_MEDIUM).count(),
            "HIGH": activities_qs.filter(priority=CommercialActivity.PRIORITY_HIGH).count(),
            "URGENT": activities_qs.filter(priority=CommercialActivity.PRIORITY_URGENT).count(),
        }

        total_leads = sum(lead_counts.values()) or 0
        converted_leads = lead_counts.get("CONVERTED", 0)
        total_opportunities = sum(opportunity_counts.values()) or 0
        won_opportunities = opportunity_counts.get("WON", 0)

        conversion = {
            "lead_to_opportunity_rate": (
                round((converted_leads / total_leads) * 100, 2) if total_leads else 0.0
            ),
            "opportunity_win_rate": (
                round((won_opportunities / total_opportunities) * 100, 2)
                if total_opportunities
                else 0.0
            ),
        }
        today = timezone.localdate()
        thirty_days_from_now = today + timedelta(days=30)
        open_stages = (
            "NEW",
            "DISCOVERY",
            "QUALIFICATION",
            "NEEDS_ASSESSMENT",
            "QUOTATION",
            "PROPOSAL",
            "PROPOSAL_PRESENTATION",
            "NEGOTIATION",
        )
        pipeline_values = opportunities_qs.aggregate(
            open_total_amount=Sum(
                "amount",
                filter=Q(stage__in=open_stages),
            ),
            won_total_amount=Sum("amount", filter=Q(stage="WON")),
            lost_total_amount=Sum("amount", filter=Q(stage="LOST")),
            expected_close_next_30d_amount=Sum(
                "amount",
                filter=Q(
                    stage__in=open_stages,
                    expected_close_date__gte=today,
                    expected_close_date__lte=thirty_days_from_now,
                ),
            ),
        )
        pipeline_value = {
            key: round(float(value or 0), 2)
            for key, value in pipeline_values.items()
        }
        discovery_total = (
            opportunity_counts.get("NEW", 0) + opportunity_counts.get("DISCOVERY", 0)
        )
        proposal_total = (
            opportunity_counts.get("PROPOSAL", 0)
            + opportunity_counts.get("PROPOSAL_PRESENTATION", 0)
        )

        payload = SalesMetricsSerializer(
            {
                "tenant_code": request.company.tenant_code,
                "period": {
                    "from_date": from_date,
                    "to_date": to_date,
                    "assigned_to_user_id": assigned_to_user_id,
                },
                "lead_funnel": {
                    "NEW": lead_counts.get("NEW", 0),
                    "QUALIFIED": lead_counts.get("QUALIFIED", 0),
                    "DISQUALIFIED": lead_counts.get("DISQUALIFIED", 0),
                    "CONVERTED": lead_counts.get("CONVERTED", 0),
                },
                "opportunity_funnel": {
                    "NEW": opportunity_counts.get("NEW", 0),
                    "QUALIFICATION": opportunity_counts.get("QUALIFICATION", 0),
                    "NEEDS_ASSESSMENT": opportunity_counts.get("NEEDS_ASSESSMENT", 0),
                    "QUOTATION": opportunity_counts.get("QUOTATION", 0),
                    "PROPOSAL_PRESENTATION": opportunity_counts.get(
                        "PROPOSAL_PRESENTATION",
                        0,
                    ),
                    "NEGOTIATION": opportunity_counts.get("NEGOTIATION", 0),
                    "WON": opportunity_counts.get("WON", 0),
                    "LOST": opportunity_counts.get("LOST", 0),
                    "DISCOVERY": discovery_total,
                    "PROPOSAL": proposal_total,
                },
                "policy_requests": {
                    "PENDING_DATA": policy_request_counts.get("PENDING_DATA", 0),
                    "UNDER_REVIEW": policy_request_counts.get("UNDER_REVIEW", 0),
                    "READY_TO_ISSUE": policy_request_counts.get("READY_TO_ISSUE", 0),
                    "ISSUED": policy_request_counts.get("ISSUED", 0),
                    "REJECTED": policy_request_counts.get("REJECTED", 0),
                },
                "activities": activities_info,
                "activities_by_priority": activities_by_priority,
                "pipeline_value": pipeline_value,
                "conversion": conversion,
            }
        ).data
        return Response(payload)
