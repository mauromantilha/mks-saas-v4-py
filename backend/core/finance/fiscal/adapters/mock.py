from __future__ import annotations

import itertools
from datetime import date
from typing import Any, Mapping
from uuid import uuid4

from .base import FiscalAdapterBase, FiscalAdapterError


class MockFiscalAdapter(FiscalAdapterBase):
    """In-memory mock adapter for local development and tests.

    Behavior:
    - `issue_invoice(...)` simulates immediate authorization, generating a fake
      series/number and a minimal XML payload.
    - `cancel_invoice(...)` flips status to CANCELLED for the mocked document.
    - `check_status(...)` returns the current mocked status.
    """

    _sequence = itertools.count(100000)
    _documents: dict[str, dict[str, Any]] = {}

    def __init__(self, *, series: str = "1") -> None:
        self.series = series

    def issue_invoice(self, data: Mapping[str, Any]) -> Mapping[str, Any]:
        document_id = f"mock:{uuid4().hex}"
        number = str(next(self._sequence))

        issue_date = data.get("issue_date") or date.today().isoformat()
        amount = data.get("amount")

        xml_content = (
            f"<NFe><infNFe><ide><serie>{self.series}</serie><nNF>{number}</nNF></ide>"
            f"<total><ICMSTot><vNF>{amount}</vNF></ICMSTot></total>"
            f"</infNFe></NFe>"
        )

        payload: dict[str, Any] = {
            "document_id": document_id,
            "status": "AUTHORIZED",
            "series": self.series,
            "number": number,
            "issue_date": issue_date,
            "xml_content": xml_content,
            "raw": {"mock": True},
        }
        self._documents[document_id] = payload
        return dict(payload)

    def cancel_invoice(self, document_id: str) -> Mapping[str, Any]:
        doc = self._documents.get(document_id)
        if not doc:
            raise FiscalAdapterError(f"Mock document not found: {document_id}")

        doc["status"] = "CANCELLED"
        return {"document_id": document_id, "status": doc["status"]}

    def check_status(self, document_id: str) -> Mapping[str, Any]:
        doc = self._documents.get(document_id)
        if not doc:
            raise FiscalAdapterError(f"Mock document not found: {document_id}")
        return {"document_id": document_id, "status": doc["status"]}

