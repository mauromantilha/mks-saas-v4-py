from __future__ import annotations

import logging

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ledger.models import LedgerEntry
from ledger.services import append_ledger_entry
from finance.fiscal.api.serializers.fiscal_config import (
    TenantFiscalConfigReadSerializer,
    TenantFiscalConfigUpsertSerializer,
    resolve_provider,
)
from finance.fiscal.crypto import encrypt_token
from finance.fiscal.models import TenantFiscalConfig
from tenancy.permissions import IsTenantRoleAllowed

logger = logging.getLogger(__name__)


class TenantFiscalConfigUpsertAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "fiscal_config"

    def post(self, request):
        company = getattr(request, "company", None)
        if company is None:
            return Response(
                {"detail": "Tenant context is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TenantFiscalConfigUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provider = resolve_provider(provider_value=serializer.validated_data["provider"])
        environment = serializer.validated_data["environment"]
        token_plain = serializer.validated_data.get("token", "") or ""

        logger.info(
            "fiscal.config.upsert.started company_id=%s provider_type=%s environment=%s",
            company.id,
            provider.provider_type,
            environment,
        )

        encrypted = encrypt_token(token_plain) if token_plain else ""

        with transaction.atomic():
            previous = (
                TenantFiscalConfig.all_objects.filter(company=company, active=True)
                .select_related("provider")
                .first()
            )
            before_payload = None
            if previous is not None:
                before_payload = {
                    "id": previous.id,
                    "provider_type": previous.provider.provider_type,
                    "environment": previous.environment,
                    "active": previous.active,
                }

            # Ensure single active per tenant: deactivate all, then activate the chosen config.
            TenantFiscalConfig.all_objects.filter(company=company).update(active=False)

            defaults = {
                "environment": environment,
                "active": True,
            }
            if encrypted:
                defaults["api_token"] = encrypted

            config, created = TenantFiscalConfig.all_objects.update_or_create(
                company=company,
                provider=provider,
                defaults=defaults,
            )

            append_ledger_entry(
                scope=LedgerEntry.SCOPE_TENANT,
                company=company,
                actor=request.user,
                action=LedgerEntry.ACTION_CREATE if created else LedgerEntry.ACTION_UPDATE,
                resource_label=TenantFiscalConfig._meta.label,
                resource_pk=str(config.id),
                request=request,
                event_type="finance.fiscal.config.upsert",
                data_before=before_payload,
                data_after={
                    "id": config.id,
                    "provider_type": provider.provider_type,
                    "environment": config.environment,
                    "active": config.active,
                },
                metadata={"tenant_resource_key": "fiscal_config"},
            )

        logger.info(
            "fiscal.config.upsert.completed company_id=%s config_id=%s provider_type=%s",
            company.id,
            config.id,
            provider.provider_type,
        )

        return Response(
            TenantFiscalConfigReadSerializer(config).data,
            status=status.HTTP_201_CREATED,
        )

