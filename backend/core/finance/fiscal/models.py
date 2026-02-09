from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models

from tenancy.models import BaseTenantModel


class FiscalProvider(models.Model):
    """Catalog of fiscal emission providers.

    This model is intentionally provider-agnostic. `provider_type` is used to select
    the adapter/driver implementation at runtime, without coupling the DB schema to
    a specific vendor.
    """

    name = models.CharField(max_length=120)
    provider_type = models.CharField(
        max_length=60,
        help_text="Adapter identifier (ex: focusnfe, nfeio, plugnotas).",
    )
    api_base_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        verbose_name = "Fiscal Provider"
        verbose_name_plural = "Fiscal Providers"
        constraints = [
            models.UniqueConstraint(
                fields=("provider_type",),
                name="uq_fiscal_provider_type",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.provider_type})"


class TenantFiscalConfig(BaseTenantModel):
    """Per-tenant fiscal provider configuration.

    Notes on secrets:
    - For production, store secrets in Secret Manager and keep only references here.
    - For local dev, you may store raw tokens, but treat this as sensitive data.
    """

    class Environment(models.TextChoices):
        SANDBOX = "SANDBOX", "Sandbox"
        PRODUCTION = "PRODUCTION", "Production"

    provider = models.ForeignKey(
        FiscalProvider,
        on_delete=models.PROTECT,
        related_name="tenant_configs",
    )
    api_token = models.TextField(blank=True)
    environment = models.CharField(
        max_length=20,
        choices=Environment.choices,
        default=Environment.SANDBOX,
        db_index=True,
    )
    active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("-active", "-updated_at", "id")
        verbose_name = "Tenant Fiscal Config"
        verbose_name_plural = "Tenant Fiscal Configs"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "provider"),
                name="uq_tenant_fiscal_config_provider_per_tenant",
            ),
            models.UniqueConstraint(
                fields=("company",),
                condition=models.Q(active=True),
                name="uq_tenant_fiscal_config_single_active_per_tenant",
            ),
        ]
        indexes = [
            models.Index(
                fields=("company", "active", "environment"),
                name="idx_tenant_fiscal_config_active_env",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        status = "active" if self.active else "inactive"
        return f"{self.company_id} - {self.provider.provider_type} ({self.environment}, {status})"


class FiscalDocument(BaseTenantModel):
    """Fiscal document emitted for an invoice (finance bounded context).

    - This model must NOT FK to finance invoices to keep bounded contexts decoupled.
    - `invoice_id` is a numeric reference to the finance invoice record.
    - XML is stored in `xml_content` (and can also be mirrored to Cloud Storage via `xml_document_id`).
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        EMITTING = "EMITTING", "Emitting"
        AUTHORIZED = "AUTHORIZED", "Authorized"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    invoice_id = models.PositiveBigIntegerField(db_index=True)
    provider_document_id = models.CharField(
        max_length=200,
        blank=True,
        help_text="External provider document id used for status/cancellation calls.",
    )
    number = models.CharField(max_length=40, blank=True)
    series = models.CharField(max_length=20, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    xml_document_id = models.CharField(
        max_length=200,
        blank=True,
        help_text="External XML document reference (Cloud Storage object path, documents module id, etc.).",
    )
    xml_content = models.TextField(
        blank=True,
        help_text="Raw XML content snapshot stored for audit and interoperability.",
    )

    class Meta:
        ordering = ("-issue_date", "-id")
        verbose_name = "Fiscal Document"
        verbose_name_plural = "Fiscal Documents"
        indexes = [
            models.Index(fields=("company", "invoice_id"), name="idx_fiscal_doc_invoice"),
            models.Index(fields=("company", "status", "issue_date"), name="idx_fiscal_doc_status"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("company", "series", "number"),
                condition=~models.Q(number=""),
                name="uq_fiscal_doc_number_per_tenant",
            ),
            models.UniqueConstraint(
                fields=("company", "provider_document_id"),
                condition=~models.Q(provider_document_id=""),
                name="uq_fiscal_doc_provider_document_id_per_tenant",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        label = f"{self.series}-{self.number}" if self.number else f"invoice:{self.invoice_id}"
        return f"FiscalDocument {label} [{self.status}]"


class FiscalCustomerSnapshot(BaseTenantModel):
    """Immutable customer snapshot used for fiscal emission/audits.

    We store a snapshot to avoid cross-context reads and to keep fiscal documents stable
    even if the CRM customer data changes later.
    """

    fiscal_document = models.OneToOneField(
        FiscalDocument,
        related_name="customer_snapshot",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    cpf_cnpj = models.CharField(max_length=20)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ("-id",)
        verbose_name = "Fiscal Customer Snapshot"
        verbose_name_plural = "Fiscal Customer Snapshots"
        indexes = [
            models.Index(fields=("company", "cpf_cnpj"), name="idx_fiscal_snap_cpfcnpj"),
        ]

    def save(self, *args, **kwargs):
        if self.fiscal_document_id:
            self.company = self.fiscal_document.company
        return super().save(*args, **kwargs)
