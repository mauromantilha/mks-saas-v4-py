from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from commission.models.scope import CommissionPlanScope
from tenancy.models import BaseTenantModel


class CommissionSplit(BaseTenantModel):
    """How commission is split among recipients for a given scope."""

    class RecipientType(models.TextChoices):
        USER = "USER", "User"
        ROLE = "ROLE", "Role"
        EXTERNAL = "EXTERNAL", "External"

    scope = models.ForeignKey(
        CommissionPlanScope,
        related_name="splits",
        on_delete=models.CASCADE,
    )
    recipient_type = models.CharField(
        max_length=20,
        choices=RecipientType.choices,
        db_index=True,
    )
    recipient_ref = models.CharField(
        max_length=255,
        help_text="Opaque recipient reference (e.g. user_id, role code, external id).",
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
    )
    priority = models.PositiveIntegerField(
        default=100,
        help_text="Lower values win when multiple splits match within a scope.",
    )
    effective_from = models.DateField(default=timezone.localdate)
    effective_to = models.DateField(null=True, blank=True)
    rules_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optional split-specific rules/metadata.",
    )

    class Meta:
        ordering = ("priority", "recipient_type", "recipient_ref", "id")
        verbose_name = "Commission Split"
        verbose_name_plural = "Commission Splits"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "scope", "recipient_type", "recipient_ref", "effective_from"),
                name="uq_comm_split_key",
            ),
            models.CheckConstraint(
                check=Q(effective_to__isnull=True) | Q(effective_to__gte=F("effective_from")),
                name="ck_comm_split_eff_range",
            ),
        ]
        indexes = [
            models.Index(
                fields=("company", "scope"),
                name="idx_comm_split_company_scope",
            ),
            models.Index(
                fields=("company", "recipient_type", "recipient_ref"),
                name="idx_comm_split_recipient",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.recipient_type}:{self.recipient_ref} {self.percentage}%"

    def clean(self):
        super().clean()
        if self.scope_id and self.company_id and self.scope.company_id != self.company_id:
            raise ValidationError("CommissionSplit and CommissionPlanScope must belong to the same company.")

    def save(self, *args, **kwargs):
        if self.scope_id:
            self.company = self.scope.company
        return super().save(*args, **kwargs)

