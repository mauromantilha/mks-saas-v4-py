"""
URL configuration for mks_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from control_plane.views import (
    ControlPlaneTenantDetailAPIView,
    ControlPlaneTenantListCreateAPIView,
    ControlPlaneTenantProvisionAPIView,
)
from customers.views import (
    ActiveTenantUserAPIView,
    AuthenticatedUserAPIView,
    TenantCapabilitiesAPIView,
    TenantMemberDetailAPIView,
    TenantMembersAPIView,
    TenantRBACAPIView,
)
from operational.views import (
    ApoliceDetailAPIView,
    ApoliceListCreateAPIView,
    CommercialActivityCompleteAPIView,
    CommercialActivityDetailAPIView,
    CommercialActivityListCreateAPIView,
    CommercialActivityMarkRemindedAPIView,
    CommercialActivityRemindersAPIView,
    CommercialActivityReopenAPIView,
    CustomerDetailAPIView,
    CustomerListCreateAPIView,
    EndossoDetailAPIView,
    EndossoListCreateAPIView,
    LeadHistoryAPIView,
    LeadConvertAPIView,
    LeadDisqualifyAPIView,
    LeadQualifyAPIView,
    LeadDetailAPIView,
    LeadListCreateAPIView,
    OpportunityHistoryAPIView,
    OpportunityStageUpdateAPIView,
    OpportunityDetailAPIView,
    OpportunityListCreateAPIView,
    SalesMetricsAPIView,
)


def healthz(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthz, name="healthz"),
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
    path("api/auth/token/", obtain_auth_token, name="api-token-auth"),
    path("api/auth/me/", AuthenticatedUserAPIView.as_view(), name="auth-me"),
    path(
        "api/auth/tenant-me/",
        ActiveTenantUserAPIView.as_view(),
        name="auth-tenant-me",
    ),
    path(
        "api/auth/capabilities/",
        TenantCapabilitiesAPIView.as_view(),
        name="auth-capabilities",
    ),
    path(
        "api/auth/tenant-rbac/",
        TenantRBACAPIView.as_view(),
        name="auth-tenant-rbac",
    ),
    path(
        "api/auth/tenant-members/",
        TenantMembersAPIView.as_view(),
        name="auth-tenant-members",
    ),
    path(
        "api/auth/tenant-members/<int:membership_id>/",
        TenantMemberDetailAPIView.as_view(),
        name="auth-tenant-members-detail",
    ),
    path("api/customers/", CustomerListCreateAPIView.as_view(), name="customers-list"),
    path(
        "api/customers/<int:pk>/",
        CustomerDetailAPIView.as_view(),
        name="customers-detail",
    ),
    path("api/leads/", LeadListCreateAPIView.as_view(), name="leads-list"),
    path("api/leads/<int:pk>/", LeadDetailAPIView.as_view(), name="leads-detail"),
    path("api/leads/<int:pk>/qualify/", LeadQualifyAPIView.as_view(), name="leads-qualify"),
    path(
        "api/leads/<int:pk>/disqualify/",
        LeadDisqualifyAPIView.as_view(),
        name="leads-disqualify",
    ),
    path("api/leads/<int:pk>/convert/", LeadConvertAPIView.as_view(), name="leads-convert"),
    path("api/leads/<int:pk>/history/", LeadHistoryAPIView.as_view(), name="leads-history"),
    path(
        "api/opportunities/",
        OpportunityListCreateAPIView.as_view(),
        name="opportunities-list",
    ),
    path(
        "api/opportunities/<int:pk>/",
        OpportunityDetailAPIView.as_view(),
        name="opportunities-detail",
    ),
    path(
        "api/opportunities/<int:pk>/history/",
        OpportunityHistoryAPIView.as_view(),
        name="opportunities-history",
    ),
    path(
        "api/opportunities/<int:pk>/stage/",
        OpportunityStageUpdateAPIView.as_view(),
        name="opportunities-stage",
    ),
    path(
        "api/activities/",
        CommercialActivityListCreateAPIView.as_view(),
        name="activities-list",
    ),
    path(
        "api/activities/reminders/",
        CommercialActivityRemindersAPIView.as_view(),
        name="activities-reminders",
    ),
    path(
        "api/activities/<int:pk>/",
        CommercialActivityDetailAPIView.as_view(),
        name="activities-detail",
    ),
    path(
        "api/activities/<int:pk>/complete/",
        CommercialActivityCompleteAPIView.as_view(),
        name="activities-complete",
    ),
    path(
        "api/activities/<int:pk>/reopen/",
        CommercialActivityReopenAPIView.as_view(),
        name="activities-reopen",
    ),
    path(
        "api/activities/<int:pk>/mark-reminded/",
        CommercialActivityMarkRemindedAPIView.as_view(),
        name="activities-mark-reminded",
    ),
    path("api/sales/metrics/", SalesMetricsAPIView.as_view(), name="sales-metrics"),
    path("api/apolices/", ApoliceListCreateAPIView.as_view(), name="apolices-list"),
    path(
        "api/apolices/<int:pk>/",
        ApoliceDetailAPIView.as_view(),
        name="apolices-detail",
    ),
    path("api/endossos/", EndossoListCreateAPIView.as_view(), name="endossos-list"),
    path(
        "api/endossos/<int:pk>/",
        EndossoDetailAPIView.as_view(),
        name="endossos-detail",
    ),
]
