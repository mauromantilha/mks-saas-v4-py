from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from insurance_core.models.insurer import Insurer
from insurance_core.models.product import InsuranceProduct, ProductCoverage
from tenancy.models import BaseTenantModel


_MIN_ZERO = MinValueValidator(Decimal("0.00"))


class Policy(BaseTenantModel):
    """Operational insurance policy aggregate (tenant scoped)."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        UNDERWRITING = "UNDERWRITING", "Underwriting"
        ISSUED = "ISSUED", "Issued"
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"

    policy_number = models.CharField(
        max_length=80,
        blank=True,
        null=True,
        help_text="Policy number assigned by the insurer (nullable until issued).",
    )
    insurer = models.ForeignKey(
        Insurer,
        related_name="policies",
        on_delete=models.PROTECT,
    )
    product = models.ForeignKey(
        InsuranceProduct,
        related_name="policies",
        on_delete=models.PROTECT,
    )

    insured_party_id = models.PositiveBigIntegerField(
        db_index=True,
        help_text="Reference to the insured party (Customer ID in the CRM bounded context).",
    )
    insured_party_label = models.CharField(
        max_length=255,
        blank=True,
        help_text="Snapshot label (ex: customer name) to avoid cross-context joins in listings.",
    )

    broker_reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    issue_date = models.DateField(null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()

    currency = models.CharField(max_length=3, default="BRL")
    premium_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[_MIN_ZERO],
    )
    tax_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[_MIN_ZERO],
    )
    commission_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[_MIN_ZERO],
    )
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_policies",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("-start_date", "-id")
        verbose_name = "Policy"
        verbose_name_plural = "Policies"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "policy_number"),
                name="uq_policy_number_per_company",
                condition=(~models.Q(policy_number__isnull=True) & ~models.Q(policy_number="")),
            ),
        ]
        indexes = [
            models.Index(
                fields=("company", "status", "start_date"),
                name="idx_pol_cmp_stat_start",
            ),
            models.Index(
                fields=("company", "insurer", "product"),
                name="idx_pol_cmp_ins_prod",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        label = self.policy_number or f"Policy #{self.pk}"
        return f"{label} ({self.status})"

    def clean(self):
        super().clean()

        errors: dict[str, str] = {}

        if self.start_date and self.end_date and self.start_date > self.end_date:
            errors["end_date"] = "end_date must be greater than or equal to start_date."

        if self.insurer_id and self.company_id and self.insurer.company_id != self.company_id:
            errors["insurer"] = "Policy and Insurer must belong to the same company."

        if self.product_id and self.company_id and self.product.company_id != self.company_id:
            errors["product"] = "Policy and InsuranceProduct must belong to the same company."

        if self.insurer_id and self.product_id and self.product.insurer_id != self.insurer_id:
            errors["product"] = "InsuranceProduct must belong to the selected insurer."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.product_id:
            self.company = self.product.company
            if not self.insurer_id:
                self.insurer = self.product.insurer
        elif self.insurer_id:
            self.company = self.insurer.company

        if self.policy_number == "":
            self.policy_number = None

        if self.currency:
            self.currency = self.currency.strip().upper()
        else:
            self.currency = "BRL"

        return super().save(*args, **kwargs)


class PolicyItem(BaseTenantModel):
    """Insured object (vehicle/property/etc.) attached to a policy."""

    class ItemType(models.TextChoices):
        AUTO = "AUTO", "Auto"
        PROPERTY = "PROPERTY", "Property"
        LIFE = "LIFE", "Life"
        OTHER = "OTHER", "Other"

    policy = models.ForeignKey(
        Policy,
        related_name="items",
        on_delete=models.CASCADE,
    )
    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    description = models.CharField(max_length=255, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    sum_insured = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[_MIN_ZERO],
    )

    class Meta:
        ordering = ("policy_id", "item_type", "id")
        verbose_name = "Policy Item"
        verbose_name_plural = "Policy Items"
        indexes = [
            models.Index(
                fields=("company", "policy", "item_type"),
                name="idx_pitem_cmp_pol_type",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.policy_id}:{self.item_type}"

    def clean(self):
        super().clean()
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("PolicyItem and Policy must belong to the same company.")

    def save(self, *args, **kwargs):
        if self.policy_id:
            self.company = self.policy.company
        return super().save(*args, **kwargs)


class PolicyCoverage(BaseTenantModel):
    """Coverage instances contracted inside a policy."""

    policy = models.ForeignKey(
        Policy,
        related_name="coverages",
        on_delete=models.CASCADE,
    )
    product_coverage = models.ForeignKey(
        ProductCoverage,
        related_name="policy_coverages",
        on_delete=models.PROTECT,
    )
    limit_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[_MIN_ZERO],
    )
    deductible_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[_MIN_ZERO],
    )
    premium_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[_MIN_ZERO],
    )
    is_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ("policy_id", "product_coverage_id", "id")
        verbose_name = "Policy Coverage"
        verbose_name_plural = "Policy Coverages"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "policy", "product_coverage"),
                name="uq_policy_coverage_per_policy_company",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.policy_id}:{self.product_coverage_id}"

    def clean(self):
        super().clean()
        errors: dict[str, str] = {}

        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            errors["policy"] = "PolicyCoverage and Policy must belong to the same company."

        if (
            self.product_coverage_id
            and self.policy_id
            and self.policy.product_id
            and self.product_coverage.product_id != self.policy.product_id
        ):
            errors["product_coverage"] = "Coverage must belong to the policy product."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.policy_id:
            self.company = self.policy.company
        return super().save(*args, **kwargs)


class PolicyDocumentRequirement(BaseTenantModel):
    """Document checklist required to issue / maintain a policy."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RECEIVED = "RECEIVED", "Received"
        VALIDATED = "VALIDATED", "Validated"
        REJECTED = "REJECTED", "Rejected"

    policy = models.ForeignKey(
        Policy,
        related_name="document_requirements",
        on_delete=models.CASCADE,
    )
    requirement_code = models.CharField(max_length=80)
    required = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    document_id = models.CharField(
        max_length=120,
        blank=True,
        help_text="Reference to documents module (future).",
    )

    class Meta:
        ordering = ("policy_id", "status", "id")
        verbose_name = "Policy Document Requirement"
        verbose_name_plural = "Policy Document Requirements"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "policy", "requirement_code"),
                name="uq_policy_doc_requirement_code_per_policy_company",
            ),
        ]
        indexes = [
            models.Index(
                fields=("company", "policy", "status"),
                name="idx_pdoc_cmp_pol_stat",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.policy_id}:{self.requirement_code}"

    def clean(self):
        super().clean()
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("PolicyDocumentRequirement and Policy must belong to the same company.")

    def save(self, *args, **kwargs):
        if self.policy_id:
            self.company = self.policy.company
        return super().save(*args, **kwargs)
