from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from tenancy.models import BaseTenantModel

class ParticipantProfile(BaseTenantModel):
    TYPE_INDEPENDENT = "INDEPENDENT_PRODUCER"
    TYPE_EMPLOYEE = "EMPLOYEE_SALESPERSON"
    TYPE_CHOICES = [
        (TYPE_INDEPENDENT, "Produtor Autônomo"),
        (TYPE_EMPLOYEE, "Vendedor CLT"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="commission_profile"
    )
    participant_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_INDEPENDENT)
    payout_rules = models.JSONField(default=dict, blank=True, help_text="Regras de repasse (ex: {'retention_percent': 10.0})")

    class Meta:
        verbose_name = "Perfil de Comissionado"
        verbose_name_plural = "Perfis de Comissionados"

    def __str__(self):
        return f"{self.user} - {self.get_participant_type_display()}"


class CommissionPlanScope(BaseTenantModel):
    BASIS_ISSUED = "ISSUED"
    BASIS_PAID = "PAID"
    BASIS_CHOICES = [
        (BASIS_ISSUED, "Na Emissão"),
        (BASIS_PAID, "No Pagamento"),
    ]

    priority = models.PositiveIntegerField(default=0, help_text="Higher number = higher priority")
    insurer_name = models.CharField(max_length=120, blank=True, help_text="Empty matches all")
    product_line = models.CharField(max_length=50, blank=True, help_text="Empty matches all")
    trigger_basis = models.CharField(max_length=10, choices=BASIS_CHOICES, default=BASIS_ISSUED)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        ordering = ("-priority", "-created_at")

    def __str__(self):
        return f"Plan {self.priority} - {self.trigger_basis} ({self.commission_percent}%)"


class CommissionAccrual(BaseTenantModel):
    STATUS_PENDING = "PENDING"
    STATUS_PAYABLE = "PAYABLE"
    STATUS_PAID = "PAID"
    STATUS_REVERSED = "REVERSED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_PAYABLE, "A Pagar"),
        (STATUS_PAID, "Pago"),
        (STATUS_REVERSED, "Estornado"),
    ]

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PAYABLE)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="commission_accruals",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    recipient_type = models.CharField(max_length=30, blank=True, help_text="Tipo do participante no momento do accrual")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Accrual {self.amount} - {self.description}"


class CommissionPayoutBatch(BaseTenantModel):
    STATUS_DRAFT = "DRAFT"
    STATUS_APPROVED = "APPROVED"
    STATUS_PROCESSED = "PROCESSED"
    STATUS_CANCELED = "CANCELED"
    STATUS_PAID = "PAID"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Rascunho"),
        (STATUS_APPROVED, "Aprovado"),
        (STATUS_PROCESSED, "Processado"),
        (STATUS_CANCELED, "Cancelado"),
        (STATUS_PAID, "Pago"),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    period_start = models.DateField()
    period_end = models.DateField()
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_payout_batches",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approved_payout_batches",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Batch {self.id} ({self.period_start} - {self.period_end})"


class CommissionPayoutItem(BaseTenantModel):
    STATUS_PENDING = "PENDING"
    STATUS_PAID = "PAID"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_PAID, "Pago"),
    ]

    batch = models.ForeignKey(
        CommissionPayoutBatch,
        related_name="items",
        on_delete=models.CASCADE,
    )
    accrual = models.OneToOneField(
        CommissionAccrual,
        related_name="payout_item",
        on_delete=models.PROTECT,
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("company", "accrual"),
                name="uq_payout_item_accrual_company",
            ),
        ]


class InsurerPayableAccrual(BaseTenantModel):
    STATUS_PENDING = "PENDING"
    STATUS_SETTLED = "SETTLED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_SETTLED, "Liquidado"),
    ]

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    insurer_name = models.CharField(max_length=120)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Payable {self.amount} - {self.insurer_name}"


class InsurerSettlementBatch(BaseTenantModel):
    STATUS_DRAFT = "DRAFT"
    STATUS_APPROVED = "APPROVED"
    STATUS_PROCESSED = "PROCESSED"
    STATUS_CANCELED = "CANCELED"
    STATUS_PAID = "PAID"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Rascunho"),
        (STATUS_APPROVED, "Aprovado"),
        (STATUS_PROCESSED, "Processado"),
        (STATUS_CANCELED, "Cancelado"),
        (STATUS_PAID, "Pago"),
    ]

    insurer_name = models.CharField(max_length=120)
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_insurer_batches",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approved_insurer_batches",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)


class InsurerSettlementItem(BaseTenantModel):
    STATUS_PENDING = "PENDING"
    STATUS_PAID = "PAID"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_PAID, "Pago"),
    ]

    batch = models.ForeignKey(
        InsurerSettlementBatch,
        related_name="items",
        on_delete=models.CASCADE,
    )
    accrual = models.OneToOneField(
        InsurerPayableAccrual,
        related_name="settlement_item",
        on_delete=models.PROTECT,
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)