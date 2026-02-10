from django.conf import settings
from uuid import uuid4
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from tenancy.models import BaseTenantModel
from operational.models import Customer


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


class Insurer(BaseTenantModel):
    """
    Representa uma Seguradora (ex: Porto Seguro, Allianz, Bradesco).
    Substitui o campo string 'seguradora' do modelo legado.
    """
    name = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=18, blank=True)
    susep_code = models.CharField(max_length=20, blank=True, help_text="Código de registro na SUSEP")
    is_active = models.BooleanField(default=True)
    logo_url = models.URLField(blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "Seguradora"
        verbose_name_plural = "Seguradoras"

    def __str__(self):
        return self.name


class InsuranceProduct(BaseTenantModel):
    """
    Representa um produto comercial de seguro (ex: Auto Supremo, Vida Individual).
    Permite agrupar apólices por linha de negócio e regras específicas.
    """
    insurer = models.ForeignKey(Insurer, on_delete=models.PROTECT, related_name="products")
    branch = models.ForeignKey(InsuranceBranch, on_delete=models.PROTECT, related_name="products", null=True, blank=True)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True, help_text="Código interno do produto na seguradora")

    class Meta:
        ordering = ("insurer", "name")
        verbose_name = "Produto de Seguro"
        verbose_name_plural = "Produtos de Seguro"

    def __str__(self):
        return f"{self.insurer.name} - {self.name}"


class Policy(BaseTenantModel):
    """
    Entidade principal do contrato de seguro.
    Substitui 'operational.Apolice' com relacionamentos fortes.
    """
    STATUS_QUOTED = "QUOTED"
    STATUS_ISSUED = "ISSUED"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_EXPIRED = "EXPIRED"
    STATUS_CHOICES = [
        (STATUS_QUOTED, "Cotado"),
        (STATUS_ISSUED, "Emitido"),
        (STATUS_ACTIVE, "Vigente"),
        (STATUS_CANCELLED, "Cancelada"),
        (STATUS_EXPIRED, "Vencida"),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="policies")
    insurer = models.ForeignKey(Insurer, on_delete=models.PROTECT, related_name="policies")
    product = models.ForeignKey(InsuranceProduct, on_delete=models.PROTECT, related_name="policies")
    branch = models.ForeignKey(InsuranceBranch, on_delete=models.PROTECT, related_name="policies")
    policy_number = models.CharField(max_length=100, db_index=True)
    
    issue_date = models.DateField(null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUOTED)
    is_renewal = models.BooleanField(default=False, help_text="Indica se é uma renovação (regras específicas de comissão)")
    producer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="policies_sold",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("-end_date",)
        verbose_name = "Apólice"
        verbose_name_plural = "Apólices"
        indexes = [
            models.Index(fields=["company", "policy_number"]),
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "end_date"]),
        ]

    def __str__(self):
        return f"{self.policy_number} - {self.customer.name}"

    @property
    def is_health_plan(self):
        return self.branch.branch_type == InsuranceBranch.TYPE_HEALTH

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": "Data final deve ser posterior à data inicial."})


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


class Endorsement(BaseTenantModel):
    TYPE_INCREASE = "PREMIUM_INCREASE"
    TYPE_DECREASE = "PREMIUM_DECREASE"
    TYPE_NO_MOVE = "NO_PREMIUM_MOVEMENT"
    TYPE_CANCEL = "CANCELLATION_ENDORSEMENT"
    TYPE_HEALTH_ADD_BENEFICIARY = "HEALTH_ADD_BENEFICIARY"
    TYPE_CHOICES = [
        (TYPE_INCREASE, "Aumento de Prêmio"),
        (TYPE_DECREASE, "Redução de Prêmio"),
        (TYPE_NO_MOVE, "Sem Movimento Financeiro"),
        (TYPE_CANCEL, "Cancelamento"),
        (TYPE_HEALTH_ADD_BENEFICIARY, "Inclusão de Beneficiário (Saúde)"),
    ]

    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name="endorsements")
    endorsement_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    premium_delta = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    issue_date = models.DateField()
    effective_date = models.DateField()
    description = models.TextField(blank=True)

    class Meta:
        ordering = ("-issue_date", "-created_at")
        verbose_name = "Endosso"
        verbose_name_plural = "Endossos"

    def __str__(self):
        return f"{self.get_endorsement_type_display()} - {self.policy.policy_number}"


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