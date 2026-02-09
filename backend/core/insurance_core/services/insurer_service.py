from __future__ import annotations

from django.db import transaction

from insurance_core.events import publish_tenant_event
from insurance_core.models import Insurer
from ledger.models import LedgerEntry


def _insurer_snapshot(insurer: Insurer) -> dict:
    return {
        "id": insurer.id,
        "name": insurer.name,
        "legal_name": insurer.legal_name,
        "cnpj": insurer.cnpj,
        "status": insurer.status,
        "integration_type": insurer.integration_type,
        "integration_config": insurer.integration_config,
    }


def upsert_insurer(
    *,
    company,
    actor,
    instance: Insurer | None,
    data: dict,
    request=None,
) -> Insurer:
    """Create or update an insurer and emit a domain event into the ledger."""

    with transaction.atomic():
        if instance is None:
            insurer = Insurer(company=company, **data)
            insurer.save()
            publish_tenant_event(
                company=company,
                actor=actor,
                action=LedgerEntry.ACTION_CREATE,
                event_type="insurance_core.insurer.create",
                resource_label="insurance_core.Insurer",
                resource_pk=str(insurer.pk),
                request=request,
                data_before=None,
                data_after=_insurer_snapshot(insurer),
            )
            return insurer

        if instance.company_id != company.id:
            raise ValueError("Cross-tenant insurer update blocked.")

        before = _insurer_snapshot(instance)
        for key, value in data.items():
            setattr(instance, key, value)
        instance.save()
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_UPDATE,
            event_type="insurance_core.insurer.update",
            resource_label="insurance_core.Insurer",
            resource_pk=str(instance.pk),
            request=request,
            data_before=before,
            data_after=_insurer_snapshot(instance),
        )
        return instance


def deactivate_insurer(*, company, actor, insurer: Insurer, request=None) -> Insurer:
    with transaction.atomic():
        if insurer.company_id != company.id:
            raise ValueError("Cross-tenant insurer deactivation blocked.")

        before = _insurer_snapshot(insurer)
        insurer.status = Insurer.Status.INACTIVE
        insurer.save(update_fields=("status", "updated_at"))
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_UPDATE,
            event_type="insurance_core.insurer.deactivate",
            resource_label="insurance_core.Insurer",
            resource_pk=str(insurer.pk),
            request=request,
            data_before=before,
            data_after=_insurer_snapshot(insurer),
        )
        return insurer

