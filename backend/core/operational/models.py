from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
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
    INDUSTRY_CHOICES = [
        ("INDUSTRY", "Indústria"),
        ("COMMERCE", "Comércio"),
        ("RETAIL", "Varejo"),
        ("SERVICES", "Serviços"),
    ]
    LEAD_SOURCE_CHOICES = [
        ("SOCIAL_MEDIA", "Redes Sociais"),
        ("GOOGLE_ADS", "Google Ads"),
        ("FACEBOOK_ADS", "Facebook Ads"),
        ("OTHER", "Outros"),
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
        indexes = [
            models.Index(fields=["company", "lifecycle_stage", "-created_at"]),
            models.Index(fields=["company", "email"]),
            models.Index(fields=["company", "-last_contact_at"]),
            models.Index(fields=["company", "-next_follow_up_at"]),
            models.Index(fields=["assigned_to", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.name} <{self.email}>"


class SpecialProject(BaseTenantModel):
    TYPE_TRANSFER_RISK = "TRANSFER_RISK"
    TYPE_RISK_MANAGEMENT = "RISK_MANAGEMENT"
    TYPE_CHOICES = [
        (TYPE_TRANSFER_RISK, "Transferência de Risco (Seguros)"),
        (TYPE_RISK_MANAGEMENT, "Gestão de Riscos"),
    ]

    STATUS_OPEN = "OPEN"
    STATUS_CLOSED = "CLOSED"
    STATUS_CLOSED_WON = "CLOSED_WON"
    STATUS_CLOSED_LOST = "CLOSED_LOST"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Aberto"),
        (STATUS_CLOSED, "Fechado"),
        (STATUS_CLOSED_WON, "Ganho"),
        (STATUS_CLOSED_LOST, "Perdido"),
    ]

    customer = models.ForeignKey(
        Customer,
        related_name="special_projects",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    prospect_name = models.CharField(max_length=255, blank=True)
    prospect_document = models.CharField(max_length=20, blank=True)
    prospect_phone = models.CharField(max_length=30, blank=True)
    prospect_email = models.EmailField(blank=True)
    name = models.CharField(max_length=255)
    project_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="owned_special_projects",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    start_date = models.DateField()
    due_date = models.DateField()
    swot_strengths = models.TextField(blank=True)
    swot_weaknesses = models.TextField(blank=True)
    swot_opportunities = models.TextField(blank=True)
    swot_threats = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    loss_reason = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    won_at = models.DateTimeField(null=True, blank=True)
    lost_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("company", "status"), name="idx_special_project_status"),
            models.Index(fields=("company", "project_type"), name="idx_special_project_type"),
        ]

    def __str__(self):
        return f"Projeto {self.id} - {self.name}"

    def clean(self):
        super().clean()
        if self.customer_id and self.customer.company_id != self.company_id:
            raise ValidationError("Project and Customer must belong to the same company.")
        if self.owner_id and self.owner_id <= 0:
            raise ValidationError("Project owner is invalid.")
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValidationError("Due date must be greater or equal start date.")
        if self.status == self.STATUS_CLOSED_LOST and not self.loss_reason.strip():
            raise ValidationError("Loss reason is required for lost projects.")

    def save(self, *args, **kwargs):
        now = timezone.now()
        if self.status == self.STATUS_CLOSED:
            if self.closed_at is None:
                self.closed_at = now
            self.won_at = None
            self.lost_at = None
        elif self.status == self.STATUS_CLOSED_WON:
            if self.won_at is None:
                self.won_at = now
            self.closed_at = now
            self.lost_at = None
        elif self.status == self.STATUS_CLOSED_LOST:
            if self.lost_at is None:
                self.lost_at = now
            self.closed_at = now
            self.won_at = None
        else:
            self.closed_at = None
            self.won_at = None
            self.lost_at = None
        return super().save(*args, **kwargs)


class SpecialProjectActivity(BaseTenantModel):
    STATUS_OPEN = "OPEN"
    STATUS_DONE = "DONE"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Aberta"),
        (STATUS_DONE, "Concluída"),
    ]

    project = models.ForeignKey(
        SpecialProject,
        related_name="activities",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("status", "due_date", "id")

    def clean(self):
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Project activity must belong to the same company.")

    def save(self, *args, **kwargs):
        if self.project_id and self.company_id is None:
            self.company = self.project.company
        if self.status == self.STATUS_DONE and self.done_at is None:
            self.done_at = timezone.now()
        if self.status != self.STATUS_DONE:
            self.done_at = None
        return super().save(*args, **kwargs)


class SpecialProjectDocument(BaseTenantModel):
    project = models.ForeignKey(
        SpecialProject,
        related_name="documents",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="special_projects/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="uploaded_special_project_documents",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def clean(self):
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Project document must belong to the same company.")

    def save(self, *args, **kwargs):
        if self.project_id and self.company_id is None:
            self.company = self.project.company
        return super().save(*args, **kwargs)


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
        indexes = [
            models.Index(fields=["company", "status", "-created_at"]),
            models.Index(fields=["company", "-first_response_due_at"]),
            models.Index(fields=["company", "customer", "status"]),
            models.Index(fields=["company", "lead_score_label"]),
            models.Index(fields=["company", "-next_follow_up_at"]),
        ]

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


class CustomerContact(BaseTenantModel):
    customer = models.ForeignKey(
        Customer,
        related_name="contacts",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    role = models.CharField(max_length=120, blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-is_primary", "name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "customer"),
                condition=models.Q(is_primary=True),
                name="uq_customer_primary_contact_per_customer",
            ),
        ]
        indexes = [
            models.Index(fields=("company", "customer"), name="idx_customer_contact_customer"),
        ]

    def clean(self):
        super().clean()
        if self.customer_id and self.customer.company_id != self.company_id:
            raise ValidationError("Contact and Customer must belong to the same company.")

    def save(self, *args, **kwargs):
        if self.customer_id and self.company_id is None:
            self.company = self.customer.company
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
        indexes = [
            models.Index(fields=["company", "stage", "-created_at"]),
            models.Index(fields=["company", "customer", "stage"]),
            models.Index(fields=["company", "-expected_close_date"]),
            models.Index(fields=["company", "stage", "-amount"]),
            models.Index(fields=["company", "-next_step_due_at"]),
        ]

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
    TYPE_TASK = "TASK"
    TYPE_FOLLOW_UP = "FOLLOW_UP"
    TYPE_NOTE = "NOTE"
    TYPE_MEETING = "MEETING"
    TYPE_CHOICES = [
        (TYPE_TASK, "Task"),
        (TYPE_FOLLOW_UP, "Follow-up"),
        (TYPE_NOTE, "Note"),
        (TYPE_MEETING, "Meeting"),
    ]

    # Backwards-compatible aliases used across older frontend/backend paths.
    KIND_TASK = TYPE_TASK
    KIND_FOLLOW_UP = TYPE_FOLLOW_UP
    KIND_NOTE = TYPE_NOTE
    KIND_MEETING = TYPE_MEETING
    KIND_CHOICES = TYPE_CHOICES

    ORIGIN_LEAD = "LEAD"
    ORIGIN_OPPORTUNITY = "OPPORTUNITY"
    ORIGIN_PROJECT = "PROJECT"
    ORIGIN_CUSTOMER = "CUSTOMER"
    ORIGIN_CHOICES = [
        (ORIGIN_LEAD, "Lead"),
        (ORIGIN_OPPORTUNITY, "Opportunity"),
        (ORIGIN_PROJECT, "Project"),
        (ORIGIN_CUSTOMER, "Customer"),
    ]

    STATUS_OPEN = "OPEN"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_CANCELED = "CANCELED"
    STATUS_CONFIRMED = "CONFIRMED"
    # Backwards-compatible aliases used across older code paths.
    STATUS_PENDING = STATUS_OPEN
    STATUS_DONE = STATUS_COMPLETED
    LEGACY_STATUS_PENDING = "PENDING"
    LEGACY_STATUS_DONE = "DONE"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELED, "Canceled"),
        (STATUS_CONFIRMED, "Confirmed"),
        (LEGACY_STATUS_PENDING, "Pending (Legacy)"),
        (LEGACY_STATUS_DONE, "Done (Legacy)"),
    ]

    REMINDER_PENDING = "PENDING"
    REMINDER_SENT = "SENT"
    REMINDER_ACKED = "ACKED"
    REMINDER_STATE_CHOICES = [
        (REMINDER_PENDING, "Pending"),
        (REMINDER_SENT, "Sent"),
        (REMINDER_ACKED, "Acknowledged"),
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

    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_TASK)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_TASK)
    origin = models.CharField(max_length=20, choices=ORIGIN_CHOICES, default=ORIGIN_LEAD)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default=CHANNEL_EMAIL,
    )
    outcome = models.CharField(max_length=30, choices=OUTCOME_CHOICES, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM,
    )
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    remind_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    reminder_at = models.DateTimeField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)
    reminder_state = models.CharField(
        max_length=20,
        choices=REMINDER_STATE_CHOICES,
        default=REMINDER_PENDING,
    )
    sla_hours = models.PositiveIntegerField(null=True, blank=True)
    sla_due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    meeting_url = models.URLField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    attendee_name = models.CharField(max_length=255, blank=True)
    attendee_email = models.EmailField(blank=True)
    invite_sent_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

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
    project = models.ForeignKey(
        SpecialProject,
        related_name="commercial_activities",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customer,
        related_name="commercial_activities",
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
        ordering = ("status", "start_at", "due_at", "-created_at")
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(
                        origin="LEAD",
                        lead__isnull=False,
                        opportunity__isnull=True,
                        project__isnull=True,
                        customer__isnull=True,
                    )
                    | models.Q(
                        origin="OPPORTUNITY",
                        lead__isnull=True,
                        opportunity__isnull=False,
                        project__isnull=True,
                        customer__isnull=True,
                    )
                    | models.Q(
                        origin="PROJECT",
                        lead__isnull=True,
                        opportunity__isnull=True,
                        project__isnull=False,
                        customer__isnull=True,
                    )
                    | models.Q(
                        origin="CUSTOMER",
                        lead__isnull=True,
                        opportunity__isnull=True,
                        project__isnull=True,
                        customer__isnull=False,
                    )
                ),
                name="ck_activity_origin_matches_relation",
            ),
        ]
        indexes = [
            models.Index(
                fields=("company", "status", "start_at"),
                name="idx_act_company_st_start",
            ),
            models.Index(
                fields=("company", "remind_at"),
                name="idx_activity_company_remind",
            ),
        ]

    def __str__(self):
        return f"{self.type} - {self.title}"

    def _active_origin_fields(self):
        return {
            self.ORIGIN_LEAD: self.lead_id,
            self.ORIGIN_OPPORTUNITY: self.opportunity_id,
            self.ORIGIN_PROJECT: self.project_id,
            self.ORIGIN_CUSTOMER: self.customer_id,
        }

    def _infer_origin(self):
        for candidate, relation_id in self._active_origin_fields().items():
            if relation_id:
                return candidate
        return None

    @property
    def is_overdue(self):
        status_open = {self.STATUS_OPEN, self.STATUS_PENDING}
        due_anchor = self.start_at or self.due_at
        return (
            self.status in status_open
            and due_anchor is not None
            and due_anchor < timezone.now()
        )

    @property
    def is_sla_breached(self):
        status_open = {self.STATUS_OPEN, self.STATUS_PENDING}
        return (
            self.status in status_open
            and self.sla_due_at is not None
            and self.sla_due_at < timezone.now()
        )

    def clean(self):
        super().clean()
        if self.customer_id and self.customer.company_id != self.company_id:
            raise ValidationError("Activity and Customer must belong to the same company.")
        if self.lead_id and self.lead.company_id != self.company_id:
            raise ValidationError("Activity and Lead must belong to the same company.")
        if self.opportunity_id and self.opportunity.company_id != self.company_id:
            raise ValidationError("Activity and Opportunity must belong to the same company.")
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Activity and Project must belong to the same company.")

        active_fields = {
            key: bool(value) for key, value in self._active_origin_fields().items()
        }
        active_total = sum(1 for is_active in active_fields.values() if is_active)
        if active_total != 1:
            raise ValidationError("Activity must have exactly one active origin relation.")
        if not active_fields.get(self.origin, False):
            raise ValidationError("Activity origin must match the active relation.")

        if self.remind_at and self.start_at and self.remind_at > self.start_at:
            raise ValidationError("Remind date must be before start date.")
        if self.reminder_at and self.due_at and self.reminder_at > self.due_at:
            raise ValidationError("Reminder must be before due date.")
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValidationError("Activity end date must be after start date.")
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            raise ValidationError("Activity end date must be after start date.")

    def save(self, *args, **kwargs):
        # Keep legacy and canonical fields synchronized while migration is in progress.
        if self.type and self.kind != self.type:
            self.kind = self.type
        if self.kind and self.type != self.kind:
            self.type = self.kind

        if self.start_at is None:
            self.start_at = self.started_at or self.due_at
        if self.end_at is None and self.ended_at is not None:
            self.end_at = self.ended_at
        if self.remind_at is None and self.reminder_at is not None:
            self.remind_at = self.reminder_at
        if self.started_at is None and self.start_at is not None:
            self.started_at = self.start_at
        if self.ended_at is None and self.end_at is not None:
            self.ended_at = self.end_at
        if self.reminder_at is None and self.remind_at is not None:
            self.reminder_at = self.remind_at

        inferred_origin = self._infer_origin()
        if inferred_origin and self.origin != inferred_origin:
            self.origin = inferred_origin
        if self.origin == self.ORIGIN_LEAD:
            self.opportunity_id = None
            self.project_id = None
            self.customer_id = None
        elif self.origin == self.ORIGIN_OPPORTUNITY:
            self.lead_id = None
            self.project_id = None
            self.customer_id = None
        elif self.origin == self.ORIGIN_PROJECT:
            self.lead_id = None
            self.opportunity_id = None
            self.customer_id = None
        elif self.origin == self.ORIGIN_CUSTOMER:
            self.lead_id = None
            self.opportunity_id = None
            self.project_id = None

        if self.status == self.LEGACY_STATUS_PENDING:
            self.status = self.STATUS_OPEN
        if self.status == self.LEGACY_STATUS_DONE:
            self.status = self.STATUS_COMPLETED

        if self.status == self.STATUS_COMPLETED and self.completed_at is None:
            self.completed_at = timezone.now()
        if self.status != self.STATUS_COMPLETED:
            self.completed_at = None
        if self.status == self.STATUS_CONFIRMED and self.confirmed_at is None:
            self.confirmed_at = timezone.now()
        if self.status == self.STATUS_CANCELED and self.canceled_at is None:
            self.canceled_at = timezone.now()

        if self.reminder_state == self.REMINDER_SENT:
            self.reminder_sent = True
        if self.reminder_sent and self.reminder_state == self.REMINDER_PENDING:
            self.reminder_state = self.REMINDER_SENT

        self.clean()

        if self.sla_hours and self.sla_due_at is None:
            self.sla_due_at = timezone.now() + timedelta(hours=self.sla_hours)
        if self.started_at and self.ended_at:
            elapsed = self.ended_at - self.started_at
            self.duration_minutes = int(elapsed.total_seconds() // 60)
        return super().save(*args, **kwargs)

    def mark_done(self):
        self.status = self.STATUS_COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=("status", "completed_at", "updated_at"))

    def reopen(self):
        self.status = self.STATUS_OPEN
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


