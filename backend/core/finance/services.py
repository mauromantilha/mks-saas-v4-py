from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from finance.models import IntegrationInbox, ReceivableInvoice, ReceivableInstallment
from insurance_core.models import Policy
from ledger.services import append_ledger_entry
from operational.models import Customer


def create_receivables_from_policy_event(event: dict, company):
    event_id = event.get("id")
    if not event_id:
        return

    if IntegrationInbox.all_objects.filter(company=company, event_id=event_id).exists():
        return

    policy_id = event.get("data", {}).get("policy_id")
    if not policy_id:
        return

    with transaction.atomic():
        IntegrationInbox.all_objects.create(
            company=company,
            event_id=event_id,
            event_type="POLICY_ISSUED_RECEIVABLES",
        )

        try:
            policy = Policy.all_objects.select_related("billing_config").get(
                id=policy_id, company=company
            )
        except Policy.DoesNotExist:
            return

        if not hasattr(policy, "billing_config"):
            return

        payer = getattr(policy, "customer", None)
        if payer is None:
            insured_party_id = getattr(policy, "insured_party_id", None)
            if insured_party_id is None:
                return
            try:
                payer = Customer.all_objects.get(company=company, id=insured_party_id)
            except ObjectDoesNotExist:
                return

        billing = policy.billing_config
        total_amount = billing.premium_total
        count = billing.installments_count
        first_due_date = billing.first_installment_due_date

        invoice = ReceivableInvoice.objects.create(
            company=company,
            payer=payer,
            policy=policy,
            total_amount=total_amount,
            issue_date=timezone.localdate(),
            description=f"Prêmio Apólice {policy.policy_number}",
            status=ReceivableInvoice.STATUS_OPEN,
        )

        installment_value = (total_amount / count).quantize(Decimal("0.01"))
        total_calculated = installment_value * count
        diff = total_amount - total_calculated

        installments = []
        for i in range(1, count + 1):
            amount = installment_value
            if i == count:
                amount += diff
            
            due_date = first_due_date + relativedelta(months=i-1)
            installments.append(ReceivableInstallment(
                company=company,
                invoice=invoice,
                number=i,
                amount=amount,
                due_date=due_date,
                status=ReceivableInstallment.STATUS_OPEN
            ))
        
        ReceivableInstallment.objects.bulk_create(installments)

        append_ledger_entry(
            scope="TENANT",
            company=company,
            actor=None,
            action="CREATE",
            resource_label="ReceivableInvoice",
            resource_pk=str(invoice.pk),
            event_type="FINANCE_RECEIVABLES_GENERATED",
            data_after={"total_amount": str(total_amount), "installments_count": count},
            metadata={"policy_id": policy.id}
        )


def sync_receivable_invoice_status(invoice: ReceivableInvoice) -> ReceivableInvoice:
    """Keep invoice status consistent with installment settlement state."""

    if invoice.status == ReceivableInvoice.STATUS_CANCELLED:
        return invoice

    has_open_installments = invoice.installments.filter(
        status=ReceivableInstallment.STATUS_OPEN
    ).exists()
    next_status = (
        ReceivableInvoice.STATUS_OPEN
        if has_open_installments
        else ReceivableInvoice.STATUS_PAID
    )

    if invoice.status != next_status:
        invoice.status = next_status
        invoice.save(update_fields=["status", "updated_at"])

    return invoice


def settle_receivable_installment(
    *,
    company,
    installment: ReceivableInstallment,
    actor=None,
    request=None,
):
    """Settle a receivable installment and recompute parent invoice status."""

    if installment.company_id != company.id:
        raise ValidationError("Installment does not belong to the active tenant.")

    if installment.status != ReceivableInstallment.STATUS_OPEN:
        raise ValidationError("Only OPEN installments can be settled.")

    with transaction.atomic():
        installment.status = ReceivableInstallment.STATUS_PAID
        installment.save(update_fields=["status", "updated_at"])

        invoice = sync_receivable_invoice_status(installment.invoice)

        append_ledger_entry(
            scope="TENANT",
            company=company,
            actor=actor,
            action="SETTLE",
            resource_label="ReceivableInstallment",
            resource_pk=str(installment.pk),
            request=request,
            data_after={
                "status": installment.status,
                "invoice_id": installment.invoice_id,
                "invoice_status": invoice.status,
            },
            metadata={
                "invoice_id": installment.invoice_id,
                "policy_id": invoice.policy_id,
            },
        )

    return installment


