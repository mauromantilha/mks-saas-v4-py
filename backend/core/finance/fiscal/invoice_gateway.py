from __future__ import annotations

from typing import Any, Mapping

from django.conf import settings
from django.utils.module_loading import import_string


class InvoiceGatewayError(RuntimeError):
    """Base error for invoice gateway/resolution failures."""


class InvoiceResolverNotConfigured(InvoiceGatewayError):
    """Raised when no invoice resolver is configured for fiscal issuance."""


def resolve_invoice_for_fiscal(*, invoice_id: int, company_id: int) -> Mapping[str, Any]:
    """Resolve an invoice into a provider-agnostic payload for fiscal issuance.

    This function keeps the fiscal bounded context decoupled from the finance
    "Invoice" model. The concrete implementation must live in the finance context
    (or another integration layer) and be configured via Django settings.

    Expected returned mapping (minimum):
    - invoice_id: int
    - amount: Decimal|str|int|float
    - issue_date: date|str|None (optional)
    - currency: str (optional; default "BRL")
    - customer: {
        "name": str,
        "cpf_cnpj": str,
        "address": str,  # free-form address snapshot
      }
    - items: list[dict] (optional; for adapters that require itemization)

    Settings:
    - FISCAL_INVOICE_RESOLVER: dotted path to a callable with signature:
        resolver(invoice_id: int, company_id: int) -> Mapping[str, Any]
    """

    resolver_path = (getattr(settings, "FISCAL_INVOICE_RESOLVER", "") or "").strip()
    if not resolver_path:
        raise InvoiceResolverNotConfigured(
            "FISCAL_INVOICE_RESOLVER is not configured. "
            "Provide a resolver callable to fetch/normalize invoice data."
        )

    resolver = import_string(resolver_path)
    return resolver(invoice_id=invoice_id, company_id=company_id)

