import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db import connection
from django.core.validators import MaxValueValidator, MinValueValidator

from django_tenants.models import DomainMixin, TenantMixin

from tenancy.rbac import validate_rbac_overrides_schema


def _normalize_schema_name(value: str) -> str:
    """Normalize tenant code into a safe, deterministic postgres schema name."""

    normalized = (value or "").strip().lower()
    normalized = re.sub(r"[^a-z0-9_-]+", "-", normalized).strip("-")
    return normalized[:63] if normalized else normalized


class Company(TenantMixin):
    # Keep tenant schema creation enabled by default. For production, you may want
    # to provision asynchronously by setting `auto_create_schema = False` and
    # calling `company.create_schema()` from a job.
    auto_create_schema = True

    name = models.CharField(max_length=150)
    tenant_code = models.SlugField(
        max_length=63,
        unique=True,
        help_text="Identifier used in the X-Tenant-ID header.",
    )
    subdomain = models.SlugField(
        max_length=63,
        unique=True,
        help_text="Tenant subdomain used for host-based tenant resolution.",
    )
    is_active = models.BooleanField(default=True)
    rbac_overrides = models.JSONField(
        default=dict,
        blank=True,
        validators=[validate_rbac_overrides_schema],
        help_text=(
            "Optional tenant RBAC overrides. "
            "Example: {'apolices': {'POST': ['OWNER', 'MANAGER']}}"
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "Company"
        verbose_name_plural = "Companies"

    def __str__(self):
        return f"{self.name} ({self.tenant_code})"

    def clean(self):
        super().clean()

        if not self.schema_name:
            self.schema_name = _normalize_schema_name(self.tenant_code)
        if self.schema_name == "public":
            raise ValidationError({"tenant_code": "tenant_code cannot map to the public schema."})

        try:
            validate_rbac_overrides_schema(self.rbac_overrides)
        except ValidationError as exc:
            try:
                detail = exc.message_dict
            except (AttributeError, TypeError):
                detail = exc.messages
            raise ValidationError(detail) from exc

    def save(self, *args, **kwargs):
        # Ensure schema_name is always set (TenantMixin requires it).
        if not getattr(self, "schema_name", ""):
            self.schema_name = _normalize_schema_name(self.tenant_code)

        # When django-tenants is disabled (sqlite/legacy), we must bypass TenantMixin.save,
        # because it queries postgres catalogs to create/check schemas.
        if not getattr(settings, "DJANGO_TENANTS_ENABLED", False) or connection.vendor != "postgresql":
            return models.Model.save(self, *args, **kwargs)

        return super().save(*args, **kwargs)


class Domain(DomainMixin):
    """Tenant domain mapping for django-tenants.

    Examples:
    - acme.mksbrasil.com
    - acme.localhost (dev)
    """

    class Meta:
        verbose_name = "Tenant Domain"
        verbose_name_plural = "Tenant Domains"


class CompanyMembership(models.Model):
    ROLE_MEMBER = "MEMBER"
    ROLE_MANAGER = "MANAGER"
    ROLE_OWNER = "OWNER"
    ROLE_CHOICES = [
        (ROLE_MEMBER, "Member"),
        (ROLE_MANAGER, "Manager"),
        (ROLE_OWNER, "Owner"),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="company_memberships",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("company__name", "user__username")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "user"),
                name="uq_company_membership_company_user",
            ),
        ]
        verbose_name = "Company Membership"
        verbose_name_plural = "Company Memberships"

    def __str__(self):
        return f"{self.user} @ {self.company} ({self.role})"