class OperationalIntegrationInbox(BaseTenantModel):
    event_id = models.CharField(max_length=120)
    event_type = models.CharField(max_length=120)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("company", "event_id"),
                name="uq_integration_inbox_event_id_company",
            ),
        ]


class Installment(BaseTenantModel):
    endosso = models.ForeignKey(
        Endosso,
        related_name="installments",
        on_delete=models.CASCADE,
    )
    number = models.PositiveSmallIntegerField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    due_date = models.DateField()
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("company", "endosso", "number"),
                name="uq_installment_number_per_endosso",
            ),
        ]


class TenantAIInteraction(BaseTenantModel):
    """
    Stores AI assistant interactions per tenant to support contextual learning.
    """

    query_text = models.TextField()
    focus = models.CharField(max_length=255, blank=True)
    cnpj = models.CharField(max_length=14, blank=True)
    context_snapshot = models.JSONField(default=dict, blank=True)
    cnpj_profile = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    learned_note = models.TextField(blank=True)
    is_pinned_learning = models.BooleanField(default=False)
    provider = models.CharField(max_length=50, blank=True)
    confidence_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="tenant_ai_interactions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=("company", "-created_at"),
                name="idx_taii_recent",
            ),
            models.Index(
                fields=("company", "is_pinned_learning"),
                name="idx_taii_pinned",
            ),
        ]


