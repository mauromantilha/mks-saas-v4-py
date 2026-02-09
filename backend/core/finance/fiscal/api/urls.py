from django.urls import include, path
from rest_framework.routers import DefaultRouter

from finance.fiscal.api.views import FiscalDocumentViewSet

router = DefaultRouter()
router.register(r"fiscal", FiscalDocumentViewSet, basename="fiscal-document")

urlpatterns = [
    path("", include(router.urls)),
]

