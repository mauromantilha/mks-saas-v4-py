from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Tenant(models.Model):
    STATUS_ACTIVE = "ACTIVE"
    STATUS_SUSPENDED = "SUSPENDED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_DELETED = "DELETED"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_DELETED, "Deleted"),
    ]

    company = models.OneToOneField(
        "customers.Company",
        on_delete=models.CASCADE,
        related_name="control_tenant",
    )
    legal_name = models.CharField(max_length=180)
    cnpj = models.CharField(max_length=18, blank=True)
    contact_email = models.EmailField(blank=True)
    slug = models.SlugField(max_length=63, unique=True)
    subdomain = models.SlugField(max_length=63, unique=True)
    cep = models.CharField(max_length=9, blank=True)
    street = models.CharField(max_length=180, blank=True)
    number = models.CharField(max_length=20, blank=True)
    complement = models.CharField(max_length=120, blank=True)
    district = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=2, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("legal_name",)
        constraints = [
            models.CheckConstraint(
                check=~models.Q(slug=""),
                name="cp_tenant_slug_not_blank",
            ),
        ]
        indexes = [
            models.Index(fields=("status",), name="cp_tenant_status_idx"),
            models.Index(fields=("slug",), name="cp_tenant_slug_idx"),
            models.Index(fields=("company", "status"), name="cp_tenant_company_status_idx"),
        ]

    def __str__(self):
        return f"{self.legal_name} ({self.slug})"

    def save(self, *args, **kwargs):
        if self.status == self.STATUS_DELETED and self.deleted_at is None:
            self.deleted_at = timezone.now()
        if self.status != self.STATUS_DELETED:
            self.deleted_at = None
        super().save(*args, **kwargs)


class Plan(models.Model):
    TIER_STARTER = "STARTER"
    TIER_GROWTH = "GROWTH"
    TIER_ENTERPRISE = "ENTERPRISE"
    TIER_CHOICES = [
        (TIER_STARTER, "Starter"),
        (TIER_GROWTH, "Growth"),
        (TIER_ENTERPRISE, "Enterprise"),
    ]

    name = models.CharField(max_length=100, unique=True)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=("tier", "is_active"), name="cp_plan_tier_active_idx"),
        ]

    def __str__(self):
        return self.name


class PlanPrice(models.Model):
    ALLOWED_MONTHLY_PRICE = (150, 250, 350)
    ALLOWED_SETUP_FEE = (0, 150)

    plan = models.OneToOneField(
        Plan,
        on_delete=models.CASCADE,
        related_name="price",
    )
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    setup_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(monthly_price__in=[150, 250, 350]),
                name="cp_plan_price_monthly_allowed",
            ),
            models.CheckConstraint(
                check=models.Q(setup_fee__in=[0, 150]),
                name="cp_plan_price_setup_allowed",
            ),
        ]

    def __str__(self):
        return f"{self.plan.name}: {self.monthly_price}/m"

    def clean(self):
        super().clean()
        if float(self.monthly_price) not in self.ALLOWED_MONTHLY_PRICE:
            raise ValidationError(
                {"monthly_price": "monthly_price must be one of: 150, 250, 350."}
            )
        if float(self.setup_fee) not in self.ALLOWED_SETUP_FEE:
            raise ValidationError({"setup_fee": "setup_fee must be 0 or 150."})


