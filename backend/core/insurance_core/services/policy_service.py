from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from insurance_core.events import publish_tenant_event
from insurance_core.models import (
    Endorsement,
    InsuranceProduct,
    Insurer,
    Policy,
    PolicyCoverage,
    PolicyDocumentRequirement,
    PolicyItem,
    ProductCoverage,
)
from ledger.models import LedgerEntry
from operational.models import Customer


def _policy_snapshot(policy: Policy) -> dict:
    return {
        "id": policy.id,
        "policy_number": policy.policy_number,
        "insurer_id": policy.insurer_id,
        "product_id": policy.product_id,
        "insured_party_id": policy.insured_party_id,
        "insured_party_label": policy.insured_party_label,
        "broker_reference": policy.broker_reference,
        "status": policy.status,
        "issue_date": policy.issue_date,
        "start_date": policy.start_date,
        "end_date": policy.end_date,
        "currency": policy.currency,
        "premium_total": policy.premium_total,
        "tax_total": policy.tax_total,
        "commission_total": policy.commission_total,
        "notes": policy.notes,
        "created_by_id": policy.created_by_id,
    }


def _policy_item_snapshot(item: PolicyItem) -> dict:
    return {
        "id": item.id,
        "policy_id": item.policy_id,
        "item_type": item.item_type,
        "description": item.description,
        "attributes": item.attributes,
        "sum_insured": item.sum_insured,
    }


def _policy_coverage_snapshot(coverage: PolicyCoverage) -> dict:
    return {
        "id": coverage.id,
        "policy_id": coverage.policy_id,
        "product_coverage_id": coverage.product_coverage_id,
        "limit_amount": coverage.limit_amount,
        "deductible_amount": coverage.deductible_amount,
        "premium_amount": coverage.premium_amount,
        "is_enabled": coverage.is_enabled,
    }


def _policy_docreq_snapshot(docreq: PolicyDocumentRequirement) -> dict:
    return {
        "id": docreq.id,
        "policy_id": docreq.policy_id,
        "requirement_code": docreq.requirement_code,
        "required": docreq.required,
        "status": docreq.status,
        "document_id": docreq.document_id,
    }


def _endorsement_snapshot(endorsement: Endorsement) -> dict:
    return {
        "id": endorsement.id,
        "policy_id": endorsement.policy_id,
        "endorsement_number": endorsement.endorsement_number,
        "type": endorsement.type,
        "status": endorsement.status,
        "effective_date": endorsement.effective_date,
        "payload": endorsement.payload,
    }


def _resolve_customer_label(*, company, customer_id: int) -> str:
    customer = (
        Customer.all_objects.filter(company=company, id=customer_id)
        .only("id", "name")
        .first()
    )
    if customer is None:
        raise ValidationError({"insured_party_id": "Customer not found for this tenant."})
    return customer.name


def upsert_policy(
    *,
    company,
    actor,
    instance: Policy | None,
    data: dict,
    request=None,
) -> Policy:
    """Create or update a policy and emit a domain event into the ledger."""

    insurer = data.get("insurer") or getattr(instance, "insurer", None)
    product = data.get("product") or getattr(instance, "product", None)
    insured_party_id = data.get("insured_party_id") or getattr(instance, "insured_party_id", None)

    if insurer is None:
        raise ValidationError({"insurer_id": "insurer_id is required."})
    if product is None:
        raise ValidationError({"product_id": "product_id is required."})
    if insured_party_id is None:
        raise ValidationError({"insured_party_id": "insured_party_id is required."})

    if not Insurer.all_objects.filter(company=company, id=insurer.id).exists():
        raise ValidationError({"insurer_id": "Invalid insurer for this tenant."})
    if not InsuranceProduct.all_objects.filter(company=company, id=product.id).exists():
        raise ValidationError({"product_id": "Invalid product for this tenant."})
    if product.insurer_id != insurer.id:
        raise ValidationError({"product_id": "Product must belong to the selected insurer."})

    insured_party_label = data.get("insured_party_label") or ""
    if not insured_party_label:
        insured_party_label = _resolve_customer_label(company=company, customer_id=int(insured_party_id))
        data = {**data, "insured_party_label": insured_party_label}

    with transaction.atomic():
        if instance is None:
            policy = Policy(company=company, created_by=actor, **data)
            policy.save()
            publish_tenant_event(
                company=company,
                actor=actor,
                action=LedgerEntry.ACTION_CREATE,
                event_type="insurance_core.policy.create",
                resource_label="insurance_core.Policy",
                resource_pk=str(policy.pk),
                request=request,
                data_before=None,
                data_after=_policy_snapshot(policy),
            )
            return policy

        if instance.company_id != company.id:
            raise ValidationError("Cross-tenant policy update blocked.")

        before = _policy_snapshot(instance)
        for key, value in data.items():
            setattr(instance, key, value)
        instance.save()
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_UPDATE,
            event_type="insurance_core.policy.update",
            resource_label="insurance_core.Policy",
            resource_pk=str(instance.pk),
            request=request,
            data_before=before,
            data_after=_policy_snapshot(instance),
        )
        return instance


