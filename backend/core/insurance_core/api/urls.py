from django.urls import include, path
from rest_framework.routers import DefaultRouter

from insurance_core.api.views.coverage import ProductCoverageViewSet
from insurance_core.api.views.insurer import InsurerViewSet
from insurance_core.api.views.product import InsuranceProductViewSet

router = DefaultRouter()
router.register(r"insurers", InsurerViewSet, basename="insurer")
router.register(r"products", InsuranceProductViewSet, basename="insurance-product")
router.register(r"coverages", ProductCoverageViewSet, basename="product-coverage")

urlpatterns = [
    path("", include(router.urls)),
]

