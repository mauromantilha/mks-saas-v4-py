from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from insurance_core.models.insurer import Insurer
from tenancy.models import BaseTenantModel


class InsuranceProduct(BaseTenantModel):
    """Tenant-scoped insurance product (plan) catalog for an insurer."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    class LineOfBusiness(models.TextChoices):
        AUTO = "AUTO", "Auto"
        LIFE = "LIFE", "Vida"
        HEALTH = "HEALTH", "Saude"
        PROPERTY = "PROPERTY", "Patrimonial"
        TRANSPORT = "TRANSPORT", "Transporte"
        LIABILITY = "LIABILITY", "RC"
        OTHER = "OTHER", "Outro"

    insurer = models.ForeignKey(
        Insurer,
        related_name="products",
        on_delete=models.PROTECT,
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=255)
    line_of_business = models.CharField(
        max_length=30,
        choices=LineOfBusiness.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    rules = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("line_of_business", "name")
        verbose_name = "Insurance Product"
        verbose_name_plural = "Insurance Products"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "insurer", "code"),
                name="uq_insurance_product_code_per_insurer_company",
            ),
        ]
        indexes = [
            models.Index(
                fields=("company", "line_of_business"),
                name="idx_product_company_lob",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.insurer.name} - {self.name}"

    def clean(self):
        super().clean()
        if self.insurer_id and self.company_id and self.insurer.company_id != self.company_id:
            raise ValidationError("InsuranceProduct and Insurer must belong to the same company.")

    def save(self, *args, **kwargs):
        if self.insurer_id:
            self.company = self.insurer.company
        return super().save(*args, **kwargs)


class ProductCoverage(BaseTenantModel):
    """Product coverage definitions (parametrizable coverages/guarantees)."""

    class CoverageType(models.TextChoices):
        BASIC = "BASIC", "Basic"
        ADDITIONAL = "ADDITIONAL", "Additional"
        ASSIST = "ASSIST", "Assist"

    product = models.ForeignKey(
        InsuranceProduct,
        related_name="coverages",
        on_delete=models.CASCADE,
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=255)
    coverage_type = models.CharField(
        max_length=20,
        choices=CoverageType.choices,
        default=CoverageType.BASIC,
    )
    default_limit_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    default_deductible_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    required = models.BooleanField(default=False)

    class Meta:
        ordering = ("product__id", "code")
        verbose_name = "Product Coverage"
        verbose_name_plural = "Product Coverages"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "product", "code"),
                name="uq_product_coverage_code_per_product_company",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.product.name} - {self.code}"

    def clean(self):
        super().clean()
        if self.product_id and self.company_id and self.product.company_id != self.company_id:
            raise ValidationError("ProductCoverage and InsuranceProduct must belong to the same company.")

    def save(self, *args, **kwargs):
        if self.product_id:
            self.company = self.product.company
        return super().save(*args, **kwargs)

