from django.contrib import admin

from customers.models import Company, CompanyMembership


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
