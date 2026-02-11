from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token

from control_plane.views import (
    ControlPlaneTenantDetailAPIView,
    ControlPlaneTenantListCreateAPIView,
    ControlPlaneTenantProvisionExecuteAPIView,
    ControlPlaneTenantProvisionAPIView,
    MonitoringHeartbeatAPIView,
)
from customers.views import (
    AuthenticatedUserAPIView,
    PasswordResetConfirmAPIView,
    PasswordResetRequestAPIView,
)


def healthz(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthz, name="healthz"),
    path("monitoring/heartbeat/", MonitoringHeartbeatAPIView.as_view(), name="monitoring-heartbeat"),
    # Control plane APIs (public schema only).
    path(
        "platform/api/tenants/",
        ControlPlaneTenantListCreateAPIView.as_view(),
        name="platform-tenants-list",
    ),
    path(
        "platform/api/tenants/<int:company_id>/",
        ControlPlaneTenantDetailAPIView.as_view(),
        name="platform-tenants-detail",
    ),
    path(
        "platform/api/tenants/<int:company_id>/provision/",
        ControlPlaneTenantProvisionAPIView.as_view(),
        name="platform-tenants-provision",
    ),
    path(
        "platform/api/tenants/<int:company_id>/provision/execute/",
        ControlPlaneTenantProvisionExecuteAPIView.as_view(),
        name="platform-tenants-provision-execute",
    ),
    path("control-panel/", include("control_plane.urls")),
    # Frontend reverse-proxy routes API traffic through /api/* in production.
    path("api/control-panel/", include("control_plane.urls")),
    # Auth endpoints (shared auth/public schema).
    path("api/auth/token/", obtain_auth_token, name="api-token-auth"),
    path("api/auth/me/", AuthenticatedUserAPIView.as_view(), name="auth-me"),
    path(
        "api/auth/password-reset/request/",
        PasswordResetRequestAPIView.as_view(),
        name="auth-password-reset-request",
    ),
    path(
        "api/auth/password-reset/confirm/",
        PasswordResetConfirmAPIView.as_view(),
        name="auth-password-reset-confirm",
    ),
]