_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    Policy.Status.DRAFT: frozenset((Policy.Status.UNDERWRITING, Policy.Status.CANCELLED)),
    Policy.Status.UNDERWRITING: frozenset((Policy.Status.ISSUED, Policy.Status.CANCELLED)),
    Policy.Status.ISSUED: frozenset((Policy.Status.ACTIVE, Policy.Status.CANCELLED)),
    Policy.Status.ACTIVE: frozenset((Policy.Status.EXPIRED, Policy.Status.CANCELLED)),
    Policy.Status.EXPIRED: frozenset(),
    Policy.Status.CANCELLED: frozenset(),
}


def transition_policy_status(
    *,
    company,
    actor,
    policy: Policy,
    to_status: str,
    request=None,
    reason: str = "",
) -> Policy:
    """Apply a minimal state machine transition and audit it."""

    if policy.company_id != company.id:
        raise ValidationError("Cross-tenant policy transition blocked.")

    from_status = policy.status
    allowed = _ALLOWED_TRANSITIONS.get(from_status, frozenset())
    if to_status not in allowed:
        raise ValidationError(
            {"status": f"Transition {from_status} -> {to_status} is not allowed."}
        )

    with transaction.atomic():
        before = _policy_snapshot(policy)
        policy.status = to_status

        update_fields = {"status", "updated_at"}
        if to_status in (Policy.Status.ISSUED, Policy.Status.ACTIVE) and policy.issue_date is None:
            policy.issue_date = date.today()
            update_fields.add("issue_date")

        policy.save(update_fields=tuple(sorted(update_fields)))

        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_UPDATE,
            event_type="insurance_core.policy.transition",
            resource_label="insurance_core.Policy",
            resource_pk=str(policy.pk),
            request=request,
            data_before=before,
            data_after=_policy_snapshot(policy),
            metadata={
                "from_status": from_status,
                "to_status": to_status,
                "reason": reason,
            },
        )
        return policy


def delete_policy(*, company, actor, policy: Policy, request=None) -> None:
    """Hard delete is allowed only for drafts; everything else must be cancelled."""

    if policy.company_id != company.id:
        raise ValidationError("Cross-tenant policy delete blocked.")
    if policy.status != Policy.Status.DRAFT:
        raise ValidationError({"detail": "Only DRAFT policies can be deleted."})

    with transaction.atomic():
        before = _policy_snapshot(policy)
        policy_pk = policy.pk
        policy.delete()
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_DELETE,
            event_type="insurance_core.policy.delete",
            resource_label="insurance_core.Policy",
            resource_pk=str(policy_pk),
            request=request,
            data_before=before,
            data_after=None,
        )