class TenantPlanSubscription(models.Model):
    STATUS_ACTIVE = "ACTIVE"
    STATUS_SUSPENDED = "SUSPENDED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_DELETED = "DELETED"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_DELETED, "Deleted"),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    is_trial = models.BooleanField(default=False)
    trial_ends_at = models.DateField(null=True, blank=True)
    is_courtesy = models.BooleanField(default=False)
    setup_fee_override = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("tenant", "status"), name="cp_sub_tenant_status_idx"),
            models.Index(fields=("tenant", "start_date"), name="cp_sub_tenant_start_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__isnull=True) | models.Q(end_date__gte=models.F("start_date")),
                name="cp_tenant_sub_end_after_start",
            ),
            models.CheckConstraint(
                check=models.Q(setup_fee_override__isnull=True) | models.Q(setup_fee_override__gte=0),
                name="cp_tenant_sub_setup_fee_non_negative",
            ),
        ]

    def clean(self):
        super().clean()
        if self.is_trial and not self.trial_ends_at:
            raise ValidationError({"trial_ends_at": "trial_ends_at is required when is_trial=true."})
        if not self.is_trial and self.trial_ends_at:
            raise ValidationError(
                {"trial_ends_at": "trial_ends_at must be null when is_trial=false."}
            )
        if self.is_trial and self.trial_ends_at and self.trial_ends_at < self.start_date:
            raise ValidationError(
                {"trial_ends_at": "trial_ends_at must be greater than or equal to start_date."}
            )

    def __str__(self):
        return f"{self.tenant.slug} - {self.plan.name} ({self.status})"


class TenantStatusHistory(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    from_status = models.CharField(max_length=20, choices=Tenant.STATUS_CHOICES)
    to_status = models.CharField(max_length=20, choices=Tenant.STATUS_CHOICES)
    reason = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenant_status_changes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("tenant", "created_at"), name="cp_tsh_tenant_created_idx"),
            models.Index(fields=("to_status",), name="cp_tsh_to_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(from_status=models.F("to_status")),
                name="cp_tenant_status_hist_from_to_diff",
            ),
        ]

    def __str__(self):
        return f"{self.tenant.slug}: {self.from_status} -> {self.to_status}"


class ControlPanelAuditLog(models.Model):
    ACTION_LIST = "LIST"
    ACTION_RETRIEVE = "RETRIEVE"
    ACTION_CREATE = "CREATE"
    ACTION_UPDATE = "UPDATE"
    ACTION_SUSPEND = "SUSPEND"
    ACTION_UNSUSPEND = "UNSUSPEND"
    ACTION_SOFT_DELETE = "SOFT_DELETE"
    ACTION_CHOICES = [
        (ACTION_LIST, "List"),
        (ACTION_RETRIEVE, "Retrieve"),
        (ACTION_CREATE, "Create"),
        (ACTION_UPDATE, "Update"),
        (ACTION_SUSPEND, "Suspend"),
        (ACTION_UNSUSPEND, "Unsuspend"),
        (ACTION_SOFT_DELETE, "Soft delete"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="control_panel_audit_logs",
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    resource = models.CharField(max_length=80, default="tenant")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("tenant", "created_at"), name="cp_audit_tenant_created_idx"),
            models.Index(fields=("action", "created_at"), name="cp_audit_action_created_idx"),
        ]

    def __str__(self):
        tenant_slug = self.tenant.slug if self.tenant else "-"
        return f"{self.action} {self.resource} [{tenant_slug}]"


class AdminAuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_audit_events",
    )
    action = models.CharField(max_length=50)
    entity_type = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=80, blank=True)
    target_tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_audit_events",
    )
    before_data = models.JSONField(default=dict, blank=True)
    after_data = models.JSONField(default=dict, blank=True)
    correlation_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("target_tenant", "created_at"), name="cp_admin_audit_tenant_ts_idx"),
            models.Index(fields=("action", "created_at"), name="cp_admin_audit_action_ts_idx"),
            models.Index(fields=("entity_type", "entity_id"), name="cp_admin_audit_entity_idx"),
            models.Index(fields=("correlation_id",), name="cp_admin_audit_corr_idx"),
        ]

    def __str__(self):
        return f"{self.action} {self.entity_type}#{self.entity_id or '-'}"


class TenantInternalNote(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="internal_notes",
    )
    note = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenant_internal_notes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("tenant", "created_at"), name="cp_note_tenant_ts_idx"),
        ]

    def __str__(self):
        return f"Note #{self.id} for {self.tenant.slug}"


class FeatureFlag(models.Model):
    key = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=("is_active", "key"), name="cp_feature_active_key_idx"),
        ]

    def __str__(self):
        return self.key


