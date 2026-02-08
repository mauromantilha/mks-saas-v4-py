from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.forms.models import model_to_dict
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

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
    Lead,
    Opportunity,
)
from operational.serializers import (
    AIInsightRequestSerializer,
    ApoliceSerializer,
    CNPJEnrichmentRequestSerializer,
    CommercialActivitySerializer,
    CustomerSerializer,
    LeadHistorySerializer,
    LeadConvertSerializer,
    EndossoSerializer,
    LeadSerializer,
    OpportunityHistorySerializer,
    OpportunityStageUpdateSerializer,
    OpportunitySerializer,
    SalesMetricsSerializer,
)
from tenancy.permissions import IsTenantRoleAllowed


class TenantScopedAPIViewMixin:
    permission_classes = [IsTenantRoleAllowed]
    model = None
    ordering = ()

    def get_queryset(self):
        queryset = self.model.objects.all()
        if self.ordering:
            return queryset.order_by(*self.ordering)
        return queryset


class CustomerListCreateAPIView(TenantScopedAPIViewMixin, generics.ListCreateAPIView):
    """
    Isolamento por tenant via manager padrão.
    RBAC por método HTTP via IsTenantRoleAllowed.
    """

    model = Customer
    serializer_class = CustomerSerializer
    ordering = ("name",)
    tenant_resource_key = "customers"


class CustomerDetailAPIView(TenantScopedAPIViewMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Customer
    serializer_class = CustomerSerializer
    tenant_resource_key = "customers"


class LeadListCreateAPIView(TenantScopedAPIViewMixin, generics.ListCreateAPIView):
    model = Lead
    serializer_class = LeadSerializer
    ordering = ("-created_at",)
    tenant_resource_key = "leads"


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


class LeadQualifyAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "leads"

    def post(self, request, pk):
        lead = get_object_or_404(Lead.objects.all(), pk=pk)
        try:
            lead.transition_status("QUALIFIED")
        except ValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response(LeadSerializer(lead).data)


class LeadDisqualifyAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "leads"

    def post(self, request, pk):
        lead = get_object_or_404(Lead.objects.all(), pk=pk)
        try:
            lead.transition_status("DISQUALIFIED")
        except ValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
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
            "lifecycle_stage": Customer.STAGE_PROSPECT,
            "notes": lead.notes,
        },
    )
    return customer


class LeadConvertAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "leads"

    def post(self, request, pk):
        lead = get_object_or_404(Lead.objects.select_related("customer"), pk=pk)
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
        customer = lead.customer or requested_customer
        if lead.customer_id and requested_customer and requested_customer.id != lead.customer_id:
            return Response(
                {"detail": "Lead already linked to another customer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        customer_created = False

        if customer is None and create_customer_if_missing:
            customer = _build_customer_from_lead(lead, request.company)
            customer_created = customer is not None

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

        with transaction.atomic():
            if lead.customer_id is None:
                lead.customer = customer
                lead.save(update_fields=("customer", "updated_at"))
            opportunity = Opportunity.objects.create(
                company=request.company,
                customer=customer,
                source_lead=lead,
                title=title,
                stage=serializer.validated_data.get("stage", "DISCOVERY"),
                amount=serializer.validated_data.get("amount", 0),
                expected_close_date=serializer.validated_data.get("expected_close_date"),
            )
            lead.transition_status("CONVERTED")

        return Response(
            {
                "lead": LeadSerializer(lead).data,
                "customer": CustomerSerializer(customer).data,
                "customer_created": customer_created,
                "opportunity": OpportunitySerializer(opportunity).data,
            },
            status=status.HTTP_201_CREATED,
        )


class OpportunityStageUpdateAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "opportunities"

    def post(self, request, pk):
        opportunity = get_object_or_404(Opportunity.objects.all(), pk=pk)
        serializer = OpportunityStageUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_stage = serializer.validated_data["stage"]
        try:
            opportunity.transition_stage(target_stage)
        except ValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OpportunitySerializer(opportunity).data)


class CommercialActivityListCreateAPIView(
    TenantScopedAPIViewMixin, generics.ListCreateAPIView
):
    model = CommercialActivity
    serializer_class = CommercialActivitySerializer
    ordering = ("status", "due_at", "-created_at")
    tenant_resource_key = "activities"

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.company,
            created_by=self.request.user,
        )


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
        activity = get_object_or_404(CommercialActivity.objects.all(), pk=pk)
        activity.mark_done()
        return Response(CommercialActivitySerializer(activity).data)


class CommercialActivityReopenAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "activities"

    def post(self, request, pk):
        activity = get_object_or_404(CommercialActivity.objects.all(), pk=pk)
        activity.reopen()
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
        activity = get_object_or_404(CommercialActivity.objects.all(), pk=pk)
        activity.reminder_sent = True
        activity.save(update_fields=("reminder_sent", "updated_at"))
        return Response(CommercialActivitySerializer(activity).data)


class LeadHistoryAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "leads"

    def get(self, request, pk):
        lead = get_object_or_404(Lead.objects.all(), pk=pk)
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
        opportunity = get_object_or_404(Opportunity.objects.all(), pk=pk)
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
    return model_to_dict(instance, fields=fields)


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
        activities_qs = CommercialActivity.objects.filter(
            status=CommercialActivity.STATUS_PENDING
        )
        if from_date:
            leads_qs = leads_qs.filter(created_at__date__gte=from_date)
            opportunities_qs = opportunities_qs.filter(created_at__date__gte=from_date)
            activities_qs = activities_qs.filter(created_at__date__gte=from_date)
        if to_date:
            leads_qs = leads_qs.filter(created_at__date__lte=to_date)
            opportunities_qs = opportunities_qs.filter(created_at__date__lte=to_date)
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
        pipeline_values = opportunities_qs.aggregate(
            open_total_amount=Sum(
                "amount",
                filter=Q(
                    stage__in=(
                        "DISCOVERY",
                        "PROPOSAL",
                        "NEGOTIATION",
                    )
                ),
            ),
            won_total_amount=Sum("amount", filter=Q(stage="WON")),
            lost_total_amount=Sum("amount", filter=Q(stage="LOST")),
            expected_close_next_30d_amount=Sum(
                "amount",
                filter=Q(
                    stage__in=("DISCOVERY", "PROPOSAL", "NEGOTIATION"),
                    expected_close_date__gte=today,
                    expected_close_date__lte=thirty_days_from_now,
                ),
            ),
        )
        pipeline_value = {
            key: round(float(value or 0), 2)
            for key, value in pipeline_values.items()
        }

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
                    "DISCOVERY": opportunity_counts.get("DISCOVERY", 0),
                    "PROPOSAL": opportunity_counts.get("PROPOSAL", 0),
                    "NEGOTIATION": opportunity_counts.get("NEGOTIATION", 0),
                    "WON": opportunity_counts.get("WON", 0),
                    "LOST": opportunity_counts.get("LOST", 0),
                },
                "activities": activities_info,
                "activities_by_priority": activities_by_priority,
                "pipeline_value": pipeline_value,
                "conversion": conversion,
            }
        ).data
        return Response(payload)
