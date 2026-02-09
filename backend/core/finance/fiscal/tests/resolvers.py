from __future__ import annotations

from typing import Any, Mapping


def mock_invoice_resolver(*, invoice_id: int, company_id: int) -> Mapping[str, Any]:
    """Resolve an invoice for fiscal issuance in tests.

    This keeps finance.fiscal decoupled from a concrete finance Invoice model while
    allowing end-to-end API tests with the MockFiscalAdapter.
    """

    return {
        "invoice_id": invoice_id,
        "amount": f"{invoice_id}.00",
        "issue_date": "2026-02-09",
        "currency": "BRL",
        "customer": {
            "name": f"Cliente {company_id}",
            "cpf_cnpj": "123.456.789-09",
            "address": "Rua X, 123 - Centro - Sao Paulo/SP",
        },
        "items": [
            {"description": "Servico", "amount": f"{invoice_id}.00"},
        ],
    }

