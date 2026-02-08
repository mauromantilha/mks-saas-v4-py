from django.contrib import admin

from operational.models import (
    Apolice,
    CommercialActivity,
    Customer,
    Endosso,
    Lead,
    Opportunity,
)


class TenantScopedAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return self.model.all_objects.all()


@admin.register(Customer)
class CustomerAdmin(TenantScopedAdmin):
    list_display = ("name", "email", "lifecycle_stage", "cnpj", "company", "created_at")
    search_fields = ("name", "email", "document", "cnpj", "legal_name", "trade_name")
    list_filter = ("company", "lifecycle_stage", "customer_type")


@admin.register(Lead)
class LeadAdmin(TenantScopedAdmin):
    list_display = ("id", "source", "company_name", "status", "qualification_score", "company")
    list_filter = ("status", "company")
    search_fields = ("source", "full_name", "company_name", "email", "cnpj")


@admin.register(Opportunity)
class OpportunityAdmin(TenantScopedAdmin):
    list_display = ("title", "customer", "stage", "amount", "closing_probability", "company")
    search_fields = ("title", "customer__name")
    list_filter = ("stage", "company")


@admin.register(Apolice)
class ApoliceAdmin(TenantScopedAdmin):
    list_display = ("numero", "cliente_nome", "status", "company", "inicio_vigencia")
    search_fields = ("numero", "cliente_nome", "cliente_cpf_cnpj")
    list_filter = ("status", "company")


@admin.register(Endosso)
class EndossoAdmin(TenantScopedAdmin):
    list_display = ("numero_endosso", "tipo", "apolice", "company", "data_emissao")
    list_filter = ("tipo", "company")


@admin.register(CommercialActivity)
class CommercialActivityAdmin(TenantScopedAdmin):
    list_display = (
        "id",
        "title",
        "kind",
        "channel",
        "status",
        "priority",
        "due_at",
        "company",
    )
    list_filter = ("kind", "channel", "status", "priority", "company")
    search_fields = ("title", "description", "lead__source", "opportunity__title")
