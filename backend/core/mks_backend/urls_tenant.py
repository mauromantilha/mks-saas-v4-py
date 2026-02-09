from django.http import JsonResponse
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token

from customers.views import (
    ActiveTenantUserAPIView,
    AuthenticatedUserAPIView,
    PasswordResetConfirmAPIView,
    PasswordResetRequestAPIView,
    TenantCapabilitiesAPIView,
    TenantMemberDetailAPIView,
    TenantMembersAPIView,
    TenantRBACAPIView,
)
from ledger.views import TenantLedgerEntryListAPIView
from operational.views import (
    ApoliceAIInsightsAPIView,
    ApoliceDetailAPIView,
    ApoliceListCreateAPIView,
    CepLookupAPIView,
    CommercialActivityAIInsightsAPIView,
    CommercialActivityCompleteAPIView,
    CommercialActivityDetailAPIView,
    CommercialActivityListCreateAPIView,
    CommercialActivityMarkRemindedAPIView,
    CommercialActivityRemindersAPIView,
    CommercialActivityReopenAPIView,
    CustomerAIInsightsAPIView,
    CustomerCNPJEnrichmentAPIView,
    CustomerDetailAPIView,
    CustomerListCreateAPIView,
    EndossoAIInsightsAPIView,
    EndossoDetailAPIView,
    EndossoListCreateAPIView,
    LeadAIInsightsAPIView,
    LeadCNPJEnrichmentAPIView,
    LeadConvertAPIView,
    LeadDetailAPIView,
    LeadDisqualifyAPIView,
    LeadHistoryAPIView,
    LeadListCreateAPIView,
    LeadQualifyAPIView,
    OpportunityAIInsightsAPIView,
    OpportunityDetailAPIView,
    OpportunityHistoryAPIView,
    OpportunityListCreateAPIView,
    OpportunityStageUpdateAPIView,
    PolicyRequestAIInsightsAPIView,
    PolicyRequestDetailAPIView,
    PolicyRequestListCreateAPIView,
    ProposalOptionAIInsightsAPIView,
    ProposalOptionDetailAPIView,
    ProposalOptionListCreateAPIView,
    SalesGoalDetailAPIView,
    SalesGoalListCreateAPIView,
    SalesMetricsAPIView,
    TenantDashboardSummaryAPIView,
)


def healthz(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    # Auth endpoints (shared tables in public schema).
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
    # Tenant context/auth helpers.
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
    # Immutable tenant ledger.
    path("api/ledger/", TenantLedgerEntryListAPIView.as_view(), name="tenant-ledger-list"),
    # CRM entities (tenant schema).
    path("api/customers/", CustomerListCreateAPIView.as_view(), name="customers-list"),
    path(
        "api/customers/<int:pk>/",
        CustomerDetailAPIView.as_view(),
        name="customers-detail",
    ),
    path(
        "api/customers/<int:pk>/ai-insights/",
        CustomerAIInsightsAPIView.as_view(),
        name="customers-ai-insights",
    ),
    path(
        "api/customers/<int:pk>/ai-enrich-cnpj/",
        CustomerCNPJEnrichmentAPIView.as_view(),
        name="customers-ai-enrich-cnpj",
    ),
    path(
        "api/utils/cep/<str:cep>/",
        CepLookupAPIView.as_view(),
        name="utils-cep-lookup",
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
        "api/leads/<int:pk>/ai-insights/",
        LeadAIInsightsAPIView.as_view(),
        name="leads-ai-insights",
    ),
    path(
        "api/leads/<int:pk>/ai-enrich-cnpj/",
        LeadCNPJEnrichmentAPIView.as_view(),
        name="leads-ai-enrich-cnpj",
    ),
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
        "api/opportunities/<int:pk>/ai-insights/",
        OpportunityAIInsightsAPIView.as_view(),
        name="opportunities-ai-insights",
    ),
    path(
        "api/opportunities/<int:pk>/stage/",
        OpportunityStageUpdateAPIView.as_view(),
        name="opportunities-stage",
    ),
    path(
        "api/dashboard/summary/",
        TenantDashboardSummaryAPIView.as_view(),
        name="tenant-dashboard-summary",
    ),
    path("api/sales-goals/", SalesGoalListCreateAPIView.as_view(), name="sales-goals-list"),
    path(
        "api/sales-goals/<int:pk>/",
        SalesGoalDetailAPIView.as_view(),
        name="sales-goals-detail",
    ),
    path(
        "api/proposal-options/",
        ProposalOptionListCreateAPIView.as_view(),
        name="proposal-options-list",
    ),
    path(
        "api/proposal-options/<int:pk>/",
        ProposalOptionDetailAPIView.as_view(),
        name="proposal-options-detail",
    ),
    path(
        "api/proposal-options/<int:pk>/ai-insights/",
        ProposalOptionAIInsightsAPIView.as_view(),
        name="proposal-options-ai-insights",
    ),
    path(
        "api/policy-requests/",
        PolicyRequestListCreateAPIView.as_view(),
        name="policy-requests-list",
    ),
    path(
        "api/policy-requests/<int:pk>/",
        PolicyRequestDetailAPIView.as_view(),
        name="policy-requests-detail",
    ),
    path(
        "api/policy-requests/<int:pk>/ai-insights/",
        PolicyRequestAIInsightsAPIView.as_view(),
        name="policy-requests-ai-insights",
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
    path(
        "api/activities/<int:pk>/ai-insights/",
        CommercialActivityAIInsightsAPIView.as_view(),
        name="activities-ai-insights",
    ),
    path("api/sales/metrics/", SalesMetricsAPIView.as_view(), name="sales-metrics"),
    path("api/apolices/", ApoliceListCreateAPIView.as_view(), name="apolices-list"),
    path(
        "api/apolices/<int:pk>/",
        ApoliceDetailAPIView.as_view(),
        name="apolices-detail",
    ),
    path(
        "api/apolices/<int:pk>/ai-insights/",
        ApoliceAIInsightsAPIView.as_view(),
        name="apolices-ai-insights",
    ),
    path("api/endossos/", EndossoListCreateAPIView.as_view(), name="endossos-list"),
    path(
        "api/endossos/<int:pk>/",
        EndossoDetailAPIView.as_view(),
        name="endossos-detail",
    ),
    path(
        "api/endossos/<int:pk>/ai-insights/",
        EndossoAIInsightsAPIView.as_view(),
        name="endossos-ai-insights",
    ),
    # Insurance core (bounded context): insurers, products, coverages
    path("api/insurance/", include("insurance_core.api.urls")),
    # Finance fiscal (bounded context): NF issuance/cancellation (tenant-scoped)
    path("api/finance/", include("finance.fiscal.api.urls")),
]
