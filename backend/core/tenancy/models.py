from django.core.exceptions import ValidationError
from django.db import models

from tenancy.context import get_current_company
from tenancy.managers import TenantManager


class BaseTenantModel(models.Model):
    company = models.ForeignKey(
        "customers.Company",
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_set",
    )
    ai_insights = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def _enforce_company_scope(self):
        current_company = get_current_company()

        if self.company_id is None and current_company is not None:
            self.company = current_company

        if self.company_id is None:
            raise ValidationError("company is required.")

        if current_company is not None and self.company_id != current_company.id:
            raise ValidationError(
                "Cross-tenant write blocked: resource company does not match request tenant."
            )

    def save(self, *args, **kwargs):
        self._enforce_company_scope()
        return super().save(*args, **kwargs)
