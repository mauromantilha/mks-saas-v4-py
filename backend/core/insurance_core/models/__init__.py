from django.conf import settings
from uuid import uuid4
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from tenancy.models import BaseTenantModel
from operational.models import Customer

# Import from models package files
from .insurer import Insurer, InsurerContact
from .endorsement import Endorsement
from .policy import (
    Policy,
    PolicyCoverage,
    PolicyDocumentRequirement,
    PolicyItem,
)
from .product import InsuranceProduct, ProductCoverage


class InsuranceBranch(BaseTenantModel):
    """
    Ramo de Seguro (ex: Automóvel, Vida, Saúde, Patrimonial).
    Define regras macro de negócio (ex: Saúde tem regras de ANS).
    """
    TYPE_NORMAL = "NORMAL"
    TYPE_HEALTH = "HEALTH"
    TYPE_CHOICES = [
        (TYPE_NORMAL, "Seguro Geral"),
        (TYPE_HEALTH, "Plano de Saúde"),
    ]

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True, help_text="Código SUSEP")
    branch_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_NORMAL)

    class Meta:
        ordering = ("name",)
        verbose_name = "Ramo de Seguro"
        verbose_name_plural = "Ramos de Seguro"
        constraints = [
            models.UniqueConstraint(fields=("company", "code"), name="uq_insurance_branch_code_company"),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class PolicyBillingConfig(BaseTenantModel):
    """
    Configurações financeiras da apólice.
    Separa as regras de cobrança e comissionamento do contrato principal.
    """
    policy = models.OneToOneField(Policy, on_delete=models.CASCADE, related_name="billing_config")
    
    first_installment_due_date = models.DateField()
    installments_count = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Número de parcelas (1 a 12)"
    )
    premium_total = models.DecimalField(max_digits=14, decimal_places=2)
    commission_rate_percent = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentual de comissão acordado"
    )
    original_premium_total = models.DecimalField(
        max_digits=14, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Prêmio original da apólice (sem endossos) para cálculo de base de comissão (Health)"
    )

    class Meta:
        verbose_name = "Configuração de Faturamento"
        verbose_name_plural = "Configurações de Faturamento"

    def __str__(self):
        return f"Billing for {self.policy}"


class Claim(BaseTenantModel):
    STATUS_OPEN = "OPEN"
    STATUS_IN_REVIEW = "IN_REVIEW"
    STATUS_APPROVED = "APPROVED"
    STATUS_DENIED = "DENIED"
    STATUS_PAID = "PAID"
    STATUS_CLOSED = "CLOSED"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Aberto"),
        (STATUS_IN_REVIEW, "Em Análise"),
        (STATUS_APPROVED, "Aprovado"),
        (STATUS_DENIED, "Negado"),
        (STATUS_PAID, "Pago"),
        (STATUS_CLOSED, "Encerrado"),
    ]

    policy = models.ForeignKey(Policy, on_delete=models.PROTECT, related_name="claims")
    claim_number = models.CharField(max_length=50, db_index=True)
    occurrence_date = models.DateField()
    report_date = models.DateField()
    description = models.TextField(blank=True)
    
    amount_claimed = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    amount_approved = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    status_notes = models.TextField(blank=True, help_text="Motivo da decisão ou notas de status")

    class Meta:
        ordering = ("-report_date", "-created_at")
        verbose_name = "Sinistro"
        verbose_name_plural = "Sinistros"

    def __str__(self):
        return f"Claim {self.claim_number} - {self.policy.policy_number}"


class PolicyDocument(BaseTenantModel):
    """
    Armazena referências a arquivos no Cloud Storage.
    Não expõe URLs públicas; o acesso é via Signed URL gerada on-the-fly.
    """
    TYPE_POLICY = "POLICY"
    TYPE_ENDORSEMENT = "ENDORSEMENT"
    TYPE_CLAIM = "CLAIM"
    TYPE_BILL = "BILL"
    TYPE_OTHER = "OTHER"
    TYPE_CHOICES = [
        (TYPE_POLICY, "Apólice (PDF)"),
        (TYPE_ENDORSEMENT, "Endosso (PDF)"),
        (TYPE_CLAIM, "Sinistro"),
        (TYPE_BILL, "Boleto"),
        (TYPE_OTHER, "Outros"),
    ]

    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name="documents")
    endorsement = models.ForeignKey(Endorsement, on_delete=models.CASCADE, related_name="documents", null=True, blank=True)
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="documents", null=True, blank=True)
    document_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_OTHER)
    file_name = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=512, help_text="Caminho relativo no bucket (ex: tenants/1/policies/doc.pdf)")
    bucket_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    checksum = models.CharField(max_length=64, blank=True, help_text="Checksum (MD5/SHA256) for integrity")
    uploaded_at = models.DateTimeField(null=True, blank=True, help_text="When upload was confirmed")
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.file_name} ({self.get_document_type_display()})"


class DomainEventOutbox(BaseTenantModel):
    event_id = models.UUIDField(default=uuid4, editable=False, unique=True)
    event_type = models.CharField(max_length=255)
    payload = models.JSONField(default=dict)
    correlation_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=["company", "published_at"]),
            models.Index(fields=["company", "event_type"]),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.event_id}"


__all__ = [
    "Endorsement",
    "Insurer",
    "InsurerContact",
    "InsuranceProduct",
    "Policy",
    "PolicyCoverage",
    "PolicyDocumentRequirement",
    "PolicyItem",
    "ProductCoverage",
    "InsuranceBranch",
    "Claim",
    "PolicyDocument",
    "PolicyBillingConfig",
    "DomainEventOutbox",
]
