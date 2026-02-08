from django.contrib import admin

from control_plane.models import TenantContract, TenantProvisioning


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
