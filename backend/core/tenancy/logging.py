from __future__ import annotations

import logging
import re
from typing import Any


_CNPJ_RE = re.compile(
    r"(?<!\d)(?:\d{14}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})(?!\d)"
)
_CPF_RE = re.compile(r"(?<!\d)(?:\d{11}|\d{3}\.\d{3}\.\d{3}-\d{2})(?!\d)")


def mask_cpf_cnpj(text: str) -> str:
    """Mask CPF/CNPJ patterns in a string.

    We intentionally do not keep any digits in logs to reduce accidental leakage.
    """

    if not text:
        return text

    text = _CNPJ_RE.sub("***CNPJ***", text)
    text = _CPF_RE.sub("***CPF***", text)
    return text


class MaskCPFCNPJFilter(logging.Filter):
    """Logging filter to mask CPF/CNPJ in log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover
            message = str(getattr(record, "msg", ""))

        masked = mask_cpf_cnpj(str(message))

        # Replace the formatted message and clear args to avoid double formatting.
        record.msg = masked
        record.args = ()

        # Best-effort: mask common extra fields if present.
        for key in ("cpf", "cnpj", "cpf_cnpj"):
            if hasattr(record, key):
                value: Any = getattr(record, key)
                if isinstance(value, str):
                    setattr(record, key, mask_cpf_cnpj(value))

        return True