class TenantFeatureFlag(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="feature_flags",
    )
    feature = models.ForeignKey(
        FeatureFlag,
        on_delete=models.CASCADE,
        related_name="tenant_flags",
    )
    enabled = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenant_feature_updates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("feature__name",)
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "feature"),
                name="cp_tenant_feature_unique",
            )
        ]
        indexes = [
            models.Index(fields=("tenant", "enabled"), name="cp_tenant_feature_enabled_idx"),
        ]

    def __str__(self):
        return f"{self.tenant.slug}:{self.feature.key}={self.enabled}"


class TenantContract(models.Model):
    PLAN_STARTER = "STARTER"
    PLAN_PRO = "PRO"
    PLAN_ENTERPRISE = "ENTERPRISE"
    PLAN_CHOICES = [
        (PLAN_STARTER, "Starter"),
        (PLAN_PRO, "Pro"),
        (PLAN_ENTERPRISE, "Enterprise"),
    ]

    STATUS_TRIAL = "TRIAL"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_SUSPENDED = "SUSPENDED"
    STATUS_CANCELED = "CANCELED"
    STATUS_CHOICES = [
        (STATUS_TRIAL, "Trial"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_CANCELED, "Canceled"),
    ]

    company = models.OneToOneField(
        "customers.Company",
        on_delete=models.CASCADE,
        related_name="contract",
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default=PLAN_STARTER)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIAL)
    seats = models.PositiveIntegerField(default=3)
    monthly_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("company__name",)
        verbose_name = "Tenant Contract"
        verbose_name_plural = "Tenant Contracts"

    def __str__(self):
        return f"{self.company.tenant_code} - {self.plan} ({self.status})"


class TenantContractDocument(models.Model):
    STATUS_DRAFT = "DRAFT"
    STATUS_SENT = "SENT"
    STATUS_SIGNED = "SIGNED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SENT, "Sent"),
        (STATUS_SIGNED, "Signed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    contract_version = models.PositiveIntegerField(default=1)
    snapshot_json = models.JSONField(default=dict)
    pdf_document_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("tenant", "status"), name="cp_contract_tenant_status_idx"),
            models.Index(fields=("tenant", "created_at"), name="cp_contract_tenant_created_idx"),
        ]

    def __str__(self):
        return f"Contract #{self.id} {self.tenant.slug} ({self.status})"


class ContractEmailLog(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_SENT = "SENT"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    ]

    contract = models.ForeignKey(
        TenantContractDocument,
        on_delete=models.CASCADE,
        related_name="email_logs",
    )
    to_email = models.EmailField()
    resend_message_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-id",)
        indexes = [
            models.Index(fields=("contract", "status"), name="cp_contract_email_status_idx"),
        ]

    def __str__(self):
        return f"ContractEmailLog #{self.id} ({self.status})"


class SystemHealthSnapshot(models.Model):
    service_name = models.CharField(max_length=100)
    status = models.CharField(max_length=30)
    latency_ms = models.FloatField(default=0)
    error_rate = models.FloatField(default=0)
    metadata_json = models.JSONField(default=dict, blank=True)
    captured_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-captured_at",)
        indexes = [
            models.Index(fields=("service_name", "captured_at"), name="cp_sys_health_service_ts_idx"),
            models.Index(fields=("status", "captured_at"), name="cp_sys_health_status_ts_idx"),
        ]

    def __str__(self):
        return f"{self.service_name} {self.status} @{self.captured_at.isoformat()}"


class TenantHealthSnapshot(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="health_snapshots",
    )
    last_seen_at = models.DateTimeField(null=True, blank=True)
    request_rate = models.FloatField(default=0)
    error_rate = models.FloatField(default=0)
    p95_latency = models.FloatField(default=0)
    jobs_pending = models.IntegerField(default=0)
    captured_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-captured_at",)
        indexes = [
            models.Index(fields=("tenant", "captured_at"), name="cp_tenant_health_tenant_ts_idx"),
            models.Index(fields=("captured_at",), name="cp_tenant_health_ts_idx"),
        ]

    def __str__(self):
        return f"{self.tenant.slug} health @{self.captured_at.isoformat()}"


