from django.urls import include, path
from rest_framework.routers import DefaultRouter

from insurance_core.api.views.coverage import ProductCoverageViewSet
from insurance_core.api.views.insurer import InsurerViewSet
from insurance_core.api.views.policy import (
    EndorsementViewSet,
    PolicyCoverageViewSet,
    PolicyDocumentRequirementViewSet,
    PolicyItemViewSet,
    PolicyViewSet,
)
from insurance_core.api.views.product import InsuranceProductViewSet

router = DefaultRouter()
router.register(r"insurers", InsurerViewSet, basename="insurer")
router.register(r"products", InsuranceProductViewSet, basename="insurance-product")
router.register(r"coverages", ProductCoverageViewSet, basename="product-coverage")
router.register(r"policies", PolicyViewSet, basename="policy")
router.register(r"policy-items", PolicyItemViewSet, basename="policy-item")
router.register(r"policy-coverages", PolicyCoverageViewSet, basename="policy-coverage")
router.register(
    r"policy-document-requirements",
    PolicyDocumentRequirementViewSet,
    basename="policy-document-requirement",
)
router.register(r"endorsements", EndorsementViewSet, basename="endorsement")

urlpatterns = [
    path("", include(router.urls)),
]
