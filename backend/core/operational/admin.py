from django.contrib import admin

from operational.models import (
    Apolice,
    CommercialActivity,
    Customer,
    CustomerContact,
    Endosso,
    Lead,
    Opportunity,
    PolicyRequest,
    ProposalOption,
)


class TenantScopedAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return self.model.all_objects.all()


class CustomerContactInline(admin.TabularInline):
    model = CustomerContact
    extra = 0
    fields = ("name", "email", "phone", "role", "is_primary")
    ordering = ("-is_primary", "name", "id")

    def get_queryset(self, request):
        return self.model.all_objects.all()


@admin.register(Customer)
class CustomerAdmin(TenantScopedAdmin):
    list_display = ("name", "email", "lifecycle_stage", "cnpj", "company", "created_at")
    search_fields = ("name", "email", "document", "cnpj", "legal_name", "trade_name")
    list_filter = ("company", "lifecycle_stage", "customer_type")
    inlines = (CustomerContactInline,)


@admin.register(Lead)
class LeadAdmin(TenantScopedAdmin):
    list_display = ("id", "source", "company_name", "status", "qualification_score", "company")
    list_filter = ("status", "company")
    search_fields = ("source", "full_name", "company_name", "email", "cnpj")


@admin.register(Opportunity)
class OpportunityAdmin(TenantScopedAdmin):
    list_display = ("title", "customer", "stage", "product_line", "amount", "company")
    search_fields = ("title", "customer__name")
    list_filter = ("stage", "company")


@admin.register(PolicyRequest)
class PolicyRequestAdmin(TenantScopedAdmin):
    list_display = (
        "id",
        "opportunity",
        "customer",
        "status",
        "inspection_status",
        "issue_deadline_at",
        "company",
    )
    list_filter = ("status", "inspection_status", "product_line", "company")
    search_fields = ("customer__name", "opportunity__title", "bank_document")


@admin.register(ProposalOption)
class ProposalOptionAdmin(TenantScopedAdmin):
    list_display = (
        "id",
        "opportunity",
        "insurer_name",
        "plan_name",
        "is_recommended",
        "ranking_score",
        "company",
    )
    list_filter = ("is_recommended", "company")
    search_fields = ("insurer_name", "plan_name", "opportunity__title")


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