def upsert_policy_item(
    *,
    company,
    actor,
    instance: PolicyItem | None,
    data: dict,
    request=None,
) -> PolicyItem:
    policy = data.get("policy") or getattr(instance, "policy", None)
    if policy is None:
        raise ValidationError({"policy_id": "policy_id is required."})
    if policy.company_id != company.id:
        raise ValidationError({"policy_id": "Invalid policy for this tenant."})

    with transaction.atomic():
        if instance is None:
            item = PolicyItem(company=company, **data)
            item.save()
            publish_tenant_event(
                company=company,
                actor=actor,
                action=LedgerEntry.ACTION_CREATE,
                event_type="insurance_core.policy_item.create",
                resource_label="insurance_core.PolicyItem",
                resource_pk=str(item.pk),
                request=request,
                data_before=None,
                data_after=_policy_item_snapshot(item),
            )
            return item

        if instance.company_id != company.id:
            raise ValidationError("Cross-tenant policy item update blocked.")

        before = _policy_item_snapshot(instance)
        for key, value in data.items():
            setattr(instance, key, value)
        instance.save()
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_UPDATE,
            event_type="insurance_core.policy_item.update",
            resource_label="insurance_core.PolicyItem",
            resource_pk=str(instance.pk),
            request=request,
            data_before=before,
            data_after=_policy_item_snapshot(instance),
        )
        return instance


def delete_policy_item(*, company, actor, item: PolicyItem, request=None) -> None:
    if item.company_id != company.id:
        raise ValidationError("Cross-tenant policy item delete blocked.")

    with transaction.atomic():
        before = _policy_item_snapshot(item)
        pk = item.pk
        item.delete()
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_DELETE,
            event_type="insurance_core.policy_item.delete",
            resource_label="insurance_core.PolicyItem",
            resource_pk=str(pk),
            request=request,
            data_before=before,
            data_after=None,
        )


def upsert_policy_coverage(
    *,
    company,
    actor,
    instance: PolicyCoverage | None,
    data: dict,
    request=None,
) -> PolicyCoverage:
    policy = data.get("policy") or getattr(instance, "policy", None)
    product_coverage = data.get("product_coverage") or getattr(instance, "product_coverage", None)

    if policy is None:
        raise ValidationError({"policy_id": "policy_id is required."})
    if policy.company_id != company.id:
        raise ValidationError({"policy_id": "Invalid policy for this tenant."})

    if product_coverage is None:
        raise ValidationError({"product_coverage_id": "product_coverage_id is required."})
    if not ProductCoverage.all_objects.filter(company=company, id=product_coverage.id).exists():
        raise ValidationError({"product_coverage_id": "Invalid coverage for this tenant."})
    if product_coverage.product_id != policy.product_id:
        raise ValidationError({"product_coverage_id": "Coverage must belong to the policy product."})

    with transaction.atomic():
        if instance is None:
            coverage = PolicyCoverage(company=company, **data)
            coverage.save()
            publish_tenant_event(
                company=company,
                actor=actor,
                action=LedgerEntry.ACTION_CREATE,
                event_type="insurance_core.policy_coverage.create",
                resource_label="insurance_core.PolicyCoverage",
                resource_pk=str(coverage.pk),
                request=request,
                data_before=None,
                data_after=_policy_coverage_snapshot(coverage),
            )
            return coverage

        if instance.company_id != company.id:
            raise ValidationError("Cross-tenant policy coverage update blocked.")

        before = _policy_coverage_snapshot(instance)
        for key, value in data.items():
            setattr(instance, key, value)
        instance.save()
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_UPDATE,
            event_type="insurance_core.policy_coverage.update",
            resource_label="insurance_core.PolicyCoverage",
            resource_pk=str(instance.pk),
            request=request,
            data_before=before,
            data_after=_policy_coverage_snapshot(instance),
        )
        return instance


def delete_policy_coverage(*, company, actor, coverage: PolicyCoverage, request=None) -> None:
    if coverage.company_id != company.id:
        raise ValidationError("Cross-tenant policy coverage delete blocked.")

    with transaction.atomic():
        before = _policy_coverage_snapshot(coverage)
        pk = coverage.pk
        coverage.delete()
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_DELETE,
            event_type="insurance_core.policy_coverage.delete",
            resource_label="insurance_core.PolicyCoverage",
            resource_pk=str(pk),
            request=request,
            data_before=before,
            data_after=None,
        )


