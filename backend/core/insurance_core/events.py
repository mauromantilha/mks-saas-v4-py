from __future__ import annotations

from ledger.models import LedgerEntry
from ledger.services import append_ledger_entry


def publish_tenant_event(
    *,
    company,
    actor,
    action: str,
    event_type: str,
    resource_label: str,
    resource_pk: str,
    request=None,
    data_before: dict | None = None,
    data_after: dict | None = None,
    metadata: dict | None = None,
) -> LedgerEntry:
    """Publish a domain event into the immutable tenant ledger (outbox seed)."""

    return append_ledger_entry(
        scope=LedgerEntry.SCOPE_TENANT,
        company=company,
        actor=actor,
        action=action,
        event_type=event_type,
        resource_label=resource_label,
        resource_pk=str(resource_pk),
        request=request,
        data_before=data_before,
        data_after=data_after,
        metadata=metadata,
    )

