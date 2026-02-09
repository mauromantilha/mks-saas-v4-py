from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from tenancy.models import BaseTenantModel


class Insurer(BaseTenantModel):
    """Tenant-scoped insurer registry.

    Secrets must NOT be stored in `integration_config`. Store only Secret Manager references.
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    class IntegrationType(models.TextChoices):
        NONE = "NONE", "None"
        API = "API", "API"
        MANUAL = "MANUAL", "Manual"
        BROKER_PORTAL = "BROKER_PORTAL", "Broker Portal"

    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    cnpj = models.CharField(max_length=18, blank=True)
    zip_code = models.CharField(max_length=12, blank=True)
    state = models.CharField(max_length=60, blank=True)
    city = models.CharField(max_length=120, blank=True)
    neighborhood = models.CharField(max_length=120, blank=True)
    street = models.CharField(max_length=255, blank=True)
    street_number = models.CharField(max_length=30, blank=True)
    address_complement = models.CharField(max_length=120, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    integration_type = models.CharField(
        max_length=20,
        choices=IntegrationType.choices,
        default=IntegrationType.NONE,
    )
    integration_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Integration config (store Secret Manager references, never raw secrets).",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "Insurer"
        verbose_name_plural = "Insurers"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "name"),
                name="uq_insurer_name_per_company",
            ),
        ]
        indexes = [
            models.Index(
                fields=("company", "status"),
                name="idx_insurer_company_status",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class InsurerContact(BaseTenantModel):
    insurer = models.ForeignKey(
        Insurer,
        related_name="contacts",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    role = models.CharField(max_length=120, blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-is_primary", "name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "insurer"),
                condition=models.Q(is_primary=True),
                name="uq_insurer_primary_contact_per_insurer",
            ),
        ]
        indexes = [
            models.Index(
                fields=("company", "insurer"),
                name="idx_insurer_contact_insurer",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - admin/debug helper
        primary = " (primary)" if self.is_primary else ""
        return f"{self.name}{primary}"

    def clean(self):
        super().clean()
        if self.insurer_id and self.insurer.company_id != self.company_id:
            raise ValidationError(
                "Insurer contact and Insurer must belong to the same company."
            )

    def save(self, *args, **kwargs):
        if self.insurer_id:
            self.company = self.insurer.company
        return super().save(*args, **kwargs)
