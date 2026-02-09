from __future__ import annotations

from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from tenancy.models import BaseTenantModel


class CommissionPlan(BaseTenantModel):
    """Commission plan definition (accrual rules), scoped per tenant."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    priority = models.PositiveIntegerField(
        default=100,
        help_text="Lower values win when multiple plans match.",
    )
    effective_from = models.DateField(default=timezone.localdate)
    effective_to = models.DateField(null=True, blank=True)
    rules_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Commission rules payload (JSONB on Postgres).",
    )

    class Meta:
        ordering = ("priority", "name", "id")
        verbose_name = "Commission Plan"
        verbose_name_plural = "Commission Plans"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "name"),
                name="uq_comm_plan_company_name",
            ),
            models.CheckConstraint(
                check=Q(effective_to__isnull=True) | Q(effective_to__gte=F("effective_from")),
                name="ck_comm_plan_eff_range",
            ),
        ]
        indexes = [
            models.Index(
                fields=("company", "status"),
                name="idx_comm_plan_company_status",
            ),
            models.Index(
                fields=("company", "effective_from"),
                name="idx_comm_plan_company_eff",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.name

