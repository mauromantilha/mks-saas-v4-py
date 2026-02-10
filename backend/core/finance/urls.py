from django.urls import path
from finance.api.views import ReceivableInvoiceListAPIView

urlpatterns = [
    path(
        "invoices/",
        ReceivableInvoiceListAPIView.as_view(),
        name="receivable-invoices-list",
    ),
]