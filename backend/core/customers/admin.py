from django.contrib import admin

from customers.models import (
    Company,
    CompanyMembership,
    Domain,
    ProducerProfile,
    TenantEmailConfig,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "tenant_code",
        "subdomain",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "tenant_code", "subdomain")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "tenant_code",
                    "subdomain",
                    "is_active",
                )
            },
        ),
        (
            "RBAC",
            {
                "fields": ("rbac_overrides",),
                "description": (
                    "JSON overrides per resource/method. "
                    "Example: {'apolices': {'POST': ['OWNER', 'MANAGER']}}"
                ),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )


@admin.register(CompanyMembership)
class CompanyMembershipAdmin(admin.ModelAdmin):
    list_display = ("company", "user", "role", "is_active", "created_at")
    list_filter = ("role", "is_active", "company")
    search_fields = ("company__name", "user__username", "user__email")


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "tenant", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("domain", "tenant__tenant_code", "tenant__subdomain")


@admin.register(ProducerProfile)
class ProducerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "company",
        "team_name",
        "is_team_manager",
        "commission_transfer_percent",
        "is_active",
    )
    list_filter = ("company", "is_active", "is_team_manager", "team_name")
    search_fields = ("full_name", "cpf", "membership__user__username", "team_name")


@admin.register(TenantEmailConfig)
class TenantEmailConfigAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "smtp_host",
        "smtp_port",
        "smtp_use_tls",
        "smtp_use_ssl",
        "is_enabled",
        "last_tested_at",
        "last_test_status",
    )
    list_filter = ("is_enabled", "smtp_use_tls", "smtp_use_ssl", "last_test_status")
    search_fields = ("company__name", "company__tenant_code", "smtp_host", "smtp_username")