class TenantOperationalSettings(models.Model):
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="operational_settings",
    )
    requests_per_minute = models.PositiveIntegerField(default=600)
    storage_limit_gb = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    docs_storage_limit_gb = models.DecimalField(max_digits=10, decimal_places=2, default=5)
    module_limits_json = models.JSONField(default=dict, blank=True)
    current_storage_gb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    current_docs_storage_gb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_storage_sync_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenant_operational_settings_updates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("tenant",), name="cp_ops_settings_tenant_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(requests_per_minute__gte=1),
                name="cp_ops_settings_rpm_positive",
            ),
            models.CheckConstraint(
                check=models.Q(storage_limit_gb__gte=0),
                name="cp_ops_settings_storage_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(docs_storage_limit_gb__gte=0),
                name="cp_ops_settings_docs_storage_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(current_storage_gb__gte=0),
                name="cp_ops_settings_current_storage_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(current_docs_storage_gb__gte=0),
                name="cp_ops_settings_current_docs_storage_non_negative",
            ),
        ]

    def __str__(self):
        return f"Ops settings {self.tenant.slug}"


class TenantIntegrationSecretRef(models.Model):
    PROVIDER_SMTP = "SMTP"
    PROVIDER_WHATSAPP = "WHATSAPP"
    PROVIDER_VERTEX_AI = "VERTEX_AI"
    PROVIDER_CUSTOM = "CUSTOM"
    PROVIDER_CHOICES = [
        (PROVIDER_SMTP, "SMTP"),
        (PROVIDER_WHATSAPP, "WhatsApp"),
        (PROVIDER_VERTEX_AI, "Vertex AI"),
        (PROVIDER_CUSTOM, "Custom"),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="integration_secrets",
    )
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES)
    alias = models.SlugField(max_length=80, default="default")
    secret_manager_ref = models.CharField(
        max_length=255,
        help_text="GCP Secret Manager reference, never store raw credentials.",
    )
    metadata_json = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenant_integration_secret_refs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "provider", "alias"),
                name="cp_tenant_integration_ref_unique",
            )
        ]
        indexes = [
            models.Index(fields=("tenant", "provider"), name="cp_int_tenant_provider_idx"),
            models.Index(fields=("tenant", "is_active"), name="cp_int_tenant_active_idx"),
        ]

    def __str__(self):
        return f"{self.tenant.slug}:{self.provider}:{self.alias}"


class TenantImpersonationSession(models.Model):
    STATUS_ACTIVE = "ACTIVE"
    STATUS_ENDED = "ENDED"
    STATUS_EXPIRED = "EXPIRED"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_ENDED, "Ended"),
        (STATUS_EXPIRED, "Expired"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tenant_impersonation_sessions",
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="impersonation_sessions",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    reason = models.CharField(max_length=255, blank=True)
    correlation_id = models.CharField(max_length=64, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=("tenant", "status"), name="cp_imp_tenant_status_idx"),
            models.Index(fields=("actor", "status"), name="cp_imp_actor_status_idx"),
            models.Index(fields=("expires_at",), name="cp_imp_expires_at_idx"),
        ]

    def __str__(self):
        return f"{self.actor_id}->{self.tenant.slug} ({self.status})"


