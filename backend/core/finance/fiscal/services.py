from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from django.db import transaction
from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_date

from ledger.models import LedgerEntry
from ledger.services import append_ledger_entry
from tenancy.context import get_current_company
from tenancy.context import reset_current_company, set_current_company
from tenancy.logging import mask_cpf_cnpj

from finance.fiscal.adapters import FiscalAdapterError, get_fiscal_adapter
from finance.fiscal.invoice_gateway import resolve_invoice_for_fiscal
from finance.fiscal.models import (
    FiscalCustomerSnapshot,
    FiscalDocument,
    FiscalJob,
    TenantFiscalConfig,
)

logger = logging.getLogger(__name__)


def _normalize_fiscal_status(value: Any) -> str:
    status = str(value or "").strip().upper()
    if status in FiscalDocument.Status.values:
        return status

    aliases = {
        "AUTHORISED": FiscalDocument.Status.AUTHORIZED,
        "AUTHORIZED": FiscalDocument.Status.AUTHORIZED,
        "AUTORIZADO": FiscalDocument.Status.AUTHORIZED,
        "CANCELED": FiscalDocument.Status.CANCELLED,
        "CANCELLED": FiscalDocument.Status.CANCELLED,
        "CANCELADO": FiscalDocument.Status.CANCELLED,
        "REJECTED": FiscalDocument.Status.REJECTED,
        "REJEITADO": FiscalDocument.Status.REJECTED,
        "DENIED": FiscalDocument.Status.REJECTED,
        "ERROR": FiscalDocument.Status.REJECTED,
        "PENDING": FiscalDocument.Status.EMITTING,
        "PROCESSING": FiscalDocument.Status.EMITTING,
        "EMITTING": FiscalDocument.Status.EMITTING,
    }
    return aliases.get(status, FiscalDocument.Status.EMITTING)


def _compute_next_retry(attempts: int) -> datetime:
    # Exponential backoff capped at 1 hour.
    attempts = max(int(attempts), 1)
    delay_seconds = min(60 * (2 ** (attempts - 1)), 60 * 60)
    return timezone.now() + timedelta(seconds=delay_seconds)


class FiscalIssueError(RuntimeError):
    """Base error for fiscal issuance service failures."""


class FiscalIssueTenantMissing(FiscalIssueError):
    """Raised when issuing without an active tenant context."""


class FiscalCancelError(RuntimeError):
    """Base error for fiscal cancellation service failures."""


class FiscalCancelAlreadyCancelled(FiscalCancelError):
    """Raised when attempting to cancel a document that is already cancelled."""


@dataclass(frozen=True, slots=True)
class _CustomerSnapshotDTO:
    name: str
    cpf_cnpj: str
    address: str


def _safe_decimal(value: Any) -> Decimal:
    try:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise FiscalIssueError("Invalid invoice amount.") from exc


def _safe_issue_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        parsed = parse_date(value)
        if parsed:
            return parsed
    raise FiscalIssueError("Invalid invoice issue_date.")


def _build_customer_snapshot(invoice: Mapping[str, Any]) -> _CustomerSnapshotDTO:
    customer = invoice.get("customer") or {}
    if not isinstance(customer, Mapping):
        raise FiscalIssueError("Invalid invoice customer payload.")

    name = str(customer.get("name") or "").strip()
    cpf_cnpj = str(customer.get("cpf_cnpj") or "").strip()
    address = str(customer.get("address") or "").strip()

    if not name:
        raise FiscalIssueError("Invoice customer name is required.")
    if not cpf_cnpj:
        raise FiscalIssueError("Invoice customer cpf_cnpj is required.")

    return _CustomerSnapshotDTO(name=name, cpf_cnpj=cpf_cnpj, address=address)


