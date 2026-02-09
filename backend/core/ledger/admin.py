from django.contrib import admin

from ledger.models import LedgerEntry


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "scope",
        "chain_id",
        "action",
        "event_type",
        "resource_label",
        "resource_pk",
        "occurred_at",
        "actor_username",
        "ip_address",
    )
    list_filter = ("scope", "action")
    search_fields = ("event_type", "resource_label", "resource_pk", "actor_username", "chain_id")
    ordering = ("-occurred_at", "-id")
    readonly_fields = [field.name for field in LedgerEntry._meta.fields]

    def get_queryset(self, request):
        # Default manager is tenant-scoped; admin must see all entries.
        return LedgerEntry.all_objects.all()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
