from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from tenancy.models import BaseTenantModel


INSURANCE_LINE_CHOICES = [
    ("AUTO", "Auto"),
    ("LIFE", "Vida"),
    ("HEALTH", "Saúde"),
    ("PROPERTY", "Patrimonial"),
    ("TRANSPORT", "Transporte"),
    ("LIABILITY", "Responsabilidade Civil"),
    ("OTHER", "Outro"),
]


class Customer(BaseTenantModel):
    TYPE_INDIVIDUAL = "INDIVIDUAL"
    TYPE_COMPANY = "COMPANY"
    TYPE_CHOICES = [
        (TYPE_INDIVIDUAL, "Pessoa Física"),
        (TYPE_COMPANY, "Pessoa Jurídica"),
    ]

    STAGE_LEAD = "LEAD"
    STAGE_PROSPECT = "PROSPECT"
    STAGE_CUSTOMER = "CUSTOMER"
    STAGE_INACTIVE = "INACTIVE"
    STAGE_CHOICES = [
        (STAGE_LEAD, "Lead"),
        (STAGE_PROSPECT, "Prospect"),
        (STAGE_CUSTOMER, "Cliente"),
        (STAGE_INACTIVE, "Inativo"),
    ]

    name = models.CharField(max_length=255)
    email = models.EmailField()
    customer_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_COMPANY,
    )
    lifecycle_stage = models.CharField(
        max_length=20,
        choices=STAGE_CHOICES,
        default=STAGE_PROSPECT,
    )
    legal_name = models.CharField(max_length=255, blank=True)
    trade_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    document = models.CharField(max_length=20, blank=True)
    cnpj = models.CharField(max_length=18, blank=True, db_index=True)
    cpf = models.CharField(max_length=14, blank=True, db_index=True)
    state_registration = models.CharField(max_length=50, blank=True)
    municipal_registration = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    lead_source = models.CharField(max_length=120, blank=True)
    industry = models.CharField(max_length=120, blank=True)
    company_size = models.CharField(max_length=50, blank=True)
    annual_revenue = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
    )
    contact_name = models.CharField(max_length=255, blank=True)
    contact_role = models.CharField(max_length=120, blank=True)
    secondary_contact_name = models.CharField(max_length=255, blank=True)
    secondary_contact_email = models.EmailField(blank=True)
    secondary_contact_phone = models.CharField(max_length=30, blank=True)
    billing_email = models.EmailField(blank=True)
    billing_phone = models.CharField(max_length=30, blank=True)
    zip_code = models.CharField(max_length=12, blank=True)
    state = models.CharField(max_length=60, blank=True)
    city = models.CharField(max_length=120, blank=True)
    neighborhood = models.CharField(max_length=120, blank=True)
    street = models.CharField(max_length=255, blank=True)
    street_number = models.CharField(max_length=30, blank=True)
    address_complement = models.CharField(max_length=120, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="assigned_customers",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    last_contact_at = models.DateTimeField(null=True, blank=True)
    next_follow_up_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("company", "email"),
                name="uq_customer_email_per_company",
            ),
            models.UniqueConstraint(
                fields=("company", "cnpj"),
                name="uq_customer_cnpj_per_company",
                condition=~models.Q(cnpj=""),
            ),
        ]

    def __str__(self):
        return f"{self.name} <{self.email}>"