def _build_adapter_payload(
    *,
    invoice: Mapping[str, Any],
    customer_snapshot: _CustomerSnapshotDTO,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "invoice_id": invoice.get("invoice_id"),
        "amount": invoice.get("amount"),
        "issue_date": invoice.get("issue_date"),
        "currency": invoice.get("currency") or "BRL",
        "customer": {
            "name": customer_snapshot.name,
            "cpf_cnpj": customer_snapshot.cpf_cnpj,
            "address": customer_snapshot.address,
        },
    }

    items = invoice.get("items")
    if isinstance(items, list):
        payload["items"] = items

    return payload


def issue_nf_from_invoice(
    invoice_id: int,
    *,
    actor=None,
    request=None,
    auto_issue: bool = False,
) -> FiscalDocument:
    """Issue a fiscal document (NF-e) from a finance invoice reference.

    Steps:
    1) Fetch/resolve invoice data (via configured resolver).
    2) Build immutable customer snapshot.
    3) Build provider-agnostic payload.
    4) Call the configured adapter.
    5) Persist FiscalDocument + snapshot.
    6) Append an immutable ledger entry (audit).

    Notes:
    - This function is tenant-scoped: it requires an active tenant context
      (tenancy.context current company).
    - Logging intentionally excludes sensitive data (tokens, XML, customer PII).
    """

    company = get_current_company()
    if company is None:
        raise FiscalIssueTenantMissing(
            "Tenant context is required. Call within a tenant-scoped request."
        )

    logger.info(
        "fiscal.issue.started company_id=%s invoice_id=%s",
        company.id,
        invoice_id,
    )

    invoice = resolve_invoice_for_fiscal(invoice_id=invoice_id, company_id=company.id)
    if int(invoice.get("invoice_id", invoice_id)) != int(invoice_id):
        raise FiscalIssueError("Resolved invoice_id does not match requested invoice_id.")

    amount = _safe_decimal(invoice.get("amount"))
    issue_date = _safe_issue_date(invoice.get("issue_date"))
    customer_snapshot = _build_customer_snapshot(invoice)
    adapter_payload = _build_adapter_payload(invoice=invoice, customer_snapshot=customer_snapshot)

    # Adapter selection is tenant-based (active TenantFiscalConfig).
    try:
        config = (
            TenantFiscalConfig.all_objects.select_related("provider")
            .only("company_id", "provider__provider_type")
            .get(company_id=company.id, active=True)
        )
    except TenantFiscalConfig.DoesNotExist as exc:
        raise FiscalIssueError("Tenant has no active fiscal configuration.") from exc
    except TenantFiscalConfig.MultipleObjectsReturned as exc:
        raise FiscalIssueError("Tenant has multiple active fiscal configurations.") from exc

    provider_type = (config.provider.provider_type or "").strip()
    try:
        adapter = get_fiscal_adapter(company.id)
    except FiscalAdapterError as exc:
        raise FiscalIssueError(str(exc)) from exc

    adapter_result = adapter.issue_invoice(adapter_payload)
    status = str(adapter_result.get("status") or FiscalDocument.Status.DRAFT).strip().upper()
    if status not in FiscalDocument.Status.values:
        status = FiscalDocument.Status.DRAFT

    number = str(adapter_result.get("number") or "").strip()
    series = str(adapter_result.get("series") or "").strip()
    provider_document_id = str(adapter_result.get("document_id") or "").strip()
    xml_document_id = str(adapter_result.get("xml_document_id") or "").strip()
    xml_content = str(adapter_result.get("xml_content") or "").strip()

    # DB operations are atomic. External provider call cannot be rolled back.
    with transaction.atomic():
        doc = FiscalDocument.all_objects.create(
            company=company,
            invoice_id=invoice_id,
            provider_document_id=provider_document_id,
            number=number,
            series=series,
            issue_date=issue_date,
            amount=amount,
            status=status,
            xml_document_id=xml_document_id,
            xml_content=xml_content,
        )

        FiscalCustomerSnapshot.all_objects.create(
            fiscal_document=doc,
            name=customer_snapshot.name,
            cpf_cnpj=customer_snapshot.cpf_cnpj,
            address=customer_snapshot.address,
        )

        event_type = "finance.fiscal.auto_issue" if auto_issue else "finance.fiscal.issue"
        append_ledger_entry(
            scope=LedgerEntry.SCOPE_TENANT,
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_CREATE,
            resource_label="finance.fiscal.FiscalDocument",
            resource_pk=str(doc.id),
            request=request,
            event_type=event_type,
            data_after={
                "id": doc.id,
                "invoice_id": doc.invoice_id,
                "status": doc.status,
            },
            metadata={
                "provider_type": provider_type,
                "auto_issue": bool(auto_issue),
            },
        )

    logger.info(
        "fiscal.issue.completed company_id=%s invoice_id=%s fiscal_document_id=%s status=%s provider_type=%s",
        company.id,
        invoice_id,
        doc.id,
        doc.status,
        provider_type,
    )
    return doc


