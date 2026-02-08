from django.conf import settings
from rest_framework import serializers

from control_plane.models import TenantContract, TenantProvisioning
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
