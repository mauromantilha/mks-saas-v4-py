from django.urls import include, path
from rest_framework.routers import DefaultRouter

from control_plane.views import ControlPanelCepLookupAPIView
from control_plane.viewsets import (
    ControlPanelContractViewSet,
    ControlPanelFeatureFlagViewSet,
    ControlPanelMonitoringViewSet,
    ControlPanelPlanViewSet,
    ControlPanelTenantViewSet,
)

router = DefaultRouter()
router.register(r"tenants", ControlPanelTenantViewSet, basename="control-panel-tenants")
router.register(r"plans", ControlPanelPlanViewSet, basename="control-panel-plans")
router.register(r"contracts", ControlPanelContractViewSet, basename="control-panel-contracts")
router.register(r"monitoring", ControlPanelMonitoringViewSet, basename="control-panel-monitoring")
router.register(r"features", ControlPanelFeatureFlagViewSet, basename="control-panel-features")

urlpatterns = [
    path("utils/cep/<str:cep>/", ControlPanelCepLookupAPIView.as_view(), name="control-panel-cep"),
    path("", include(router.urls)),
]
