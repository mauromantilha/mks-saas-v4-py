from rest_framework import generics
from finance.models import ReceivableInvoice
from finance.api.serializers import ReceivableInvoiceSerializer
from operational.views import TenantScopedAPIViewMixin


class ReceivableInvoiceListAPIView(TenantScopedAPIViewMixin, generics.ListAPIView):
    model = ReceivableInvoice
    serializer_class = ReceivableInvoiceSerializer
    tenant_resource_key = "invoices"
    ordering = ("-issue_date",)

    def get_queryset(self):
        qs = super().get_queryset().select_related("payer", "policy").prefetch_related("installments")
        payer_id = self.request.query_params.get("payer_id")
        if payer_id:
            qs = qs.filter(payer_id=payer_id)
        return qs