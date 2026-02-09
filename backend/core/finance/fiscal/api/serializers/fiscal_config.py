from __future__ import annotations

from rest_framework import serializers

from finance.fiscal.models import FiscalProvider, TenantFiscalConfig


class TenantFiscalConfigUpsertSerializer(serializers.Serializer):
    provider = serializers.CharField()
    token = serializers.CharField(allow_blank=True, required=False, default="")
    environment = serializers.ChoiceField(choices=TenantFiscalConfig.Environment.choices)


class TenantFiscalConfigReadSerializer(serializers.ModelSerializer):
    provider_type = serializers.CharField(source="provider.provider_type", read_only=True)
    provider_name = serializers.CharField(source="provider.name", read_only=True)
    has_token = serializers.SerializerMethodField()

    class Meta:
        model = TenantFiscalConfig
        fields = (
            "id",
            "provider",
            "provider_type",
            "provider_name",
            "environment",
            "active",
            "has_token",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_has_token(self, obj: TenantFiscalConfig) -> bool:
        return bool((obj.api_token or "").strip())


def resolve_provider(*, provider_value: str) -> FiscalProvider:
    raw = (provider_value or "").strip()
    if not raw:
        raise serializers.ValidationError({"provider": "This field is required."})

    # Allow passing provider id (int) or provider_type (string).
    if raw.isdigit():
        provider = FiscalProvider.objects.filter(id=int(raw)).first()
        if provider is None:
            raise serializers.ValidationError({"provider": "Provider not found."})
        return provider

    provider_type = raw.lower()
    provider, _created = FiscalProvider.objects.get_or_create(
        provider_type=provider_type,
        defaults={
            "name": provider_type,
            "api_base_url": "",
        },
    )
    return provider