def process_endorsement_financial_impact(event: dict, company) -> None:
    event_id = event.get("id")
    if not event_id or IntegrationInbox.all_objects.filter(company=company, event_id=event_id).exists():
        return

    data = event.get("data", {})
    policy_id = data.get("policy_id")
    effective_date_str = data.get("effective_date")
    premium_delta = Decimal(data.get("premium_delta", "0.00"))
    endorsement_type = data.get("endorsement_type")

    if not policy_id or not effective_date_str:
        return

    with transaction.atomic():
        IntegrationInbox.all_objects.create(
            company=company,
            event_id=event_id,
            event_type="ENDORSEMENT_FINANCE_IMPACT",
        )

        # Handle Cancellation
        if endorsement_type == "CANCELLATION_ENDORSEMENT":
            # Cancel all future open installments
            ReceivableInstallment.objects.filter(
                company=company,
                invoice__policy_id=policy_id,
                status=ReceivableInstallment.STATUS_OPEN,
                due_date__gte=effective_date_str
            ).update(status=ReceivableInstallment.STATUS_CANCELLED)
            return

        # Handle Premium Changes (Increase/Decrease)
        if premium_delta == Decimal("0.00"):
            return

        # Find eligible future installments
        installments = ReceivableInstallment.objects.filter(
            company=company,
            invoice__policy_id=policy_id,
            status=ReceivableInstallment.STATUS_OPEN,
            due_date__gte=effective_date_str
        ).order_by("due_date", "number")

        count = installments.count()
        if count == 0:
            return

        # Distribute delta
        delta_per_installment = (premium_delta / count).quantize(Decimal("0.01"))
        remainder = premium_delta - (delta_per_installment * count)

        updates = []
        for idx, installment in enumerate(installments):
            adjustment = delta_per_installment
            if idx == 0:
                adjustment += remainder
            
            installment.amount += adjustment
            
            # Safety check: if decrease makes it negative, we might want to cap at 0 or allow credit.
            # For this implementation, we assume business rules prevent excessive decreases or allow negative (credit).
            # We'll allow negative as it represents a credit to the customer.
            
            updates.append(installment)

        ReceivableInstallment.objects.bulk_update(updates, ["amount"])


def preview_endorsement_impact(company, policy_id, endorsement_type, premium_delta, effective_date):
    """
    Simulates the financial impact of an endorsement on future installments.
    Returns a list of dicts with the preview.
    """
    installments = ReceivableInstallment.objects.filter(
        company=company,
        invoice__policy_id=policy_id,
        status=ReceivableInstallment.STATUS_OPEN,
        due_date__gte=effective_date
    ).order_by("due_date", "number")

    results = []
    
    # Logic for Cancellation
    if endorsement_type == "CANCELLATION_ENDORSEMENT":
        for inst in installments:
            results.append({
                "number": inst.number,
                "due_date": inst.due_date,
                "original_amount": inst.amount,
                "new_amount": Decimal("0.00"),
                "delta": -inst.amount,
                "status": "CANCELLED"
            })
        return results

    # Logic for Premium Changes
    count = installments.count()
    if count == 0:
        return []

    delta_per_installment = (premium_delta / count).quantize(Decimal("0.01"))
    remainder = premium_delta - (delta_per_installment * count)

    for idx, inst in enumerate(installments):
        adjustment = delta_per_installment
        if idx == 0:
            adjustment += remainder
        
        new_amount = inst.amount + adjustment
        results.append({
            "number": inst.number,
            "due_date": inst.due_date,
            "original_amount": inst.amount,
            "new_amount": new_amount,
            "delta": adjustment,
            "status": "OPEN"
        })
    
    return results
