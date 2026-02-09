from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist

from finance.fiscal.models import TenantFiscalConfig

from .base import FiscalAdapterBase, FiscalAdapterError
from .mock import MockFiscalAdapter


class FiscalAdapterNotConfigured(FiscalAdapterError):
    """Raised when a tenant has no active fiscal provider configuration."""


class FiscalAdapterNotSupported(FiscalAdapterError):
    """Raised when provider_type has no registered adapter implementation."""


def get_fiscal_adapter(tenant_id: int) -> FiscalAdapterBase:
    """Return the configured fiscal adapter for a tenant.

    Args:
        tenant_id: Tenant/company ID.

    Returns:
        A concrete `FiscalAdapterBase` implementation.
    """

    try:
        config = (
            TenantFiscalConfig.all_objects.select_related("provider")
            .only(
                "id",
                "company_id",
                "active",
                "environment",
                "api_token",
                "provider__provider_type",
                "provider__api_base_url",
                "provider__name",
            )
            .get(company_id=tenant_id, active=True)
        )
    except ObjectDoesNotExist as exc:
        raise FiscalAdapterNotConfigured(
            f"Tenant {tenant_id} has no active fiscal configuration."
        ) from exc
    except TenantFiscalConfig.MultipleObjectsReturned as exc:
        raise FiscalAdapterError(
            f"Tenant {tenant_id} has multiple active fiscal configurations."
        ) from exc

    provider_type = (config.provider.provider_type or "").strip().lower()

    # Local-only adapter (for dev/tests).
    if provider_type in {"mock", "dummy", "local"}:
        return MockFiscalAdapter()

    raise FiscalAdapterNotSupported(
        f"Unsupported provider_type={config.provider.provider_type!r} for tenant={tenant_id}."
    )

