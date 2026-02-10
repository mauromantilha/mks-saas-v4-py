from django.conf import settings
from rest_framework import serializers

from control_plane.models import (
    AdminAuditEvent,
    FeatureFlag,
    ContractEmailLog,
    Plan,
    PlanPrice,
    SystemHealthSnapshot,
    Tenant,
    TenantContractDocument,
    TenantFeatureFlag,
    TenantHealthSnapshot,
    TenantImpersonationSession,
    TenantIntegrationSecretRef,
    TenantInternalNote,
    TenantAlertEvent,
    TenantContract,
    TenantOperationalSettings,
    TenantPlanSubscription,
    TenantProvisioning,
    TenantReleaseRecord,
)
from customers.models import Company


class TenantContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantContract
        fields = (
            "plan",
            "status",
            "seats",
            "monthly_fee",
            "start_date",
            "end_date",
            "auto_renew",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class TenantProvisioningSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantProvisioning
        fields = (
            "isolation_model",
            "status",
            "database_alias",
            "database_name",
            "database_host",
            "database_port",
            "database_user",
            "database_password_secret",
            "portal_url",
            "provisioned_at",
            "last_error",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class TenantControlPlaneReadSerializer(serializers.ModelSerializer):
    contract = TenantContractSerializer(read_only=True)
    provisioning = TenantProvisioningSerializer(read_only=True)

    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "tenant_code",
            "subdomain",
            "is_active",
            "created_at",
            "updated_at",
            "contract",
            "provisioning",
        )


class TenantContractPayloadSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=TenantContract.PLAN_CHOICES, required=False)
    status = serializers.ChoiceField(choices=TenantContract.STATUS_CHOICES, required=False)
    seats = serializers.IntegerField(min_value=1, required=False)
    monthly_fee = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False, allow_null=True)
    auto_renew = serializers.BooleanField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class TenantProvisioningPayloadSerializer(serializers.Serializer):
    isolation_model = serializers.ChoiceField(
        choices=TenantProvisioning.ISOLATION_CHOICES,
        required=False,
    )
    status = serializers.ChoiceField(choices=TenantProvisioning.STATUS_CHOICES, required=False)
    database_alias = serializers.SlugField(max_length=63, required=False)
    database_name = serializers.CharField(max_length=100, required=False)
    database_host = serializers.CharField(max_length=255, required=False)
    database_port = serializers.IntegerField(min_value=1, max_value=65535, required=False)
    database_user = serializers.CharField(max_length=100, required=False)
    database_password_secret = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )
    portal_url = serializers.URLField(required=False, allow_blank=True)
    last_error = serializers.CharField(required=False, allow_blank=True)


class TenantControlPlaneCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    tenant_code = serializers.SlugField(max_length=63)
    subdomain = serializers.SlugField(max_length=63)
    is_active = serializers.BooleanField(default=True)
    contract = TenantContractPayloadSerializer(required=False)
    provisioning = TenantProvisioningPayloadSerializer(required=False)

    def validate_subdomain(self, value: str) -> str:
        subdomain = value.strip().lower()
        reserved = set(getattr(settings, "TENANT_RESERVED_SUBDOMAINS", []))
        if subdomain in reserved:
            raise serializers.ValidationError(
                f"Subdomain '{subdomain}' is reserved and cannot be used by tenants."
            )
        return subdomain


class TenantControlPlaneUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    subdomain = serializers.SlugField(max_length=63, required=False)
    is_active = serializers.BooleanField(required=False)
    contract = TenantContractPayloadSerializer(required=False)
    provisioning = TenantProvisioningPayloadSerializer(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Send at least one field to update.")
        return attrs

    def validate_subdomain(self, value: str) -> str:
        subdomain = value.strip().lower()
        reserved = set(getattr(settings, "TENANT_RESERVED_SUBDOMAINS", []))
        if subdomain in reserved:
            raise serializers.ValidationError(
                f"Subdomain '{subdomain}' is reserved and cannot be used by tenants."
            )
        return subdomain


class TenantProvisionActionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=TenantProvisioning.STATUS_CHOICES)
    portal_url = serializers.URLField(required=False, allow_blank=True)
    last_error = serializers.CharField(required=False, allow_blank=True)


class TenantProvisionExecuteSerializer(serializers.Serializer):
    portal_url = serializers.URLField(required=False, allow_blank=True)


class PlanPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanPrice
        fields = ("monthly_price", "setup_fee")


class PlanSerializer(serializers.ModelSerializer):
    price = PlanPriceSerializer(read_only=True)

    class Meta:
        model = Plan
        fields = ("id", "name", "tier", "is_active", "price")


class TenantPlanSubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=Plan.objects.filter(is_active=True),
        source="plan",
        write_only=True,
        required=False,
    )

    class Meta:
        model = TenantPlanSubscription
        fields = (
            "id",
            "plan",
            "plan_id",
            "start_date",
            "end_date",
            "is_trial",
            "trial_ends_at",
            "is_courtesy",
            "setup_fee_override",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class ControlPanelTenantSerializer(serializers.ModelSerializer):
    subscription = serializers.SerializerMethodField()
    company_id = serializers.IntegerField(read_only=True)
    last_status_reason = serializers.SerializerMethodField()
    last_status_changed_at = serializers.SerializerMethodField()
    limits = serializers.SerializerMethodField()
    current_release = serializers.SerializerMethodField()
    open_alerts_count = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = (
            "id",
            "company_id",
            "legal_name",
            "cnpj",
            "contact_email",
            "slug",
            "subdomain",
            "cep",
            "street",
            "number",
            "complement",
            "district",
            "city",
            "state",
            "status",
            "last_status_reason",
            "last_status_changed_at",
            "deleted_at",
            "created_at",
            "updated_at",
            "subscription",
            "limits",
            "current_release",
            "open_alerts_count",
        )
        read_only_fields = ("deleted_at", "created_at", "updated_at", "subscription")

    def get_subscription(self, obj: Tenant):
        subscription = (
            obj.subscriptions.select_related("plan", "plan__price")
            .order_by("-created_at")
            .first()
        )
        if not subscription:
            return None
        return TenantPlanSubscriptionSerializer(subscription).data

    def get_last_status_reason(self, obj: Tenant):
        latest = obj.status_history.order_by("-created_at").first()
        if not latest:
            return ""
        return latest.reason or ""

    def get_last_status_changed_at(self, obj: Tenant):
        latest = obj.status_history.order_by("-created_at").first()
        if not latest:
            return None
        return latest.created_at

    def get_limits(self, obj: Tenant):
        settings_obj = getattr(obj, "operational_settings", None)
        if settings_obj is None:
            return None
        return TenantOperationalSettingsSerializer(settings_obj).data

    def get_current_release(self, obj: Tenant):
        release = obj.release_records.filter(is_current=True).order_by("-deployed_at").first()
        if release is None:
            return None
        return TenantReleaseRecordSerializer(release).data

    def get_open_alerts_count(self, obj: Tenant):
        return obj.alerts.filter(status=TenantAlertEvent.STATUS_OPEN).count()


class ControlPanelTenantCreateSerializer(serializers.Serializer):
    legal_name = serializers.CharField(max_length=180)
    cnpj = serializers.CharField(max_length=18, required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    slug = serializers.SlugField(max_length=63)
    subdomain = serializers.SlugField(max_length=63)
    cep = serializers.CharField(max_length=9, required=False, allow_blank=True)
    street = serializers.CharField(max_length=180, required=False, allow_blank=True)
    number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    complement = serializers.CharField(max_length=120, required=False, allow_blank=True)
    district = serializers.CharField(max_length=120, required=False, allow_blank=True)
    city = serializers.CharField(max_length=120, required=False, allow_blank=True)
    state = serializers.CharField(max_length=2, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Tenant.STATUS_CHOICES, required=False)
    subscription = TenantPlanSubscriptionSerializer(required=False)


class ControlPanelTenantUpdateSerializer(serializers.Serializer):
    legal_name = serializers.CharField(max_length=180, required=False)
    cnpj = serializers.CharField(max_length=18, required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    slug = serializers.SlugField(max_length=63, required=False)
    subdomain = serializers.SlugField(max_length=63, required=False)
    cep = serializers.CharField(max_length=9, required=False, allow_blank=True)
    street = serializers.CharField(max_length=180, required=False, allow_blank=True)
    number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    complement = serializers.CharField(max_length=120, required=False, allow_blank=True)
    district = serializers.CharField(max_length=120, required=False, allow_blank=True)
    city = serializers.CharField(max_length=120, required=False, allow_blank=True)
    state = serializers.CharField(max_length=2, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Tenant.STATUS_CHOICES, required=False)
    subscription = TenantPlanSubscriptionSerializer(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Send at least one field to update.")
        return attrs


class TenantStatusActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)


class TenantSoftDeleteActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)
    confirm_text = serializers.CharField()

    def validate_confirm_text(self, value):
        if value.strip().upper() != "DELETE":
            raise serializers.ValidationError('confirm_text must be exactly "DELETE".')
        return value.strip().upper()


class TenantContractDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantContractDocument
        fields = (
            "id",
            "tenant",
            "status",
            "contract_version",
            "snapshot_json",
            "pdf_document_id",
            "created_at",
        )
        read_only_fields = fields


class ContractEmailLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractEmailLog
        fields = (
            "id",
            "to_email",
            "resend_message_id",
            "status",
            "error",
            "sent_at",
        )
        read_only_fields = fields


class ContractSendSerializer(serializers.Serializer):
    to_email = serializers.EmailField()
    force_send = serializers.BooleanField(default=False)


class PlanWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    tier = serializers.ChoiceField(choices=Plan.TIER_CHOICES)
    is_active = serializers.BooleanField(default=True)
    monthly_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    setup_fee = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_monthly_price(self, value):
        if float(value) not in PlanPrice.ALLOWED_MONTHLY_PRICE:
            raise serializers.ValidationError("monthly_price must be one of 150, 250, 350.")
        return value

    def validate_setup_fee(self, value):
        if float(value) not in PlanPrice.ALLOWED_SETUP_FEE:
            raise serializers.ValidationError("setup_fee must be 0 or 150.")
        return value


class TenantSubscriptionChangeSerializer(serializers.Serializer):
    plan_id = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.filter(is_active=True), source="plan")
    is_trial = serializers.BooleanField(default=False)
    trial_days = serializers.IntegerField(required=False, min_value=1, max_value=90)
    is_courtesy = serializers.BooleanField(default=False)
    setup_fee_override = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
    )

    def validate_setup_fee_override(self, value):
        if value is None:
            return value
        if float(value) not in PlanPrice.ALLOWED_SETUP_FEE:
            raise serializers.ValidationError("setup_fee_override must be 0 or 150 when provided.")
        return value

    def validate(self, attrs):
        is_trial = attrs.get("is_trial", False)
        trial_days = attrs.get("trial_days")
        if is_trial and not trial_days:
            raise serializers.ValidationError({"trial_days": "trial_days is required when is_trial=true."})
        if not is_trial and trial_days:
            raise serializers.ValidationError({"trial_days": "trial_days is only allowed when is_trial=true."})
        return attrs


class SystemHealthSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemHealthSnapshot
        fields = (
            "id",
            "service_name",
            "status",
            "latency_ms",
            "error_rate",
            "metadata_json",
            "captured_at",
        )
        read_only_fields = fields


class TenantHealthSnapshotSerializer(serializers.ModelSerializer):
    tenant_id = serializers.IntegerField(read_only=True)
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    tenant_name = serializers.CharField(source="tenant.legal_name", read_only=True)

    class Meta:
        model = TenantHealthSnapshot
        fields = (
            "id",
            "tenant_id",
            "tenant_slug",
            "tenant_name",
            "last_seen_at",
            "request_rate",
            "error_rate",
            "p95_latency",
            "jobs_pending",
            "captured_at",
        )
        read_only_fields = fields


class AdminAuditEventSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)
    target_tenant_slug = serializers.CharField(source="target_tenant.slug", read_only=True)

    class Meta:
        model = AdminAuditEvent
        fields = (
            "id",
            "actor",
            "actor_username",
            "action",
            "entity_type",
            "entity_id",
            "target_tenant",
            "target_tenant_slug",
            "before_data",
            "after_data",
            "correlation_id",
            "created_at",
        )
        read_only_fields = fields


class TenantInternalNoteSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = TenantInternalNote
        fields = (
            "id",
            "tenant",
            "note",
            "created_by",
            "created_by_username",
            "created_at",
        )
        read_only_fields = ("id", "tenant", "created_by", "created_by_username", "created_at")


class TenantInternalNoteWriteSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=4000)