def auto_issue_nf_from_invoice(invoice_id: int, *, actor=None, request=None) -> FiscalDocument | None:
    """Auto-issue NF when invoice is PAID and tenant config has auto_issue enabled.

    This should be called by the finance invoice workflow when a payment is confirmed.
    It is idempotent: if a FiscalDocument already exists for the invoice, it returns it.
    """

    company = get_current_company()
    if company is None:
        raise FiscalIssueTenantMissing(
            "Tenant context is required. Call within a tenant-scoped request."
        )

    invoice = resolve_invoice_for_fiscal(invoice_id=invoice_id, company_id=company.id)
    status_value = str(invoice.get("status") or "").strip().upper()
    if status_value != "PAID":
        logger.info(
            "fiscal.auto_issue.skipped company_id=%s invoice_id=%s invoice_status=%s",
            company.id,
            invoice_id,
            status_value or "UNKNOWN",
        )
        return None

    config = TenantFiscalConfig.all_objects.filter(company_id=company.id, active=True).first()
    if config is None:
        logger.info(
            "fiscal.auto_issue.skipped company_id=%s invoice_id=%s reason=no_active_config",
            company.id,
            invoice_id,
        )
        return None

    if not config.auto_issue:
        logger.info(
            "fiscal.auto_issue.skipped company_id=%s invoice_id=%s reason=auto_issue_disabled",
            company.id,
            invoice_id,
        )
        return None

    existing = (
        FiscalDocument.all_objects.filter(company=company, invoice_id=invoice_id)
        .order_by("-id")
        .first()
    )
    if existing is not None:
        return existing

    # Issue using the existing service (manual issuance path), but tag ledger metadata.
    return issue_nf_from_invoice(invoice_id, actor=actor, request=request, auto_issue=True)


