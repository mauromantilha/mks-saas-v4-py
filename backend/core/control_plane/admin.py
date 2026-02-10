from django.contrib import admin

from control_plane.models import (
    AdminAuditEvent,
    FeatureFlag,
    ContractEmailLog,
    ControlPanelAuditLog,
    Plan,
    PlanPrice,
    SystemHealthSnapshot,
    Tenant,
    TenantContractDocument,
    TenantFeatureFlag,
    TenantHealthSnapshot,
    TenantImpersonationSession,
    TenantIntegrationSecretRef,
    TenantInternalNote,
    TenantAlertEvent,
    TenantContract,
    TenantOperationalSettings,
    TenantPlanSubscription,
    TenantProvisioning,
    TenantReleaseRecord,
    TenantStatusHistory,
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = (
        "legal_name",
        "contact_email",
        "cnpj",
        "slug",
        "subdomain",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("legal_name", "contact_email", "cnpj", "slug", "subdomain")


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "tier", "is_active", "updated_at")
    list_filter = ("tier", "is_active")
    search_fields = ("name",)


@admin.register(PlanPrice)
class PlanPriceAdmin(admin.ModelAdmin):
    list_display = ("plan", "monthly_price", "setup_fee", "updated_at")
    list_filter = ("monthly_price", "setup_fee")
    search_fields = ("plan__name",)


@admin.register(TenantPlanSubscription)
class TenantPlanSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "plan",
        "status",
        "is_trial",
        "trial_ends_at",
        "is_courtesy",
        "start_date",
        "end_date",
    )
    list_filter = ("status", "is_trial", "is_courtesy")
    search_fields = ("tenant__legal_name", "tenant__slug", "plan__name")


@admin.register(TenantStatusHistory)
class TenantStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("tenant", "from_status", "to_status", "actor", "created_at")
    list_filter = ("from_status", "to_status", "created_at")
    search_fields = ("tenant__legal_name", "tenant__slug", "reason")


@admin.register(ControlPanelAuditLog)
class ControlPanelAuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "resource", "tenant", "actor", "created_at")
    list_filter = ("action", "resource", "created_at")
    search_fields = ("tenant__legal_name", "tenant__slug", "actor__username")


@admin.register(AdminAuditEvent)
class AdminAuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "action",
        "entity_type",
        "entity_id",
        "target_tenant",
        "actor",
        "correlation_id",
        "created_at",
    )
    list_filter = ("action", "entity_type", "created_at")
    search_fields = ("entity_id", "correlation_id", "target_tenant__slug", "actor__username")


@admin.register(TenantInternalNote)
class TenantInternalNoteAdmin(admin.ModelAdmin):
    list_display = ("tenant", "created_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("tenant__slug", "tenant__legal_name", "note")


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("key", "name")


@admin.register(TenantFeatureFlag)
class TenantFeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("tenant", "feature", "enabled", "updated_by", "updated_at")
    list_filter = ("enabled", "feature")
    search_fields = ("tenant__slug", "feature__key")


@admin.register(TenantContractDocument)
class TenantContractDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "status", "contract_version", "created_at")
    list_filter = ("status",)
    search_fields = ("tenant__legal_name", "tenant__slug")


@admin.register(ContractEmailLog)
class ContractEmailLogAdmin(admin.ModelAdmin):
    list_display = ("id", "contract", "to_email", "status", "resend_message_id", "sent_at")
    list_filter = ("status",)
    search_fields = ("to_email", "resend_message_id", "contract__tenant__slug")


@admin.register(SystemHealthSnapshot)
class SystemHealthSnapshotAdmin(admin.ModelAdmin):
    list_display = ("service_name", "status", "latency_ms", "error_rate", "captured_at")
    list_filter = ("service_name", "status")
    search_fields = ("service_name",)


@admin.register(TenantHealthSnapshot)
class TenantHealthSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "last_seen_at",
        "request_rate",
        "error_rate",
        "p95_latency",
        "jobs_pending",
        "captured_at",
    )
    list_filter = ("tenant",)
    search_fields = ("tenant__legal_name", "tenant__slug")


@admin.register(TenantContract)
class TenantContractAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "plan",
        "status",
        "seats",
        "monthly_fee",
        "start_date",
        "end_date",
        "auto_renew",
    )
    list_filter = ("plan", "status", "auto_renew")
    search_fields = ("company__name", "company__tenant_code")


@admin.register(TenantProvisioning)
class TenantProvisioningAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "isolation_model",
        "status",
        "database_alias",
        "database_name",
        "database_host",
        "database_port",
        "provisioned_at",
    )
    list_filter = ("isolation_model", "status")
    search_fields = ("company__name", "company__tenant_code", "database_alias")


@admin.register(TenantOperationalSettings)
class TenantOperationalSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "requests_per_minute",
        "storage_limit_gb",
        "docs_storage_limit_gb",
        "updated_at",
    )
    search_fields = ("tenant__legal_name", "tenant__slug")


@admin.register(TenantIntegrationSecretRef)
class TenantIntegrationSecretRefAdmin(admin.ModelAdmin):
    list_display = ("tenant", "provider", "alias", "is_active", "updated_at")
    list_filter = ("provider", "is_active")
    search_fields = ("tenant__slug", "alias", "secret_manager_ref")


@admin.register(TenantImpersonationSession)
class TenantImpersonationSessionAdmin(admin.ModelAdmin):
    list_display = ("tenant", "actor", "status", "started_at", "expires_at", "ended_at")
    list_filter = ("status",)
    search_fields = ("tenant__slug", "actor__username", "correlation_id")


@admin.register(TenantAlertEvent)
class TenantAlertEventAdmin(admin.ModelAdmin):
    list_display = ("tenant", "alert_type", "severity", "status", "last_seen_at")
    list_filter = ("alert_type", "severity", "status")
    search_fields = ("tenant__slug", "message")


@admin.register(TenantReleaseRecord)
class TenantReleaseRecordAdmin(admin.ModelAdmin):
    list_display = ("tenant", "backend_version", "frontend_version", "is_current", "deployed_at")
    list_filter = ("is_current", "source")
    search_fields = ("tenant__slug", "backend_version", "frontend_version", "git_sha")
