from __future__ import annotations

from rest_framework import serializers

from insurance_core.models import Insurer, InsurerContact
from tenancy.context import get_current_company


class InsurerContactSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = InsurerContact
        fields = (
            "id",
            "name",
            "email",
            "phone",
            "role",
            "is_primary",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "created_at",
            "updated_at",
        )


class InsurerSerializer(serializers.ModelSerializer):
    contacts = InsurerContactSerializer(many=True, required=False)

    class Meta:
        model = Insurer
        fields = (
            "id",
            "name",
            "legal_name",
            "cnpj",
            "zip_code",
            "state",
            "city",
            "neighborhood",
            "street",
            "street_number",
            "address_complement",
            "contacts",
            "status",
            "integration_type",
            "integration_config",
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "ai_insights",
            "created_at",
            "updated_at",
        )

    def validate_name(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("name is required.")
        return value

    def validate_contacts(self, value):
        if not value:
            return value
        primary_count = sum(bool(item.get("is_primary")) for item in value)
        if primary_count > 1:
            raise serializers.ValidationError("Only one contact can be marked as primary.")
        return value

    def validate(self, attrs):
        company = (
            self.context.get("company")
            or getattr(self.context.get("request"), "company", None)
            or get_current_company()
        )
        name = (attrs.get("name") or getattr(self.instance, "name", "") or "").strip()
        if company and name:
            qs = Insurer.all_objects.filter(company=company, name=name)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"name": "Insurer name must be unique within the tenant."}
                )
        return attrs