def upsert_policy_document_requirement(
    *,
    company,
    actor,
    instance: PolicyDocumentRequirement | None,
    data: dict,
    request=None,
) -> PolicyDocumentRequirement:
    policy = data.get("policy") or getattr(instance, "policy", None)
    if policy is None:
        raise ValidationError({"policy_id": "policy_id is required."})
    if policy.company_id != company.id:
        raise ValidationError({"policy_id": "Invalid policy for this tenant."})

    with transaction.atomic():
        if instance is None:
            docreq = PolicyDocumentRequirement(company=company, **data)
            docreq.save()
            publish_tenant_event(
                company=company,
                actor=actor,
                action=LedgerEntry.ACTION_CREATE,
                event_type="insurance_core.policy_docreq.create",
                resource_label="insurance_core.PolicyDocumentRequirement",
                resource_pk=str(docreq.pk),
                request=request,
                data_before=None,
                data_after=_policy_docreq_snapshot(docreq),
            )
            return docreq

        if instance.company_id != company.id:
            raise ValidationError("Cross-tenant policy doc requirement update blocked.")

        before = _policy_docreq_snapshot(instance)
        for key, value in data.items():
            setattr(instance, key, value)
        instance.save()
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_UPDATE,
            event_type="insurance_core.policy_docreq.update",
            resource_label="insurance_core.PolicyDocumentRequirement",
            resource_pk=str(instance.pk),
            request=request,
            data_before=before,
            data_after=_policy_docreq_snapshot(instance),
        )
        return instance


def delete_policy_document_requirement(
    *,
    company,
    actor,
    docreq: PolicyDocumentRequirement,
    request=None,
) -> None:
    if docreq.company_id != company.id:
        raise ValidationError("Cross-tenant policy doc requirement delete blocked.")

    with transaction.atomic():
        before = _policy_docreq_snapshot(docreq)
        pk = docreq.pk
        docreq.delete()
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_DELETE,
            event_type="insurance_core.policy_docreq.delete",
            resource_label="insurance_core.PolicyDocumentRequirement",
            resource_pk=str(pk),
            request=request,
            data_before=before,
            data_after=None,
        )


def upsert_endorsement(
    *,
    company,
    actor,
    instance: Endorsement | None,
    data: dict,
    request=None,
) -> Endorsement:
    policy = data.get("policy") or getattr(instance, "policy", None)
    if policy is None:
        raise ValidationError({"policy_id": "policy_id is required."})
    if policy.company_id != company.id:
        raise ValidationError({"policy_id": "Invalid policy for this tenant."})

    with transaction.atomic():
        if instance is None:
            endorsement = Endorsement(company=company, **data)
            endorsement.save()
            publish_tenant_event(
                company=company,
                actor=actor,
                action=LedgerEntry.ACTION_CREATE,
                event_type="insurance_core.endorsement.create",
                resource_label="insurance_core.Endorsement",
                resource_pk=str(endorsement.pk),
                request=request,
                data_before=None,
                data_after=_endorsement_snapshot(endorsement),
            )
            return endorsement

        if instance.company_id != company.id:
            raise ValidationError("Cross-tenant endorsement update blocked.")

        before = _endorsement_snapshot(instance)
        for key, value in data.items():
            setattr(instance, key, value)
        instance.save()
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_UPDATE,
            event_type="insurance_core.endorsement.update",
            resource_label="insurance_core.Endorsement",
            resource_pk=str(instance.pk),
            request=request,
            data_before=before,
            data_after=_endorsement_snapshot(instance),
        )
        return instance


def delete_endorsement(*, company, actor, endorsement: Endorsement, request=None) -> None:
    if endorsement.company_id != company.id:
        raise ValidationError("Cross-tenant endorsement delete blocked.")

    with transaction.atomic():
        before = _endorsement_snapshot(endorsement)
        pk = endorsement.pk
        endorsement.delete()
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_DELETE,
            event_type="insurance_core.endorsement.delete",
            resource_label="insurance_core.Endorsement",
            resource_pk=str(pk),
            request=request,
            data_before=before,
            data_after=None,
        )