class ProducerProfile(models.Model):
    ACCOUNT_CHECKING = "CHECKING"
    ACCOUNT_SAVINGS = "SAVINGS"
    ACCOUNT_PAYMENT = "PAYMENT"
    ACCOUNT_TYPE_CHOICES = [
        (ACCOUNT_CHECKING, "Conta Corrente"),
        (ACCOUNT_SAVINGS, "Conta Poupança"),
        (ACCOUNT_PAYMENT, "Conta Pagamento"),
    ]

    PIX_CPF = "CPF"
    PIX_CNPJ = "CNPJ"
    PIX_EMAIL = "EMAIL"
    PIX_PHONE = "PHONE"
    PIX_RANDOM = "RANDOM"
    PIX_KEY_TYPE_CHOICES = [
        (PIX_CPF, "CPF"),
        (PIX_CNPJ, "CNPJ"),
        (PIX_EMAIL, "Email"),
        (PIX_PHONE, "Telefone"),
        (PIX_RANDOM, "Chave Aleatória"),
    ]

    company = models.ForeignKey(
        Company,
        related_name="producer_profiles",
        on_delete=models.CASCADE,
    )
    membership = models.OneToOneField(
        CompanyMembership,
        related_name="producer_profile",
        on_delete=models.CASCADE,
    )
    full_name = models.CharField(max_length=255)
    cpf = models.CharField(max_length=14)
    team_name = models.CharField(max_length=120, blank=True)
    is_team_manager = models.BooleanField(default=False)

    zip_code = models.CharField(max_length=12, blank=True)
    state = models.CharField(max_length=60, blank=True)
    city = models.CharField(max_length=120, blank=True)
    neighborhood = models.CharField(max_length=120, blank=True)
    street = models.CharField(max_length=255, blank=True)
    street_number = models.CharField(max_length=30, blank=True)
    address_complement = models.CharField(max_length=120, blank=True)

    commission_transfer_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentual do repasse sobre a comissão da empresa.",
    )
    payout_hold_days = models.PositiveSmallIntegerField(default=3)

    bank_code = models.CharField(max_length=4, blank=True)
    bank_name = models.CharField(max_length=120, blank=True)
    bank_agency = models.CharField(max_length=20, blank=True)
    bank_account = models.CharField(max_length=30, blank=True)
    bank_account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPE_CHOICES,
        blank=True,
    )
    pix_key_type = models.CharField(
        max_length=20,
        choices=PIX_KEY_TYPE_CHOICES,
        blank=True,
    )
    pix_key = models.CharField(max_length=140, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("full_name",)
        constraints = [
            models.UniqueConstraint(
                fields=("company", "cpf"),
                name="uq_producer_profile_company_cpf",
            ),
        ]

    def clean(self):
        super().clean()
        if self.membership_id and self.membership.company_id != self.company_id:
            raise ValidationError("Producer profile must belong to the same company as membership.")

    def save(self, *args, **kwargs):
        if self.membership_id and self.company_id is None:
            self.company = self.membership.company
        return super().save(*args, **kwargs)


class TenantEmailConfig(models.Model):
    TEST_STATUS_SUCCESS = "SUCCESS"
    TEST_STATUS_FAILED = "FAILED"
    TEST_STATUS_CHOICES = [
        (TEST_STATUS_SUCCESS, "Success"),
        (TEST_STATUS_FAILED, "Failed"),
    ]

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="email_config",
    )
    smtp_host = models.CharField(max_length=255)
    smtp_port = models.PositiveIntegerField(
        default=587,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
    )
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    smtp_use_ssl = models.BooleanField(default=False)
    default_from_email = models.EmailField(blank=True)
    default_from_name = models.CharField(max_length=150, blank=True)
    reply_to_email = models.EmailField(blank=True)
    is_enabled = models.BooleanField(default=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(
        max_length=20,
        choices=TEST_STATUS_CHOICES,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("company__name",)
        verbose_name = "Tenant Email Config"
        verbose_name_plural = "Tenant Email Configs"

    def clean(self):
        super().clean()
        if self.smtp_use_tls and self.smtp_use_ssl:
            raise ValidationError(
                {"smtp_use_ssl": "SSL and TLS cannot be enabled together."}
            )

    def __str__(self):
        return f"Email config for {self.company.tenant_code}"
