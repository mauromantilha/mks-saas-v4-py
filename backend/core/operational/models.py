from django.core.exceptions import ValidationError
from django.db import models

from tenancy.models import BaseTenantModel


class Customer(BaseTenantModel):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    document = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("company", "email"),
                name="uq_customer_email_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.name} <{self.email}>"


class Lead(BaseTenantModel):
    STATUS_CHOICES = [
        ("NEW", "Novo"),
        ("QUALIFIED", "Qualificado"),
        ("DISQUALIFIED", "Desqualificado"),
        ("CONVERTED", "Convertido"),
    ]

    source = models.CharField(max_length=100)
    customer = models.ForeignKey(
        Customer,
        related_name="leads",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="NEW")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Lead {self.id} - {self.source}"

    STATUS_TRANSITIONS = {
        "NEW": frozenset(("QUALIFIED", "DISQUALIFIED")),
        "QUALIFIED": frozenset(("CONVERTED", "DISQUALIFIED")),
        "DISQUALIFIED": frozenset(),
        "CONVERTED": frozenset(),
    }

    @classmethod
    def can_transition_status(cls, current_status: str, target_status: str) -> bool:
        if current_status == target_status:
            return True
        return target_status in cls.STATUS_TRANSITIONS.get(current_status, frozenset())

    def transition_status(self, target_status: str, *, save: bool = True):
        if not self.can_transition_status(self.status, target_status):
            raise ValidationError(
                f"Invalid lead status transition: {self.status} -> {target_status}."
            )
        self.status = target_status
        if save:
            self.save(update_fields=("status", "updated_at"))


class Opportunity(BaseTenantModel):
    STAGE_CHOICES = [
        ("DISCOVERY", "Descoberta"),
        ("PROPOSAL", "Proposta"),
        ("NEGOTIATION", "Negociação"),
        ("WON", "Ganha"),
        ("LOST", "Perdida"),
    ]

    customer = models.ForeignKey(
        Customer,
        related_name="opportunities",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=200)
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default="DISCOVERY")
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expected_close_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.title} ({self.customer.name})"

    STAGE_TRANSITIONS = {
        "DISCOVERY": frozenset(("PROPOSAL", "LOST")),
        "PROPOSAL": frozenset(("NEGOTIATION", "LOST")),
        "NEGOTIATION": frozenset(("WON", "LOST")),
        "WON": frozenset(),
        "LOST": frozenset(),
    }

    @classmethod
    def can_transition_stage(cls, current_stage: str, target_stage: str) -> bool:
        if current_stage == target_stage:
            return True
        return target_stage in cls.STAGE_TRANSITIONS.get(current_stage, frozenset())

    def transition_stage(self, target_stage: str, *, save: bool = True):
        if not self.can_transition_stage(self.stage, target_stage):
            raise ValidationError(
                f"Invalid opportunity stage transition: {self.stage} -> {target_stage}."
            )
        self.stage = target_stage
        if save:
            self.save(update_fields=("stage", "updated_at"))


class Apolice(BaseTenantModel):
    STATUS_CHOICES = [
        ("COTACAO", "Em Cotação"),
        ("PENDENTE", "Pendente de Emissão"),
        ("ATIVA", "Vigente"),
        ("CANCELADA", "Cancelada"),
        ("RENOVADA", "Renovada"),
        ("NAO_RENOVADA", "Não Renovada"),
    ]

    numero = models.CharField("Número da Apólice", max_length=50, blank=True, null=True)
    seguradora = models.CharField(max_length=100)
    ramo = models.CharField(max_length=50)
    cliente_nome = models.CharField(max_length=255)
    cliente_cpf_cnpj = models.CharField(max_length=20)
    inicio_vigencia = models.DateField()
    fim_vigencia = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="COTACAO")

    class Meta:
        verbose_name = "Apólice"
        verbose_name_plural = "Apólices"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "numero"),
                name="uq_apolice_numero_per_company",
                condition=models.Q(numero__isnull=False),
            ),
        ]

    def __str__(self):
        return f"{self.numero} - {self.cliente_nome}"


class Endosso(BaseTenantModel):
    """
    Endosso representa movimentações na apólice.
    A emissão original também é considerada um endosso (primeiro registro).
    """

    TIPO_CHOICES = [
        ("EMISSAO", "Emissão Inicial"),
        ("RENOVACAO", "Renovação"),
        ("INCLUSAO", "Endosso de Inclusão"),
        ("EXCLUSAO", "Endosso de Exclusão"),
        ("CANCELAMENTO", "Cancelamento"),
        ("FATURAMENTO", "Ajuste de Faturamento"),
        ("SEM_MOVIMENTO", "Alteração Cadastral"),
    ]

    apolice = models.ForeignKey(
        Apolice,
        related_name="endossos",
        on_delete=models.CASCADE,
    )
    numero_endosso = models.CharField(max_length=20, default="0")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    premio_liquido = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    iof = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    premio_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    percentual_comissao = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    valor_comissao = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    data_emissao = models.DateField()
    observacoes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Endosso"
        verbose_name_plural = "Endossos"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "apolice", "numero_endosso"),
                name="uq_endosso_numero_per_apolice_company",
            ),
        ]

    def __str__(self):
        return f"Endosso {self.numero_endosso} ({self.tipo}) - {self.apolice}"

    def clean(self):
        super().clean()
        if self.apolice_id and self.company_id and self.apolice.company_id != self.company_id:
            raise ValidationError("Endosso and Apólice must belong to the same company.")

    def save(self, *args, **kwargs):
        if self.apolice_id:
            self.company = self.apolice.company
        return super().save(*args, **kwargs)
