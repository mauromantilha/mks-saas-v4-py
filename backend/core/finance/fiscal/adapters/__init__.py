"""Fiscal provider adapters (provider-agnostic interface + implementations).

Adapters are responsible for talking to external fiscal emission providers.
They should not depend on the rest of the finance domain model besides the
minimal payload required to issue/cancel/check documents.
"""

from .base import (
    FiscalAdapterBase,
    FiscalAdapterError,
    FiscalAdapterFiscalRejectionError,
    FiscalAdapterTechnicalError,
    FiscalAdapterTimeoutError,
)
from .factory import (
    FiscalAdapterNotConfigured,
    FiscalAdapterNotSupported,
    get_fiscal_adapter,
)
from .mock import MockFiscalAdapter

__all__ = [
    "FiscalAdapterBase",
    "FiscalAdapterError",
    "FiscalAdapterFiscalRejectionError",
    "FiscalAdapterNotConfigured",
    "FiscalAdapterNotSupported",
    "FiscalAdapterTechnicalError",
    "FiscalAdapterTimeoutError",
    "MockFiscalAdapter",
    "get_fiscal_adapter",
]