class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = (
            "id",
            "key",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class TenantFeatureFlagSerializer(serializers.ModelSerializer):
    feature = FeatureFlagSerializer(read_only=True)
    updated_by_username = serializers.CharField(source="updated_by.username", read_only=True)

    class Meta:
        model = TenantFeatureFlag
        fields = (
            "id",
            "tenant",
            "feature",
            "enabled",
            "updated_by",
            "updated_by_username",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "tenant",
            "feature",
            "updated_by",
            "updated_by_username",
            "created_at",
            "updated_at",
        )


class TenantFeatureFlagWriteSerializer(serializers.Serializer):
    feature_key = serializers.SlugField(max_length=80)
    enabled = serializers.BooleanField()


class TenantOperationalSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantOperationalSettings
        fields = (
            "tenant",
            "requests_per_minute",
            "storage_limit_gb",
            "docs_storage_limit_gb",
            "module_limits_json",
            "current_storage_gb",
            "current_docs_storage_gb",
            "last_storage_sync_at",
            "updated_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("tenant", "updated_by", "created_at", "updated_at")


class TenantOperationalSettingsWriteSerializer(serializers.Serializer):
    requests_per_minute = serializers.IntegerField(min_value=1, required=False)
    storage_limit_gb = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    docs_storage_limit_gb = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False
    )
    module_limits_json = serializers.JSONField(required=False)
    current_storage_gb = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    current_docs_storage_gb = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False
    )
    last_storage_sync_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_module_limits_json(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("module_limits_json must be an object.")
        return value


class TenantIntegrationSecretRefSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = TenantIntegrationSecretRef
        fields = (
            "id",
            "tenant",
            "provider",
            "alias",
            "secret_manager_ref",
            "metadata_json",
            "is_active",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "tenant",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        )


class TenantIntegrationSecretRefWriteSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=TenantIntegrationSecretRef.PROVIDER_CHOICES)
    alias = serializers.SlugField(max_length=80, default="default")
    secret_manager_ref = serializers.CharField(max_length=255)
    metadata_json = serializers.JSONField(required=False)
    is_active = serializers.BooleanField(default=True)

    def validate_secret_manager_ref(self, value: str):
        normalized = (value or "").strip()
        if "/secrets/" not in normalized:
            raise serializers.ValidationError(
                "Use a GCP Secret Manager reference (projects/<project>/secrets/<name>[/versions/<v>])."
            )
        return normalized

    def validate_metadata_json(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata_json must be an object.")
        return value


class TenantImpersonationStartSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)
    duration_minutes = serializers.IntegerField(required=False, min_value=5, max_value=240, default=30)


class TenantImpersonationStopSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(required=False, min_value=1)


class TenantImpersonationSessionSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)

    class Meta:
        model = TenantImpersonationSession
        fields = (
            "id",
            "actor",
            "actor_username",
            "tenant",
            "status",
            "reason",
            "correlation_id",
            "started_at",
            "expires_at",
            "ended_at",
        )
        read_only_fields = fields


class TenantAlertEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantAlertEvent
        fields = (
            "id",
            "tenant",
            "alert_type",
            "severity",
            "status",
            "message",
            "metrics_json",
            "first_seen_at",
            "last_seen_at",
            "resolved_at",
        )
        read_only_fields = fields


class TenantAlertResolveSerializer(serializers.Serializer):
    alert_id = serializers.IntegerField(min_value=1)


class TenantReleaseRecordSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = TenantReleaseRecord
        fields = (
            "id",
            "tenant",
            "backend_version",
            "frontend_version",
            "git_sha",
            "source",
            "changelog",
            "changelog_json",
            "is_current",
            "created_by",
            "created_by_username",
            "deployed_at",
            "created_at",
        )
        read_only_fields = (
            "id",
            "tenant",
            "created_by",
            "created_by_username",
            "created_at",
        )


class TenantReleaseRecordWriteSerializer(serializers.Serializer):
    backend_version = serializers.CharField(max_length=64)
    frontend_version = serializers.CharField(max_length=64, required=False, allow_blank=True)
    git_sha = serializers.CharField(max_length=64, required=False, allow_blank=True)
    source = serializers.CharField(max_length=32, required=False, allow_blank=True)
    changelog = serializers.CharField(required=False, allow_blank=True)
    changelog_json = serializers.JSONField(required=False)
    deployed_at = serializers.DateTimeField(required=False)
    is_current = serializers.BooleanField(default=True)

    def validate_changelog_json(self, value):
        if not isinstance(value, (list, dict)):
            raise serializers.ValidationError("changelog_json must be a list or object.")
        return value


class MonitoringHeartbeatSerializer(serializers.Serializer):
    service_name = serializers.CharField(max_length=100)
    status = serializers.CharField(max_length=30)
    latency_ms = serializers.FloatField(min_value=0, required=False, default=0)
    error_rate = serializers.FloatField(min_value=0, required=False, default=0)
    metadata_json = serializers.JSONField(required=False)
    tenant_id = serializers.IntegerField(required=False)
    tenant_slug = serializers.SlugField(required=False)
    last_seen_at = serializers.DateTimeField(required=False)
    request_rate = serializers.FloatField(min_value=0, required=False, default=0)
    p95_latency = serializers.FloatField(min_value=0, required=False, default=0)
    jobs_pending = serializers.IntegerField(min_value=0, required=False, default=0)

    def validate_metadata_json(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata_json must be an object.")
        return value

    def validate(self, attrs):
        if attrs.get("tenant_id") and attrs.get("tenant_slug"):
            raise serializers.ValidationError(
                "Use either tenant_id or tenant_slug, not both."
            )
        return attrs
