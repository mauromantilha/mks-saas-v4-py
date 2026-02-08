from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from tenancy.rbac import validate_rbac_overrides_schema


class Company(models.Model):
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
        try:
            validate_rbac_overrides_schema(self.rbac_overrides)
        except ValidationError as exc:
            try:
                detail = exc.message_dict
            except (AttributeError, TypeError):
                detail = exc.messages
            raise ValidationError(detail) from exc


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
