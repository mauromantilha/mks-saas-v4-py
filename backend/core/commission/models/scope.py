from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from commission.models.plan import CommissionPlan
from tenancy.models import BaseTenantModel


class CommissionPlanScope(BaseTenantModel):
    """A plan can have multiple scopes (match criteria / segmentation)."""

    class Dimension(models.TextChoices):
        ANY = "ANY", "Any"
        LINE_OF_BUSINESS = "LINE_OF_BUSINESS", "Line of Business"
        INSURER = "INSURER", "Insurer"
        PRODUCT = "PRODUCT", "Product"
        SALES_CHANNEL = "SALES_CHANNEL", "Sales Channel"
        CUSTOM = "CUSTOM", "Custom"

    plan = models.ForeignKey(
        CommissionPlan,
        related_name="scopes",
        on_delete=models.CASCADE,
    )
    dimension = models.CharField(
        max_length=40,
        choices=Dimension.choices,
        default=Dimension.ANY,
        db_index=True,
    )
    value = models.CharField(
        max_length=255,
        blank=True,
        help_text="Scope value for the selected dimension. Empty means 'ANY'.",
    )
    priority = models.PositiveIntegerField(
        default=100,
        help_text="Lower values win when multiple scopes match within a plan.",
    )
    effective_from = models.DateField(default=timezone.localdate)
    effective_to = models.DateField(null=True, blank=True)
    rules_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optional overrides for the plan rules when this scope matches.",
    )

    class Meta:
        ordering = ("priority", "dimension", "value", "id")
        verbose_name = "Commission Plan Scope"
        verbose_name_plural = "Commission Plan Scopes"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "plan", "dimension", "value", "effective_from"),
                name="uq_comm_scope_key",
            ),
            models.CheckConstraint(
                check=Q(effective_to__isnull=True) | Q(effective_to__gte=F("effective_from")),
                name="ck_comm_scope_eff_range",
            ),
        ]
        indexes = [
            models.Index(
                fields=("company", "plan"),
                name="idx_comm_scope_company_plan",
            ),
            models.Index(
                fields=("company", "dimension"),
                name="idx_comm_scope_company_dim",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.plan.name} [{self.dimension}={self.value or '*'}]"

    def clean(self):
        super().clean()
        if self.plan_id and self.company_id and self.plan.company_id != self.company_id:
            raise ValidationError("CommissionPlanScope and CommissionPlan must belong to the same company.")

    def save(self, *args, **kwargs):
        if self.plan_id:
            self.company = self.plan.company
        return super().save(*args, **kwargs)