class TenantAlertEvent(models.Model):
    TYPE_NO_HEARTBEAT = "NO_HEARTBEAT"
    TYPE_HIGH_ERROR_RATE = "HIGH_ERROR_RATE"
    TYPE_RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    TYPE_STORAGE_LIMIT_EXCEEDED = "STORAGE_LIMIT_EXCEEDED"
    TYPE_STORAGE_LIMIT_NEAR = "STORAGE_LIMIT_NEAR"
    TYPE_CHOICES = [
        (TYPE_NO_HEARTBEAT, "No heartbeat"),
        (TYPE_HIGH_ERROR_RATE, "High error rate"),
        (TYPE_RATE_LIMIT_EXCEEDED, "Rate limit exceeded"),
        (TYPE_STORAGE_LIMIT_EXCEEDED, "Storage limit exceeded"),
        (TYPE_STORAGE_LIMIT_NEAR, "Storage limit near threshold"),
    ]

    SEVERITY_INFO = "INFO"
    SEVERITY_WARNING = "WARNING"
    SEVERITY_CRITICAL = "CRITICAL"
    SEVERITY_CHOICES = [
        (SEVERITY_INFO, "Info"),
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_CRITICAL, "Critical"),
    ]

    STATUS_OPEN = "OPEN"
    STATUS_RESOLVED = "RESOLVED"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_RESOLVED, "Resolved"),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="alerts",
    )
    alert_type = models.CharField(max_length=40, choices=TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    message = models.TextField()
    metrics_json = models.JSONField(default=dict, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=("tenant", "status"), name="cp_alert_tenant_status_idx"),
            models.Index(fields=("alert_type", "status"), name="cp_alert_type_status_idx"),
            models.Index(fields=("last_seen_at",), name="cp_alert_last_seen_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "alert_type", "status"),
                name="cp_alert_unique_open_status",
            )
        ]

    def __str__(self):
        return f"{self.tenant.slug}:{self.alert_type}:{self.status}"


class TenantReleaseRecord(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="release_records",
    )
    backend_version = models.CharField(max_length=64)
    frontend_version = models.CharField(max_length=64, blank=True)
    git_sha = models.CharField(max_length=64, blank=True)
    source = models.CharField(max_length=32, default="cloud_run")
    changelog = models.TextField(blank=True)
    changelog_json = models.JSONField(default=list, blank=True)
    is_current = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenant_release_records",
    )
    deployed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-deployed_at", "-id")
        indexes = [
            models.Index(fields=("tenant", "is_current"), name="cp_release_tenant_current_idx"),
            models.Index(fields=("tenant", "deployed_at"), name="cp_release_tenant_deployed_idx"),
        ]

    def __str__(self):
        return f"{self.tenant.slug} backend={self.backend_version}"


class TenantProvisioning(models.Model):
    # Current target architecture (django-tenants): single Postgres database, one schema per tenant.
    ISOLATION_SCHEMA_PER_TENANT = "SCHEMA_PER_TENANT"

    # Legacy value kept for backward compatibility with earlier iterations.
    ISOLATION_SHARED_SCHEMA = "SHARED_SCHEMA"
    ISOLATION_DATABASE_PER_TENANT = "DATABASE_PER_TENANT"
    ISOLATION_CHOICES = [
        (ISOLATION_SCHEMA_PER_TENANT, "Shared DB / Schema per Tenant"),
        (ISOLATION_DATABASE_PER_TENANT, "Database per Tenant"),
        (ISOLATION_SHARED_SCHEMA, "Shared DB / Shared Schema (legacy)"),
    ]

    STATUS_PENDING = "PENDING"
    STATUS_PROVISIONING = "PROVISIONING"
    STATUS_READY = "READY"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROVISIONING, "Provisioning"),
        (STATUS_READY, "Ready"),
        (STATUS_FAILED, "Failed"),
    ]

    company = models.OneToOneField(
        "customers.Company",
        on_delete=models.CASCADE,
        related_name="provisioning",
    )
    isolation_model = models.CharField(
        max_length=30,
        choices=ISOLATION_CHOICES,
        default=ISOLATION_SCHEMA_PER_TENANT,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    database_alias = models.SlugField(max_length=63, unique=True)
    database_name = models.CharField(max_length=100)
    database_host = models.CharField(max_length=255, default="127.0.0.1")
    database_port = models.PositiveIntegerField(default=5432)
    database_user = models.CharField(max_length=100)
    database_password_secret = models.CharField(max_length=255, blank=True)
    portal_url = models.URLField(blank=True)
    provisioned_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("company__name",)
        verbose_name = "Tenant Provisioning"
        verbose_name_plural = "Tenant Provisioning"

    def __str__(self):
        return f"{self.company.tenant_code} [{self.status}]"