class Lead(BaseTenantModel):
    CHANNEL_WEBHOOK = "WEBHOOK"
    CHANNEL_API = "API"
    CHANNEL_MANUAL = "MANUAL"
    CHANNEL_IMPORT = "IMPORT"
    CAPTURE_CHANNEL_CHOICES = [
        (CHANNEL_WEBHOOK, "Webhook"),
        (CHANNEL_API, "API"),
        (CHANNEL_MANUAL, "Cadastro Manual"),
        (CHANNEL_IMPORT, "Importação"),
    ]

    SCORE_COLD = "COLD"
    SCORE_WARM = "WARM"
    SCORE_HOT = "HOT"
    SCORE_LABEL_CHOICES = [
        (SCORE_COLD, "Frio"),
        (SCORE_WARM, "Morno"),
        (SCORE_HOT, "Quente"),
    ]

    STATUS_CHOICES = [
        ("NEW", "Novo"),
        ("QUALIFIED", "Qualificado"),
        ("DISQUALIFIED", "Desqualificado"),
        ("CONVERTED", "Convertido"),
    ]

    source = models.CharField(max_length=100)
    capture_channel = models.CharField(
        max_length=20,
        choices=CAPTURE_CHANNEL_CHOICES,
        default=CHANNEL_MANUAL,
    )
    external_id = models.CharField(max_length=120, blank=True)
    external_campaign = models.CharField(max_length=120, blank=True)
    full_name = models.CharField(max_length=255, blank=True)
    job_title = models.CharField(max_length=120, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    cnpj = models.CharField(max_length=18, blank=True, db_index=True)
    website = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    lead_score_label = models.CharField(
        max_length=10,
        choices=SCORE_LABEL_CHOICES,
        blank=True,
    )
    product_line = models.CharField(
        max_length=20,
        choices=INSURANCE_LINE_CHOICES,
        blank=True,
    )
    cnae_code = models.CharField(max_length=12, blank=True)
    company_size_estimate = models.CharField(max_length=60, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    needs_summary = models.TextField(blank=True)
    needs_payload = models.JSONField(default=dict, blank=True)
    first_response_sla_minutes = models.PositiveIntegerField(default=30)
    first_response_due_at = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    customer = models.ForeignKey(
        Customer,
        related_name="leads",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="NEW")
    products_of_interest = models.CharField(max_length=255, blank=True)
    estimated_budget = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    estimated_close_date = models.DateField(null=True, blank=True)
    qualification_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    disqualification_reason = models.TextField(blank=True)
    last_contact_at = models.DateTimeField(null=True, blank=True)
    next_follow_up_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Lead {self.id} - {self.source}"

    def best_customer_name(self) -> str:
        for candidate in (
            self.company_name,
            self.full_name,
            self.source,
        ):
            candidate = (candidate or "").strip()
            if candidate:
                return candidate
        return f"Lead {self.id}"

    def best_customer_email(self) -> str:
        return (self.email or "").strip().lower()

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

    def save(self, *args, **kwargs):
        if self.first_response_due_at is None and self.first_response_sla_minutes:
            self.first_response_due_at = timezone.now() + timedelta(
                minutes=self.first_response_sla_minutes
            )
        if self.first_response_at and self.status == "NEW":
            self.status = "QUALIFIED"
        return super().save(*args, **kwargs)


class Opportunity(BaseTenantModel):
    STAGE_CHOICES = [
        ("NEW", "Novo/Sem Contato"),
        ("QUALIFICATION", "Qualificação"),
        ("NEEDS_ASSESSMENT", "Levantamento de Necessidades"),
        ("QUOTATION", "Cotação"),
        ("PROPOSAL_PRESENTATION", "Apresentação de Proposta"),
        ("DISCOVERY", "Descoberta (Legado)"),
        ("PROPOSAL", "Proposta (Legado)"),
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
    stage = models.CharField(max_length=30, choices=STAGE_CHOICES, default="NEW")
    product_line = models.CharField(
        max_length=20,
        choices=INSURANCE_LINE_CHOICES,
        blank=True,
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expected_close_date = models.DateField(null=True, blank=True)
    closing_probability = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    next_step = models.CharField(max_length=255, blank=True)
    next_step_due_at = models.DateTimeField(null=True, blank=True)
    needs_payload = models.JSONField(default=dict, blank=True)
    quote_payload = models.JSONField(default=dict, blank=True)
    proposal_pdf_url = models.URLField(blank=True)
    proposal_tracking_token = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
    )
    proposal_sent_at = models.DateTimeField(null=True, blank=True)
    proposal_viewed_at = models.DateTimeField(null=True, blank=True)
    loss_reason = models.TextField(blank=True)
    competitors = models.CharField(max_length=255, blank=True)
    handover_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.title} ({self.customer.name})"

    STAGE_TRANSITIONS = {
        "NEW": frozenset(("QUALIFICATION", "DISCOVERY", "LOST")),
        "QUALIFICATION": frozenset(("NEEDS_ASSESSMENT", "PROPOSAL", "LOST")),
        "NEEDS_ASSESSMENT": frozenset(("QUOTATION", "PROPOSAL", "LOST")),
        "QUOTATION": frozenset(("PROPOSAL_PRESENTATION", "PROPOSAL", "LOST")),
        "PROPOSAL_PRESENTATION": frozenset(("NEGOTIATION", "LOST")),
        "DISCOVERY": frozenset(("PROPOSAL", "QUALIFICATION", "LOST")),
        "PROPOSAL": frozenset(("NEGOTIATION", "PROPOSAL_PRESENTATION", "LOST")),
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

    def save(self, *args, **kwargs):
        if not self.proposal_tracking_token:
            self.proposal_tracking_token = uuid4().hex
        return super().save(*args, **kwargs)


class ProposalOption(BaseTenantModel):
    opportunity = models.ForeignKey(
        Opportunity,
        related_name="proposal_options",
        on_delete=models.CASCADE,
    )
    insurer_name = models.CharField(max_length=120)
    plan_name = models.CharField(max_length=120, blank=True)
    coverage_summary = models.TextField(blank=True)
    deductible = models.CharField(max_length=120, blank=True)
    annual_premium = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    monthly_premium = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    franchise_notes = models.TextField(blank=True)
    commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    commission_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    ranking_score = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    is_recommended = models.BooleanField(default=False)
    external_reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-is_recommended", "-ranking_score", "annual_premium", "-created_at")

    def __str__(self):
        return f"{self.insurer_name} - {self.plan_name or 'Plano'}"

    def clean(self):
        super().clean()
        if self.opportunity_id and self.opportunity.company_id != self.company_id:
            raise ValidationError(
                "Proposal option and Opportunity must belong to the same company."
            )

    def save(self, *args, **kwargs):
        if self.opportunity_id:
            self.company = self.opportunity.company
        return super().save(*args, **kwargs)


class PolicyRequest(BaseTenantModel):
    STATUS_PENDING_DATA = "PENDING_DATA"
    STATUS_UNDER_REVIEW = "UNDER_REVIEW"
    STATUS_READY_TO_ISSUE = "READY_TO_ISSUE"
    STATUS_ISSUED = "ISSUED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CHOICES = [
        (STATUS_PENDING_DATA, "Pendente de Dados"),
        (STATUS_UNDER_REVIEW, "Em Revisão"),
        (STATUS_READY_TO_ISSUE, "Pronto para Emissão"),
        (STATUS_ISSUED, "Emitida"),
        (STATUS_REJECTED, "Rejeitada"),
    ]

    INSPECTION_NOT_REQUIRED = "NOT_REQUIRED"
    INSPECTION_PENDING = "PENDING"
    INSPECTION_SCHEDULED = "SCHEDULED"
    INSPECTION_APPROVED = "APPROVED"
    INSPECTION_REJECTED = "REJECTED"
    INSPECTION_STATUS_CHOICES = [
        (INSPECTION_NOT_REQUIRED, "Sem Vistoria"),
        (INSPECTION_PENDING, "Vistoria Pendente"),
        (INSPECTION_SCHEDULED, "Vistoria Agendada"),
        (INSPECTION_APPROVED, "Vistoria Aprovada"),
        (INSPECTION_REJECTED, "Vistoria Rejeitada"),
    ]

    BILLING_BANK_DEBIT = "BANK_DEBIT"
    BILLING_INVOICE = "INVOICE"
    BILLING_PIX = "PIX"
    BILLING_CREDIT_CARD = "CREDIT_CARD"
    BILLING_OTHER = "OTHER"
    BILLING_METHOD_CHOICES = [
        (BILLING_BANK_DEBIT, "Débito em Conta"),
        (BILLING_INVOICE, "Boleto"),
        (BILLING_PIX, "PIX"),
        (BILLING_CREDIT_CARD, "Cartão de Crédito"),
        (BILLING_OTHER, "Outro"),
    ]

    opportunity = models.OneToOneField(
        Opportunity,
        related_name="policy_request",
        on_delete=models.CASCADE,
    )
    customer = models.ForeignKey(
        Customer,
        related_name="policy_requests",
        on_delete=models.CASCADE,
    )
    source_lead = models.ForeignKey(
        Lead,
        related_name="policy_requests",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    product_line = models.CharField(
        max_length=20,
        choices=INSURANCE_LINE_CHOICES,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING_DATA,
    )
    inspection_required = models.BooleanField(default=True)
    inspection_status = models.CharField(
        max_length=20,
        choices=INSPECTION_STATUS_CHOICES,
        default=INSPECTION_PENDING,
    )
    inspection_scheduled_at = models.DateTimeField(null=True, blank=True)
    inspection_notes = models.TextField(blank=True)
    billing_method = models.CharField(
        max_length=20,
        choices=BILLING_METHOD_CHOICES,
        blank=True,
    )
    bank_account_holder = models.CharField(max_length=120, blank=True)
    bank_name = models.CharField(max_length=120, blank=True)
    bank_branch = models.CharField(max_length=20, blank=True)
    bank_account = models.CharField(max_length=30, blank=True)
    bank_document = models.CharField(max_length=20, blank=True)
    payment_day = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
    )
    final_premium = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    final_commission = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    issue_deadline_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("status", "issue_deadline_at", "-created_at")

    def __str__(self):
        return f"PolicyRequest #{self.id} - {self.customer.name}"

    def clean(self):
        super().clean()
        if self.opportunity_id and self.opportunity.company_id != self.company_id:
            raise ValidationError(
                "Policy request and Opportunity must belong to the same company."
            )
        if self.customer_id and self.customer.company_id != self.company_id:
            raise ValidationError(
                "Policy request and Customer must belong to the same company."
            )
        if self.source_lead_id and self.source_lead.company_id != self.company_id:
            raise ValidationError("Policy request and Lead must belong to the same company.")

    def save(self, *args, **kwargs):
        if self.opportunity_id:
            self.company = self.opportunity.company
            if self.customer_id is None:
                self.customer = self.opportunity.customer
            if self.source_lead_id is None and self.opportunity.source_lead_id:
                self.source_lead = self.opportunity.source_lead
            if not self.product_line and self.opportunity.product_line:
                self.product_line = self.opportunity.product_line
        if not self.inspection_required:
            self.inspection_status = self.INSPECTION_NOT_REQUIRED
        if self.status == self.STATUS_ISSUED and self.issued_at is None:
            self.issued_at = timezone.now()
        return super().save(*args, **kwargs)


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

    CHANNEL_EMAIL = "EMAIL"
    CHANNEL_PHONE = "PHONE"
    CHANNEL_WHATSAPP = "WHATSAPP"
    CHANNEL_MEETING = "MEETING"
    CHANNEL_VISIT = "VISIT"
    CHANNEL_LINKEDIN = "LINKEDIN"
    CHANNEL_OTHER = "OTHER"
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_PHONE, "Phone"),
        (CHANNEL_WHATSAPP, "WhatsApp"),
        (CHANNEL_MEETING, "Meeting"),
        (CHANNEL_VISIT, "Visit"),
        (CHANNEL_LINKEDIN, "LinkedIn"),
        (CHANNEL_OTHER, "Other"),
    ]

    OUTCOME_CONNECTED = "CONNECTED"
    OUTCOME_NO_ANSWER = "NO_ANSWER"
    OUTCOME_INTERESTED = "INTERESTED"
    OUTCOME_NOT_INTERESTED = "NOT_INTERESTED"
    OUTCOME_FOLLOW_UP_SCHEDULED = "FOLLOW_UP_SCHEDULED"
    OUTCOME_PROPOSAL_SENT = "PROPOSAL_SENT"
    OUTCOME_CLOSED_WON = "CLOSED_WON"
    OUTCOME_CLOSED_LOST = "CLOSED_LOST"
    OUTCOME_CHOICES = [
        (OUTCOME_CONNECTED, "Connected"),
        (OUTCOME_NO_ANSWER, "No answer"),
        (OUTCOME_INTERESTED, "Interested"),
        (OUTCOME_NOT_INTERESTED, "Not interested"),
        (OUTCOME_FOLLOW_UP_SCHEDULED, "Follow-up scheduled"),
        (OUTCOME_PROPOSAL_SENT, "Proposal sent"),
        (OUTCOME_CLOSED_WON, "Closed won"),
        (OUTCOME_CLOSED_LOST, "Closed lost"),
    ]

    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_TASK)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default=CHANNEL_EMAIL,
    )
    outcome = models.CharField(max_length=30, choices=OUTCOME_CHOICES, blank=True)
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
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    meeting_url = models.URLField(blank=True)
    location = models.CharField(max_length=255, blank=True)

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
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            raise ValidationError("Activity end date must be after start date.")

    def save(self, *args, **kwargs):
        if self.status == self.STATUS_DONE and self.completed_at is None:
            self.completed_at = timezone.now()
        if self.status != self.STATUS_DONE:
            self.completed_at = None
        if self.sla_hours and self.sla_due_at is None:
            self.sla_due_at = timezone.now() + timedelta(hours=self.sla_hours)
        if self.started_at and self.ended_at:
            elapsed = self.ended_at - self.started_at
            self.duration_minutes = int(elapsed.total_seconds() // 60)
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


class SalesGoal(BaseTenantModel):
    """Metas comerciais mensais por tenant (usadas no dashboard)."""

    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    premium_goal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    commission_goal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    new_customers_goal = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Meta Comercial"
        verbose_name_plural = "Metas Comerciais"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "year", "month"),
                name="uq_sales_goal_month_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.company.tenant_code} {self.year}-{self.month:02d}"