class AiConversation(BaseTenantModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="ai_conversations",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ("-updated_at", "-id")
        indexes = [
            models.Index(fields=("company", "status"), name="idx_aiconv_status"),
            models.Index(fields=("company", "-updated_at"), name="idx_aiconv_recent"),
            models.Index(fields=("company", "created_at"), name="idx_aiconv_ct"),
        ]


class AiMessage(BaseTenantModel):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"
        TOOL = "tool", "Tool"

    class Intent(models.TextChoices):
        WEB_MARKET = "WEB_MARKET", "Web Market"
        INTERNAL_ANALYTICS = "INTERNAL_ANALYTICS", "Internal Analytics"
        CNPJ_ENRICH = "CNPJ_ENRICH", "CNPJ Enrich"
        DOCS_RAG = "DOCS_RAG", "Docs RAG"
        SYSTEM_HEALTH = "SYSTEM_HEALTH", "System Health"
        MIXED = "MIXED", "Mixed"

    conversation = models.ForeignKey(
        AiConversation,
        related_name="messages",
        on_delete=models.CASCADE,
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    content = models.TextField()
    intent = models.CharField(max_length=30, choices=Intent.choices, default=Intent.MIXED)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [
            models.Index(fields=("company", "conversation"), name="idx_aimsg_conv"),
            models.Index(fields=("company", "intent"), name="idx_aimsg_intent"),
            models.Index(fields=("company", "created_at"), name="idx_aimsg_ct"),
        ]

    def clean(self):
        super().clean()
        if (
            self.conversation_id
            and self.company_id
            and self.conversation.company_id != self.company_id
        ):
            raise ValidationError("AiMessage and conversation must belong to the same company.")

    def save(self, *args, **kwargs):
        if self.conversation_id:
            self.company = self.conversation.company
        return super().save(*args, **kwargs)


class AiSuggestion(BaseTenantModel):
    class Scope(models.TextChoices):
        DASHBOARD = "dashboard", "Dashboard"
        FINANCE = "finance", "Finance"
        SALES = "sales", "Sales"
        OPERATIONAL = "operational", "Operational"

    scope = models.CharField(max_length=20, choices=Scope.choices)
    title = models.CharField(max_length=255)
    body = models.TextField()
    severity = models.CharField(max_length=20, blank=True)
    priority = models.CharField(max_length=20, blank=True)
    related_entity_type = models.CharField(max_length=80, blank=True)
    related_entity_id = models.CharField(max_length=80, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("company", "scope"), name="idx_aisug_scope"),
            models.Index(fields=("company", "expires_at"), name="idx_aisug_exp"),
            models.Index(fields=("company", "seen_at"), name="idx_aisug_seen"),
            models.Index(fields=("company", "created_at"), name="idx_aisug_ct"),
        ]


class AiDocumentChunk(BaseTenantModel):
    class SourceType(models.TextChoices):
        POLICY_DOCUMENT = "policy_document", "Policy Document"
        SPECIAL_PROJECT_DOCUMENT = "special_project_document", "Special Project Document"
        GENERIC_DOCUMENT = "generic_document", "Generic Document"

    source_type = models.CharField(max_length=40, choices=SourceType.choices)
    source_id = models.CharField(max_length=64)
    document_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=120, blank=True)
    chunk_text = models.TextField()
    chunk_order = models.PositiveIntegerField(default=0)
    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ("source_type", "source_id", "chunk_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "source_type", "source_id", "chunk_order"),
                name="uq_aidoc_chunk",
            ),
        ]
        indexes = [
            models.Index(
                fields=("company", "source_type", "source_id"),
                name="idx_aidoc_src",
            ),
            models.Index(fields=("company", "created_at"), name="idx_aidoc_ct"),
            GinIndex(fields=("search_vector",), name="idx_aidoc_srch"),
        ]
