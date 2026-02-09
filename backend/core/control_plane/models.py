from django.db import models
from django.utils import timezone


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