def cancel_nf(document_id: str, *, actor=None, request=None) -> FiscalDocument:
    """Cancel a fiscal document (NF-e) at the provider and persist status change.

    Args:
        document_id: Provider document id (recommended) or FiscalDocument id (fallback).
    """

    company = get_current_company()
    if company is None:
        raise FiscalIssueTenantMissing(
            "Tenant context is required. Call within a tenant-scoped request."
        )

    # Tenant-scoped resolution: try provider_document_id first, then fallback to PK.
    qs = FiscalDocument.all_objects.filter(company=company)
    doc = qs.filter(provider_document_id=document_id).first()
    if doc is None and str(document_id).isdigit():
        doc = qs.filter(id=int(document_id)).first()
    if doc is None:
        raise FiscalCancelError("Fiscal document not found.")

    logger.info(
        "fiscal.cancel.started company_id=%s fiscal_document_id=%s",
        company.id,
        doc.id,
    )

    # Serialize cancellation per document to avoid double-cancel races.
    with transaction.atomic():
        lock_qs = FiscalDocument.all_objects
        if connection.features.has_select_for_update:
            lock_qs = lock_qs.select_for_update()

        locked = lock_qs.filter(company=company, id=doc.id).first()
        if locked is None:
            raise FiscalCancelError("Fiscal document not found.")

        if locked.status == FiscalDocument.Status.CANCELLED:
            raise FiscalCancelAlreadyCancelled("Fiscal document is already cancelled.")

        provider_doc_id = (locked.provider_document_id or "").strip()
        if not provider_doc_id:
            raise FiscalCancelError(
                "provider_document_id is empty; cannot cancel at provider."
            )

        # Load provider_type for auditing only (no secrets, no payload).
        try:
            config = (
                TenantFiscalConfig.all_objects.select_related("provider")
                .only("company_id", "provider__provider_type")
                .get(company_id=company.id, active=True)
            )
        except TenantFiscalConfig.DoesNotExist as exc:
            raise FiscalCancelError("Tenant has no active fiscal configuration.") from exc
        except TenantFiscalConfig.MultipleObjectsReturned as exc:
            raise FiscalCancelError("Tenant has multiple active fiscal configurations.") from exc

        provider_type = (config.provider.provider_type or "").strip()

        try:
            adapter = get_fiscal_adapter(company.id)
        except FiscalAdapterError as exc:
            raise FiscalCancelError(str(exc)) from exc
        adapter.cancel_invoice(provider_doc_id)

        previous_status = locked.status
        locked.status = FiscalDocument.Status.CANCELLED
        locked.save(update_fields=["status", "updated_at"])

        append_ledger_entry(
            scope=LedgerEntry.SCOPE_TENANT,
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_UPDATE,
            resource_label="finance.fiscal.FiscalDocument",
            resource_pk=str(locked.id),
            request=request,
            event_type="finance.fiscal.cancel",
            data_before={
                "id": locked.id,
                "status": previous_status,
            },
            data_after={
                "id": locked.id,
                "status": locked.status,
            },
            metadata={
                "provider_type": provider_type,
            },
        )

    logger.info(
        "fiscal.cancel.completed company_id=%s fiscal_document_id=%s status=%s",
        company.id,
        locked.id,
        locked.status,
    )
    return locked


def enqueue_fiscal_job(document_id: int, *, actor=None, request=None) -> FiscalJob:
    """Create (or re-queue) an async FiscalJob for a FiscalDocument."""

    company = get_current_company()
    if company is None:
        raise FiscalIssueTenantMissing(
            "Tenant context is required. Call within a tenant-scoped request."
        )

    logger.info(
        "fiscal.job.enqueue.started company_id=%s fiscal_document_id=%s",
        company.id,
        document_id,
    )

    now = timezone.now()
    with transaction.atomic():
        doc = FiscalDocument.objects.get(id=document_id)
        job, created = FiscalJob.all_objects.get_or_create(
            fiscal_document=doc,
            defaults={
                "company": doc.company,
                "status": FiscalJob.Status.QUEUED,
                "attempts": 0,
                "last_error": "",
                "next_retry_at": now,
            },
        )

        if not created and job.status in {FiscalJob.Status.FAILED}:
            job.status = FiscalJob.Status.QUEUED
            job.last_error = ""
            job.next_retry_at = now
            job.save(update_fields=["status", "last_error", "next_retry_at", "updated_at"])

        append_ledger_entry(
            scope=LedgerEntry.SCOPE_TENANT,
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_CREATE if created else LedgerEntry.ACTION_UPDATE,
            resource_label="finance.fiscal.FiscalJob",
            resource_pk=str(job.id),
            request=request,
            event_type="finance.fiscal.job.enqueue",
            data_after={
                "id": job.id,
                "fiscal_document_id": doc.id,
                "status": job.status,
                "attempts": job.attempts,
                "next_retry_at": job.next_retry_at.isoformat() if job.next_retry_at else None,
            },
            metadata={
                "created": bool(created),
            },
        )

    logger.info(
        "fiscal.job.enqueue.completed company_id=%s fiscal_document_id=%s fiscal_job_id=%s created=%s status=%s",
        company.id,
        doc.id,
        job.id,
        created,
        job.status,
    )
    return job


