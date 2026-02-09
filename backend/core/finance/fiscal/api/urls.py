from django.urls import include, path
from rest_framework.routers import DefaultRouter

from finance.fiscal.api.views import FiscalDocumentViewSet
from finance.fiscal.api.views import TenantFiscalConfigUpsertAPIView

router = DefaultRouter()
router.register(r"fiscal", FiscalDocumentViewSet, basename="fiscal-document")

urlpatterns = [
    path("fiscal/config/", TenantFiscalConfigUpsertAPIView.as_view(), name="fiscal-config"),
    path("", include(router.urls)),
]
