from __future__ import annotations

import hashlib
import json
from uuid import UUID, uuid4

from django.db import IntegrityError, transaction
from django.utils import timezone

from ledger.models import LedgerEntry


def _canonical_json(value) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def _safe_uuid(value: str) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except Exception:
        return None


def _extract_ip(request) -> str:
    if request is None:
        return ""
    # If behind a LB, X-Forwarded-For might contain a chain. We only keep the left-most.
    forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def _build_entry_hash(payload: dict, prev_hash: str) -> str:
    payload_json = _canonical_json(payload)
    material = f"{prev_hash}{payload_json}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def append_ledger_entry(
    *,
    scope: str,
    company,
    actor,
    action: str,
    resource_label: str,
    resource_pk: str,
    request=None,
    event_type: str = "",
    data_before: dict | None = None,
    data_after: dict | None = None,
    metadata: dict | None = None,
) -> LedgerEntry:
    """Append a new immutable ledger entry.

    Uses a per-chain hash-chain and retries on concurrent writers to keep a linear chain.
    """

    if scope not in (LedgerEntry.SCOPE_TENANT, LedgerEntry.SCOPE_PLATFORM):
        raise ValueError(f"Invalid ledger scope '{scope}'.")

    company_id = getattr(company, "id", None)
    if scope == LedgerEntry.SCOPE_TENANT and company_id is None:
        raise ValueError("company is required for tenant ledger entries.")
    if scope == LedgerEntry.SCOPE_PLATFORM and company is not None:
        raise ValueError("company must be None for platform ledger entries.")

    chain_id = f"tenant:{company_id}" if scope == LedgerEntry.SCOPE_TENANT else "platform"

    occurred_at = timezone.now()
    request_id = None
    request_method = ""
    request_path = ""
    ip_address = ""
    user_agent = ""
    if request is not None:
        request_id = _safe_uuid(request.headers.get("X-Request-ID", ""))
        request_method = (getattr(request, "method", "") or "").upper()
        request_path = getattr(request, "path", "") or ""
        ip_address = _extract_ip(request)
        user_agent = (request.META.get("HTTP_USER_AGENT") or "").strip()

    if request_id is None:
        request_id = uuid4()

    actor_obj = actor if getattr(actor, "is_authenticated", False) else None
    actor_username = (getattr(actor_obj, "username", "") or "").strip()
    actor_email = (getattr(actor_obj, "email", "") or "").strip()

    metadata_payload = metadata if isinstance(metadata, dict) else {}
    if not event_type:
        event_type = f"{resource_label}.{action}"

    for _attempt in range(5):
        prev_hash = (
            LedgerEntry.all_objects.filter(chain_id=chain_id)
            .order_by("-id")
            .values_list("entry_hash", flat=True)
            .first()
            or ""
        )

        payload = {
            "chain_id": chain_id,
            "scope": scope,
            "company_id": company_id,
            "actor_username": actor_username,
            "actor_email": actor_email,
            "action": action,
            "event_type": event_type,
            "resource_label": resource_label,
            "resource_pk": resource_pk,
            "occurred_at": occurred_at.isoformat(),
            "request_id": str(request_id),
            "request_method": request_method,
            "request_path": request_path,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "data_before": data_before,
            "data_after": data_after,
            "metadata": metadata_payload,
        }

        entry_hash = _build_entry_hash(payload, prev_hash)

        entry = LedgerEntry(
            scope=scope,
            company=company if scope == LedgerEntry.SCOPE_TENANT else None,
            actor=actor_obj,
            actor_username=actor_username,
            actor_email=actor_email,
            action=action,
            event_type=event_type,
            resource_label=resource_label,
            resource_pk=resource_pk,
            occurred_at=occurred_at,
            request_id=request_id,
            request_method=request_method,
            request_path=request_path,
            ip_address=ip_address or None,
            user_agent=user_agent,
            chain_id=chain_id,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            data_before=data_before,
            data_after=data_after,
            metadata=metadata_payload,
        )

        try:
            with transaction.atomic():
                entry.save(force_insert=True)
            return entry
        except IntegrityError as exc:
            # Concurrent writers may race on prev_hash uniqueness. Retry with a new prev_hash.
            msg = str(exc)
            if "uq_ledger_prev_hash_per_chain" in msg or "uq_ledger_entry_hash_per_chain" in msg:
                continue
            raise

    raise RuntimeError("Failed to append ledger entry (concurrency retries exhausted).")

