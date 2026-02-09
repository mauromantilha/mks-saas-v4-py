from __future__ import annotations

from datetime import date
from decimal import Decimal


def mock_invoice_resolver(*, invoice_id: int, company_id: int):
    """Local/dev invoice resolver for fiscal issuance.

    This keeps the fiscal bounded context decoupled from the (future) finance Invoice model.
    Use in development only by setting:
      FISCAL_INVOICE_RESOLVER=finance.fiscal.resolvers.mock.mock_invoice_resolver
    """

    # Deterministic fake values based on invoice_id.
    invoice_id_int = int(invoice_id)
    amount = Decimal("100.00") + Decimal(str(invoice_id_int % 97))

    return {
        "invoice_id": invoice_id_int,
        "status": "PAID",
        "amount": amount,
        "issue_date": date.today().isoformat(),
        "currency": "BRL",
        "customer": {
            "name": f"Cliente {invoice_id_int}",
            "cpf_cnpj": "123.456.789-09",
            "address": f"Rua Fiscal, {invoice_id_int % 999} - Centro - Sao Paulo/SP",
        },
        "items": [
            {
                "description": "Servico de corretagem",
                "quantity": 1,
                "unit_price": str(amount),
            }
        ],
    }

