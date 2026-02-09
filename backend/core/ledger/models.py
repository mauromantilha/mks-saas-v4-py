from __future__ import annotations

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from tenancy.context import get_current_company
from tenancy.managers import TenantManager


class LedgerEntry(models.Model):
    """Append-only (immutable) ledger entry.

    This is an application-level immutable ledger. It is *tamper-evident* by using a
    hash chain per "chain_id" (tenant chain or platform chain). It is not a DB-level
    WORM store: DB superusers can still mutate rows; this ledger is designed for
    strong guarantees at the application boundary and for detecting tampering.
    """

    SCOPE_TENANT = "TENANT"
    SCOPE_PLATFORM = "PLATFORM"
    SCOPE_CHOICES = [
        (SCOPE_TENANT, "Tenant"),
        (SCOPE_PLATFORM, "Platform"),
    ]

    ACTION_CREATE = "CREATE"
    ACTION_UPDATE = "UPDATE"
    ACTION_DELETE = "DELETE"
    ACTION_SYSTEM = "SYSTEM"
    ACTION_CHOICES = [
        (ACTION_CREATE, "Create"),
        (ACTION_UPDATE, "Update"),
        (ACTION_DELETE, "Delete"),
        (ACTION_SYSTEM, "System"),
    ]

    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default=SCOPE_TENANT)
    company = models.ForeignKey(
        "customers.Company",
        on_delete=models.PROTECT,
        related_name="ledger_entries",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
        null=True,
        blank=True,
    )
    actor_username = models.CharField(max_length=150, blank=True)
    actor_email = models.EmailField(blank=True)

    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        default=ACTION_SYSTEM,
    )
    event_type = models.CharField(max_length=120, blank=True)
    resource_label = models.CharField(max_length=200)
    resource_pk = models.CharField(max_length=64, blank=True)

    occurred_at = models.DateTimeField(default=timezone.now)
    request_id = models.UUIDField(null=True, blank=True)
    request_method = models.CharField(max_length=12, blank=True)
    request_path = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Hash chain fields (per chain_id).
    chain_id = models.CharField(max_length=80, db_index=True)
    prev_hash = models.CharField(max_length=64, blank=True, default="")
    entry_hash = models.CharField(max_length=64, unique=True)

    data_before = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    data_after = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    metadata = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)

    # Default manager is tenant-scoped to prevent accidental cross-tenant reads.
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("-occurred_at", "-id")
        constraints = [
            models.CheckConstraint(
                check=models.Q(scope="TENANT", company__isnull=False)
                | models.Q(scope="PLATFORM", company__isnull=True),
                name="ck_ledger_scope_company",
            ),
            models.UniqueConstraint(
                fields=("chain_id", "prev_hash"),
                name="uq_ledger_prev_hash_per_chain",
            ),
            models.UniqueConstraint(
                fields=("chain_id", "entry_hash"),
                name="uq_ledger_entry_hash_per_chain",
            ),
        ]
        indexes = [
            models.Index(
                fields=("chain_id", "occurred_at"),
                name="idx_ledger_chain_occurred",
            ),
        ]
        verbose_name = "Ledger Entry"
        verbose_name_plural = "Ledger Entries"

    def __str__(self) -> str:  # pragma: no cover - admin/debug helper
        label = self.resource_label
        return f"{self.occurred_at:%Y-%m-%d %H:%M:%S} [{self.chain_id}] {label}:{self.action}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("Ledger entries are immutable; updates are not allowed.")

        current_company = get_current_company()
        if self.scope == self.SCOPE_TENANT:
            if self.company_id is None and current_company is not None:
                self.company = current_company
            if self.company_id is None:
                raise ValidationError("company is required for tenant ledger entries.")
            if current_company is not None and self.company_id != current_company.id:
                raise ValidationError(
                    "Cross-tenant ledger write blocked: entry company does not match request tenant."
                )
        else:
            if self.company_id is not None:
                raise ValidationError("company must be NULL for platform ledger entries.")

        if not self.chain_id:
            if self.scope == self.SCOPE_TENANT and self.company_id:
                self.chain_id = f"tenant:{self.company_id}"
            else:
                self.chain_id = "platform"

        if not self.entry_hash:
            raise ValidationError(
                "entry_hash is required. Use ledger.services.append_ledger_entry()."
            )

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # pragma: no cover - enforced behavior
        raise ValidationError("Ledger entries are immutable; deletes are not allowed.")
