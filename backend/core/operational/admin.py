from django.contrib import admin

from operational.models import Apolice, Customer, Endosso, Lead, Opportunity


class TenantScopedAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return self.model.all_objects.all()


@admin.register(Customer)
class CustomerAdmin(TenantScopedAdmin):
    list_display = ("name", "email", "company", "created_at")
    search_fields = ("name", "email", "document")
    list_filter = ("company",)


@admin.register(Lead)
class LeadAdmin(TenantScopedAdmin):
    list_display = ("id", "source", "status", "company", "created_at")
    list_filter = ("status", "company")


@admin.register(Opportunity)
class OpportunityAdmin(TenantScopedAdmin):
    list_display = ("title", "customer", "stage", "amount", "company", "created_at")
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
