from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.models import Payable, ReceivableInstallment, ReceivableInvoice
from finance.serializers import (
    PayableSerializer,
    ReceivableInstallmentSerializer,
    ReceivableInstallmentSettleSerializer,
    ReceivableInvoiceSerializer,
)
from finance.services import settle_receivable_installment
from operational.views import TenantScopedAPIViewMixin
from tenancy.permissions import IsTenantRoleAllowed


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


class PayableListCreateAPIView(TenantScopedAPIViewMixin, generics.ListCreateAPIView):
    model = Payable
    serializer_class = PayableSerializer
    tenant_resource_key = "payables"
    ordering = ("due_date", "id")

    def get_queryset(self):
        queryset = super().get_queryset().select_related("recipient")

        status_filter = (self.request.query_params.get("status") or "").strip().upper()
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        recipient_id = self.request.query_params.get("recipient_id")
        if recipient_id:
            queryset = queryset.filter(recipient_id=recipient_id)

        due_date_from = self.request.query_params.get("due_date_from")
        if due_date_from:
            queryset = queryset.filter(due_date__gte=due_date_from)

        due_date_to = self.request.query_params.get("due_date_to")
        if due_date_to:
            queryset = queryset.filter(due_date__lte=due_date_to)

        search = (self.request.query_params.get("q") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(beneficiary_name__icontains=search)
                | Q(description__icontains=search)
                | Q(source_ref__icontains=search)
                | Q(recipient__username__icontains=search)
            )

        return queryset


class PayableDetailAPIView(TenantScopedAPIViewMixin, generics.RetrieveUpdateAPIView):
    model = Payable
    serializer_class = PayableSerializer
    tenant_resource_key = "payables"


class ReceivableInvoiceListAPIView(TenantScopedAPIViewMixin, generics.ListAPIView):
    model = ReceivableInvoice
    serializer_class = ReceivableInvoiceSerializer
    tenant_resource_key = "invoices"
    ordering = ("-issue_date",)

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            "payer", "policy", "policy__insurer"
        ).prefetch_related("installments")
        payer_id = self.request.query_params.get("payer_id")
        if payer_id:
            qs = qs.filter(payer_id=payer_id)

        policy_id = self.request.query_params.get("policy_id")
        if policy_id:
            qs = qs.filter(policy_id=policy_id)

        insurer_id = self.request.query_params.get("insurer_id")
        if insurer_id:
            qs = qs.filter(policy__insurer_id=insurer_id)

        status_filter = (self.request.query_params.get("status") or "").strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)

        if _is_truthy(self.request.query_params.get("delinquent_only")):
            qs = qs.filter(
                installments__status=ReceivableInstallment.STATUS_OPEN,
                installments__due_date__lt=timezone.localdate(),
            ).distinct()

        return qs


class ReceivableInstallmentListAPIView(TenantScopedAPIViewMixin, generics.ListAPIView):
    model = ReceivableInstallment
    serializer_class = ReceivableInstallmentSerializer
    tenant_resource_key = "installments"
    ordering = ("due_date", "number")

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "invoice",
            "invoice__payer",
            "invoice__policy",
            "invoice__policy__insurer",
        )

        invoice_id = self.request.query_params.get("invoice_id")
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)

        payer_id = self.request.query_params.get("payer_id")
        if payer_id:
            queryset = queryset.filter(invoice__payer_id=payer_id)

        policy_id = self.request.query_params.get("policy_id")
        if policy_id:
            queryset = queryset.filter(invoice__policy_id=policy_id)

        insurer_id = self.request.query_params.get("insurer_id")
        if insurer_id:
            queryset = queryset.filter(invoice__policy__insurer_id=insurer_id)

        status_filter = (self.request.query_params.get("status") or "").strip().upper()
        if status_filter and status_filter != "DELINQUENT":
            queryset = queryset.filter(status=status_filter)

        delinquent = _is_truthy(self.request.query_params.get("delinquent_only"))
        if status_filter == "DELINQUENT":
            delinquent = True
            queryset = queryset.filter(status=ReceivableInstallment.STATUS_OPEN)

        if delinquent:
            queryset = queryset.filter(
                status=ReceivableInstallment.STATUS_OPEN,
                due_date__lt=timezone.localdate(),
            )

        return queryset


class ReceivableInstallmentSettleAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "installments"

    def post(self, request, pk: int):
        serializer = ReceivableInstallmentSettleSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        installment = get_object_or_404(
            ReceivableInstallment.all_objects.select_related("invoice"),
            id=pk,
            company=request.company,
        )

        try:
            settle_receivable_installment(
                company=request.company,
                installment=installment,
                actor=request.user,
                request=request,
            )
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        refreshed = (
            ReceivableInstallment.all_objects.select_related(
                "invoice",
                "invoice__payer",
                "invoice__policy",
                "invoice__policy__insurer",
            )
            .filter(id=installment.id, company=request.company)
            .first()
        )
        return Response(
            ReceivableInstallmentSerializer(refreshed).data,
            status=status.HTTP_200_OK,
        )


class PolicyFinanceSummaryAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "policies"

    def get(self, request):
        raw_policy_ids = (request.query_params.get("policy_ids") or "").strip()
        policy_ids = []
        if raw_policy_ids:
            for token in raw_policy_ids.split(","):
                token = token.strip()
                if not token:
                    continue
                try:
                    policy_ids.append(int(token))
                except ValueError:
                    continue

        queryset = ReceivableInstallment.all_objects.filter(
            company=request.company,
            invoice__policy_id__isnull=False,
        ).select_related("invoice", "invoice__policy", "invoice__policy__insurer")

        if policy_ids:
            queryset = queryset.filter(invoice__policy_id__in=policy_ids)

        today = timezone.localdate()
        summary_map: dict[int, dict] = {}

        def _money(total: Decimal, value) -> Decimal:
            return total + (value or Decimal("0.00"))

        for installment in queryset:
            policy_id = installment.invoice.policy_id
            if policy_id is None:
                continue

            policy = installment.invoice.policy
            item = summary_map.setdefault(
                policy_id,
                {
                    "policy_id": policy_id,
                    "policy_number": policy.policy_number,
                    "insurer_id": policy.insurer_id,
                    "insurer_name": getattr(policy.insurer, "name", ""),
                    "open_installments": 0,
                    "paid_installments": 0,
                    "cancelled_installments": 0,
                    "overdue_installments": 0,
                    "open_amount": Decimal("0.00"),
                    "paid_amount": Decimal("0.00"),
                    "cancelled_amount": Decimal("0.00"),
                    "overdue_amount": Decimal("0.00"),
                },
            )

            if installment.status == ReceivableInstallment.STATUS_OPEN:
                item["open_installments"] += 1
                item["open_amount"] = _money(item["open_amount"], installment.amount)
                if installment.due_date < today:
                    item["overdue_installments"] += 1
                    item["overdue_amount"] = _money(item["overdue_amount"], installment.amount)
            elif installment.status == ReceivableInstallment.STATUS_PAID:
                item["paid_installments"] += 1
                item["paid_amount"] = _money(item["paid_amount"], installment.amount)
            elif installment.status == ReceivableInstallment.STATUS_CANCELLED:
                item["cancelled_installments"] += 1
                item["cancelled_amount"] = _money(item["cancelled_amount"], installment.amount)

        results = list(summary_map.values())
        for row in results:
            row["open_amount"] = str(row["open_amount"])
            row["paid_amount"] = str(row["paid_amount"])
            row["cancelled_amount"] = str(row["cancelled_amount"])
            row["overdue_amount"] = str(row["overdue_amount"])

        results.sort(key=lambda row: row["policy_id"])
        return Response(results, status=status.HTTP_200_OK)
