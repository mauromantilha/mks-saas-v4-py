from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from operational.models import (
    Apolice,
    CommercialActivity,
    Customer,
    Endosso,
    Lead,
    Opportunity,
)
from operational.serializers import (
    ApoliceSerializer,
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
        customer = lead.customer or requested_customer
        if customer is None:
            return Response(
                {"detail": "Customer is required to convert this lead."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if lead.customer_id and requested_customer and requested_customer.id != lead.customer_id:
            return Response(
                {"detail": "Lead already linked to another customer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        title = serializer.validated_data.get("title", "").strip()
        if not title:
            title = f"Opportunity from lead #{lead.id}"

        with transaction.atomic():
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


class SalesMetricsAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "metrics"

    def get(self, request):
        lead_counts = {
            row["status"]: row["total"]
            for row in Lead.objects.values("status")
            .annotate(total=Count("id"))
            .order_by()
        }
        opportunity_counts = {
            row["stage"]: row["total"]
            for row in Opportunity.objects.values("stage")
            .annotate(total=Count("id"))
            .order_by()
        }

        now = timezone.now()
        activities_qs = CommercialActivity.objects.filter(
            status=CommercialActivity.STATUS_PENDING
        )
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

        payload = SalesMetricsSerializer(
            {
                "tenant_code": request.company.tenant_code,
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
                "conversion": conversion,
            }
        ).data
        return Response(payload)
