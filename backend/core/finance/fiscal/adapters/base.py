from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping


class FiscalAdapterError(RuntimeError):
    """Base exception for fiscal adapter failures."""

    retryable: bool = True


class FiscalAdapterTechnicalError(FiscalAdapterError):
    """Technical failure talking to the provider (network, auth, outages, etc.)."""

    retryable = True


class FiscalAdapterTimeoutError(FiscalAdapterTechnicalError):
    """Provider request timed out."""

    retryable = True


class FiscalAdapterFiscalRejectionError(FiscalAdapterError):
    """Business/fiscal rejection returned by the provider (not retryable)."""

    retryable = False

    def __init__(self, message: str, *, code: str | None = None, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = dict(details) if details else {}


class FiscalAdapterBase(ABC):
    """Adapter interface for issuing/cancelling/checking fiscal documents.

    Notes:
    - Keep this interface provider-agnostic (no vendor-specific types).
    - Adapters should be side-effectful only towards the provider API.
      Persistence, retries, and tenant-aware orchestration belong to services.
    """

    def __init__(self, *, timeout_seconds: float | None = None) -> None:
        # Adapter implementors should pass this through to their HTTP client timeout config.
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    def issue_invoice(self, data: Mapping[str, Any]) -> Mapping[str, Any]:
        """Issue a fiscal document.

        Args:
            data: Normalized invoice payload. The exact schema is defined by the
                service layer and should be consistent across adapters.

        Returns:
            A provider-agnostic response mapping. It should include enough
            information for the caller to persist a `FiscalDocument`, e.g.:
            - provider_document_id / document_id
            - status
            - number/series (if available)
            - xml_content and/or xml_document_id (if available)
            - raw (optional raw provider response)
        """

    @abstractmethod
    def cancel_invoice(self, document_id: str) -> Mapping[str, Any]:
        """Cancel a previously issued fiscal document at the provider."""

    @abstractmethod
    def check_status(self, document_id: str) -> Mapping[str, Any]:
        """Fetch current provider status for a fiscal document."""
