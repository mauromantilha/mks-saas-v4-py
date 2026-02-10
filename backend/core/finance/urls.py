from django.urls import include, path

from finance.views import (
    PayableDetailAPIView,
    PayableListCreateAPIView,
    PolicyFinanceSummaryAPIView,
    ReceivableInstallmentListAPIView,
    ReceivableInstallmentSettleAPIView,
    ReceivableInvoiceListAPIView,
)

urlpatterns = [
    path(
        "payables/",
        PayableListCreateAPIView.as_view(),
        name="payables-list",
    ),
    path(
        "payables/<int:pk>/",
        PayableDetailAPIView.as_view(),
        name="payables-detail",
    ),
    path(
        "invoices/",
        ReceivableInvoiceListAPIView.as_view(),
        name="receivable-invoices-list",
    ),
    path(
        "installments/",
        ReceivableInstallmentListAPIView.as_view(),
        name="receivable-installments-list",
    ),
    path(
        "installments/<int:pk>/settle/",
        ReceivableInstallmentSettleAPIView.as_view(),
        name="receivable-installments-settle",
    ),
    path(
        "policies/summary/",
        PolicyFinanceSummaryAPIView.as_view(),
        name="policy-finance-summary",
    ),
    path("", include("finance.fiscal.api.urls")),
]