def process_fiscal_job(job_id: int, *, actor=None, request=None) -> FiscalJob:
    """Process a single fiscal job.

    This worker is provider-agnostic and can be called from:
    - a management command (cron)
    - Celery/Cloud Tasks worker
    - Pub/Sub triggered Cloud Run service
    """

    now = timezone.now()

    # Lock job + doc and mark RUNNING (external calls must happen outside the transaction).
    with transaction.atomic():
        job_qs = FiscalJob.all_objects.select_related("fiscal_document")
        if connection.features.has_select_for_update:
            job_qs = job_qs.select_for_update()

        job = job_qs.get(id=job_id)
        doc = job.fiscal_document

        if job.status == FiscalJob.Status.SUCCEEDED:
            return job

        # Respect scheduling if present.
        if job.next_retry_at and job.next_retry_at > now and job.status != FiscalJob.Status.RUNNING:
            return job

        # Mark RUNNING and bump attempts.
        job.status = FiscalJob.Status.RUNNING
        job.attempts = int(job.attempts or 0) + 1
        job.last_error = ""
        job.next_retry_at = None
        job.save(
            update_fields=["status", "attempts", "last_error", "next_retry_at", "updated_at"]
        )

        # Keep document in progress unless it is already final.
        if doc.status not in {
            FiscalDocument.Status.AUTHORIZED,
            FiscalDocument.Status.REJECTED,
            FiscalDocument.Status.CANCELLED,
        } and doc.status != FiscalDocument.Status.EMITTING:
            doc.status = FiscalDocument.Status.EMITTING
            doc.save(update_fields=["status", "updated_at"])

    # Set tenant context for extra safety (TenantManager filtering + write enforcement).
    tenant_token = set_current_company(doc.company)
    try:
        adapter = get_fiscal_adapter(doc.company_id)

        issued_amount: Decimal | None = None
        issued_issue_date: date | None = None

        # Decide the operation based on document state.
        if not (doc.provider_document_id or "").strip():
            invoice = resolve_invoice_for_fiscal(invoice_id=doc.invoice_id, company_id=doc.company_id)
            issued_amount = _safe_decimal(invoice.get("amount"))
            issued_issue_date = _safe_issue_date(invoice.get("issue_date"))
            customer_snapshot = _build_customer_snapshot(invoice)
            payload = _build_adapter_payload(invoice=invoice, customer_snapshot=customer_snapshot)
            adapter_result = adapter.issue_invoice(payload)
        else:
            adapter_result = adapter.check_status(doc.provider_document_id)

        new_status = _normalize_fiscal_status(adapter_result.get("status"))
        provider_document_id = (
            str(adapter_result.get("provider_document_id") or adapter_result.get("document_id") or "")
            .strip()
        )
        series = str(adapter_result.get("series") or "").strip()
        number = str(adapter_result.get("number") or "").strip()
        xml_document_id = str(adapter_result.get("xml_document_id") or "").strip()
        xml_content = str(adapter_result.get("xml_content") or "").strip()

        # Persist state changes.
        with transaction.atomic():
            lock_doc_qs = FiscalDocument.all_objects
            lock_job_qs = FiscalJob.all_objects
            if connection.features.has_select_for_update:
                lock_doc_qs = lock_doc_qs.select_for_update()
                lock_job_qs = lock_job_qs.select_for_update()

            job = lock_job_qs.select_related("fiscal_document").get(id=job_id)
            doc = lock_doc_qs.get(id=job.fiscal_document_id)

            changed_fields: list[str] = ["updated_at"]
            if issued_amount is not None and issued_amount != doc.amount:
                doc.amount = issued_amount
                changed_fields.append("amount")
            if issued_issue_date is not None and issued_issue_date != doc.issue_date:
                doc.issue_date = issued_issue_date
                changed_fields.append("issue_date")
            if provider_document_id and not (doc.provider_document_id or "").strip():
                doc.provider_document_id = provider_document_id
                changed_fields.append("provider_document_id")
            if series and series != (doc.series or ""):
                doc.series = series
                changed_fields.append("series")
            if number and number != (doc.number or ""):
                doc.number = number
                changed_fields.append("number")
            if xml_document_id and xml_document_id != (doc.xml_document_id or ""):
                doc.xml_document_id = xml_document_id
                changed_fields.append("xml_document_id")
            if xml_content and xml_content != (doc.xml_content or ""):
                doc.xml_content = xml_content
                changed_fields.append("xml_content")

            if new_status and new_status != doc.status:
                doc.status = new_status
                changed_fields.append("status")

            doc.save(update_fields=sorted(set(changed_fields)))

            is_final = doc.status in {
                FiscalDocument.Status.AUTHORIZED,
                FiscalDocument.Status.REJECTED,
                FiscalDocument.Status.CANCELLED,
            }
            job.status = FiscalJob.Status.SUCCEEDED if is_final else FiscalJob.Status.QUEUED
            job.last_error = ""
            job.next_retry_at = None if is_final else _compute_next_retry(job.attempts)
            job.save(update_fields=["status", "last_error", "next_retry_at", "updated_at"])

            append_ledger_entry(
                scope=LedgerEntry.SCOPE_TENANT,
                company=doc.company,
                actor=actor,
                action=LedgerEntry.ACTION_UPDATE,
                resource_label="finance.fiscal.FiscalJob",
                resource_pk=str(job.id),
                request=request,
                event_type="finance.fiscal.job.process",
                data_after={
                    "id": job.id,
                    "fiscal_document_id": doc.id,
                    "job_status": job.status,
                    "doc_status": doc.status,
                    "attempts": job.attempts,
                },
                metadata={
                    "final": bool(is_final),
                },
            )

        logger.info(
            "fiscal.job.process.completed company_id=%s fiscal_job_id=%s fiscal_document_id=%s job_status=%s doc_status=%s attempts=%s",
            doc.company_id,
            job.id,
            doc.id,
            job.status,
            doc.status,
            job.attempts,
        )
        return job
    except Exception as exc:
        error_msg = mask_cpf_cnpj(str(exc))[:4000]
        try:
            with transaction.atomic():
                lock_job_qs = FiscalJob.all_objects
                if connection.features.has_select_for_update:
                    lock_job_qs = lock_job_qs.select_for_update()

                job = lock_job_qs.select_related("fiscal_document").get(id=job_id)
                job.status = FiscalJob.Status.FAILED
                job.last_error = error_msg
                job.next_retry_at = _compute_next_retry(job.attempts or 1)
                job.save(update_fields=["status", "last_error", "next_retry_at", "updated_at"])

                append_ledger_entry(
                    scope=LedgerEntry.SCOPE_TENANT,
                    company=job.company,
                    actor=actor,
                    action=LedgerEntry.ACTION_UPDATE,
                    resource_label="finance.fiscal.FiscalJob",
                    resource_pk=str(job.id),
                    request=request,
                    event_type="finance.fiscal.job.failed",
                    data_after={
                        "id": job.id,
                        "fiscal_document_id": job.fiscal_document_id,
                        "status": job.status,
                        "attempts": job.attempts,
                        "next_retry_at": job.next_retry_at.isoformat() if job.next_retry_at else None,
                    },
                    metadata={
                        "error": error_msg,
                    },
                )
        except Exception:  # pragma: no cover
            # Best-effort: never fail the worker because we couldn't persist failure status.
            logger.exception("fiscal.job.process.failed.persist_error job_id=%s", job_id)

        logger.warning(
            "fiscal.job.process.failed job_id=%s error=%s next_retry_at=%s",
            job_id,
            error_msg,
            job.next_retry_at.isoformat() if getattr(job, "next_retry_at", None) else "",
        )
        return job
    finally:
        reset_current_company(tenant_token)
