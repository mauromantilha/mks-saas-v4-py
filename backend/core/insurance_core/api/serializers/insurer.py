from __future__ import annotations

from rest_framework import serializers

from insurance_core.models import Insurer
from tenancy.context import get_current_company


class InsurerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insurer
        fields = (
            "id",
            "name",
            "legal_name",
            "cnpj",
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

