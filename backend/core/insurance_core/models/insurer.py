from __future__ import annotations

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

