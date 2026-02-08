from django.db import models

from tenancy.context import get_current_company


class TenantQuerySet(models.QuerySet):
    def for_company(self, company):
        return self.filter(company=company)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    def get_queryset(self):
        queryset = super().get_queryset()
        company = get_current_company()
        if company is None:
            return queryset.none()
        return queryset.filter(company=company)

    def unsafe_all(self):
        return super().get_queryset()
