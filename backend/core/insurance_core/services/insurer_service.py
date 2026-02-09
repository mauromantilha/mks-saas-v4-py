from __future__ import annotations

from django.db import transaction

from insurance_core.events import publish_tenant_event
from insurance_core.models import Insurer, InsurerContact
from ledger.models import LedgerEntry


def _insurer_snapshot(insurer: Insurer) -> dict:
    contacts = list(
        insurer.contacts.all()
        .order_by("-is_primary", "id")
        .values(
            "id",
            "name",
            "email",
            "phone",
            "role",
            "is_primary",
            "notes",
        )
    )
    return {
        "id": insurer.id,
        "name": insurer.name,
        "legal_name": insurer.legal_name,
        "cnpj": insurer.cnpj,
        "zip_code": insurer.zip_code,
        "state": insurer.state,
        "city": insurer.city,
        "neighborhood": insurer.neighborhood,
        "street": insurer.street,
        "street_number": insurer.street_number,
        "address_complement": insurer.address_complement,
        "contacts": contacts,
        "status": insurer.status,
        "integration_type": insurer.integration_type,
        "integration_config": insurer.integration_config,
    }


def _sync_insurer_contacts(*, insurer: Insurer, contacts_data: list[dict]) -> None:
    existing = {contact.id: contact for contact in insurer.contacts.all()}
    keep_ids: set[int] = set()

    for item in contacts_data:
        contact_id = item.get("id")
        if contact_id is None:
            created = InsurerContact.objects.create(insurer=insurer, **item)
            keep_ids.add(created.id)
            continue

        try:
            contact_id_int = int(contact_id)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid insurer contact id '{contact_id}'.") from None

        instance = existing.get(contact_id_int)
        if instance is None:
            raise ValueError(f"Insurer contact id '{contact_id_int}' does not exist.")

        for field in ("name", "email", "phone", "role", "is_primary", "notes"):
            if field in item:
                setattr(instance, field, item[field])
        instance.save()
        keep_ids.add(instance.id)

    # Replace semantics: if contacts are provided, any missing contact is deleted.
    for contact_id, contact in existing.items():
        if contact_id not in keep_ids:
            contact.delete()


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
        contacts_data = data.pop("contacts", None)

        if instance is None:
            insurer = Insurer(company=company, **data)
            insurer.save()
            if contacts_data:
                _sync_insurer_contacts(insurer=insurer, contacts_data=contacts_data)
                insurer.refresh_from_db()
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
        if contacts_data is not None:
            _sync_insurer_contacts(insurer=instance, contacts_data=contacts_data)
            instance.refresh_from_db()
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
