from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from insurance_core.models.policy import Policy
from tenancy.models import BaseTenantModel


class Endorsement(BaseTenantModel):
    """Endorsement structure (base) attached to a policy.

    Endorsements will be expanded in future iterations (diffs, billing, etc.).
    """

    class Type(models.TextChoices):
        COVERAGE_CHANGE = "COVERAGE_CHANGE", "Coverage change"
        INSURED_OBJECT_CHANGE = "INSURED_OBJECT_CHANGE", "Insured object change"
        FINANCIAL_CHANGE = "FINANCIAL_CHANGE", "Financial change"
        CANCELLATION_LIKE = "CANCELLATION_LIKE", "Cancellation-like"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ISSUED = "ISSUED", "Issued"
        APPLIED = "APPLIED", "Applied"
        CANCELLED = "CANCELLED", "Cancelled"

    policy = models.ForeignKey(
        Policy,
        related_name="endorsements",
        on_delete=models.CASCADE,
    )
    endorsement_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Endorsement number assigned by the insurer (nullable until issued).",
    )
    type = models.CharField(max_length=30, choices=Type.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    effective_date = models.DateField()
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-effective_date", "-id")
        verbose_name = "Endorsement"
        verbose_name_plural = "Endorsements"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "policy", "endorsement_number"),
                name="uq_endorsement_number_per_policy_company",
                condition=(~models.Q(endorsement_number__isnull=True) & ~models.Q(endorsement_number="")),
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        label = self.endorsement_number or f"Endorsement #{self.pk}"
        return f"{label} ({self.type})"

    def clean(self):
        super().clean()
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Endorsement and Policy must belong to the same company.")

    def save(self, *args, **kwargs):
        if self.policy_id:
            self.company = self.policy.company
        if self.endorsement_number == "":
            self.endorsement_number = None
        return super().save(*args, **kwargs)

