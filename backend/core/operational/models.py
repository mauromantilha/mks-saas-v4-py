from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

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
    source_lead = models.ForeignKey(
        Lead,
        related_name="converted_opportunities",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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


class CommercialActivity(BaseTenantModel):
    KIND_TASK = "TASK"
    KIND_FOLLOW_UP = "FOLLOW_UP"
    KIND_NOTE = "NOTE"
    KIND_CHOICES = [
        (KIND_TASK, "Task"),
        (KIND_FOLLOW_UP, "Follow-up"),
        (KIND_NOTE, "Note"),
    ]

    STATUS_PENDING = "PENDING"
    STATUS_DONE = "DONE"
    STATUS_CANCELED = "CANCELED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_DONE, "Done"),
        (STATUS_CANCELED, "Canceled"),
    ]

    PRIORITY_LOW = "LOW"
    PRIORITY_MEDIUM = "MEDIUM"
    PRIORITY_HIGH = "HIGH"
    PRIORITY_URGENT = "URGENT"
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_HIGH, "High"),
        (PRIORITY_URGENT, "Urgent"),
    ]

    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_TASK)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM,
    )
    due_at = models.DateTimeField(null=True, blank=True)
    reminder_at = models.DateTimeField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)
    sla_hours = models.PositiveIntegerField(null=True, blank=True)
    sla_due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    lead = models.ForeignKey(
        Lead,
        related_name="activities",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    opportunity = models.ForeignKey(
        Opportunity,
        related_name="activities",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="assigned_commercial_activities",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_commercial_activities",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("status", "due_at", "-created_at")
        constraints = [
            models.CheckConstraint(
                check=models.Q(lead__isnull=False) | models.Q(opportunity__isnull=False),
                name="ck_activity_requires_lead_or_opportunity",
            ),
        ]

    def __str__(self):
        return f"{self.kind} - {self.title}"

    @property
    def is_overdue(self):
        return (
            self.status == self.STATUS_PENDING
            and self.due_at is not None
            and self.due_at < timezone.now()
        )

    @property
    def is_sla_breached(self):
        return (
            self.status == self.STATUS_PENDING
            and self.sla_due_at is not None
            and self.sla_due_at < timezone.now()
        )

    def clean(self):
        super().clean()
        if self.lead_id and self.lead.company_id != self.company_id:
            raise ValidationError("Activity and Lead must belong to the same company.")
        if self.opportunity_id and self.opportunity.company_id != self.company_id:
            raise ValidationError("Activity and Opportunity must belong to the same company.")
        if self.reminder_at and self.due_at and self.reminder_at > self.due_at:
            raise ValidationError("Reminder must be before due date.")

    def save(self, *args, **kwargs):
        if self.status == self.STATUS_DONE and self.completed_at is None:
            self.completed_at = timezone.now()
        if self.status != self.STATUS_DONE:
            self.completed_at = None
        if self.sla_hours and self.sla_due_at is None:
            self.sla_due_at = timezone.now() + timedelta(hours=self.sla_hours)
        return super().save(*args, **kwargs)

    def mark_done(self):
        self.status = self.STATUS_DONE
        self.completed_at = timezone.now()
        self.save(update_fields=("status", "completed_at", "updated_at"))

    def reopen(self):
        self.status = self.STATUS_PENDING
        self.completed_at = None
        self.save(update_fields=("status", "completed_at", "updated_at"))


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
