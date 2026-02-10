from datetime import timedelta
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from finance.models import Payable
from operational.models import (
    Endosso,
    Installment,
    OperationalIntegrationInbox,
)
from commission.models import (
    CommissionAccrual,
    CommissionPayoutBatch,
    CommissionPayoutItem,
    CommissionPlanScope,
    InsurerPayableAccrual,
    InsurerSettlementBatch,
    InsurerSettlementItem,
    ParticipantProfile,
)


def _get_applicable_plan(company, insurer_name, product_line):
    """
    Finds the highest priority commission plan that matches the criteria.
    Empty fields in the plan act as wildcards (match all).
    """
    plans = CommissionPlanScope.objects.filter(company=company).order_by("-priority")

    for plan in plans:
        match_insurer = not plan.insurer_name or plan.insurer_name == insurer_name
        match_product = not plan.product_line or plan.product_line == product_line

        if match_insurer and match_product:
            return plan
    return None


def _get_participant_type(user):
    if not user:
        return ""
    profile = getattr(user, "commission_profile", None)
    return profile.participant_type if profile else ""


def accrue_on_policy_issued(event: dict, company) -> None:
    event_id = event.get("id")
    if not event_id:
        return

    # Idempotency check
    if OperationalIntegrationInbox.objects.filter(company=company, event_id=event_id).exists():
        return

    endosso_id = event.get("data", {}).get("endosso_id")
    if not endosso_id:
        return

    with transaction.atomic():
        OperationalIntegrationInbox.objects.create(
            company=company,
            event_id=event_id,
            event_type="POLICY_ISSUED",
        )

        try:
            endosso = Endosso.objects.select_related("apolice").get(
                id=endosso_id, company=company
            )
        except Endosso.DoesNotExist:
            return

        plan = _get_applicable_plan(
            company, endosso.apolice.seguradora, endosso.apolice.ramo
        )

        if plan and plan.trigger_basis == CommissionPlanScope.BASIS_ISSUED:
            commission_amount = endosso.premio_liquido * (
                plan.commission_percent / Decimal("100.0")
            )

            # Recipient logic would go here (e.g. from Opportunity owner)
            # For now assuming None or derived elsewhere, but if we had it:
            CommissionAccrual.objects.create(
                company=company,
                content_object=endosso,
                amount=commission_amount,
                description=f"Comissão sobre Emissão Endosso {endosso.numero_endosso}",
                # recipient=..., recipient_type=...
            )

            InsurerPayableAccrual.objects.create(
                company=company,
                content_object=endosso,
                amount=commission_amount,
                insurer_name=endosso.apolice.seguradora,
            )


def apply_endorsement_delta(event: dict, company) -> None:
    """
    Calculates the difference between the current commission value of an endorsement
    and what has already been accrued. Creates a new accrual for the delta.
    """
    endosso_id = event.get("data", {}).get("endosso_id")
    if not endosso_id:
        return

    try:
        endosso = Endosso.objects.select_related("apolice").get(
            id=endosso_id, company=company
        )
    except Endosso.DoesNotExist:
        return

    # Determine the recipient (producer) from the customer or opportunity
    # Fallback to None if not assigned.
    # In a real scenario, we might traverse Endosso -> Apolice -> Opportunity -> Assigned To
    recipient = None
    # Assuming we can get it from the customer assigned_to for now, or extend models later.
    # For this implementation, we leave it blank or fetch if available.

    content_type = ContentType.objects.get_for_model(Endosso)
    
    # Calculate total already accrued for this endorsement
    existing_accruals = CommissionAccrual.objects.filter(
        company=company,
        content_type=content_type,
        object_id=endosso.id
    ).aggregate(total=Sum("amount"))
    
    accrued_total = existing_accruals.get("total") or Decimal("0.00")
    current_commission = endosso.valor_comissao
    
    delta = current_commission - accrued_total

    if delta == Decimal("0.00"):
        return

    description = f"Ajuste de Comissão (Endosso {endosso.numero_endosso})"
    if delta < 0:
        description = f"Estorno Parcial de Comissão (Endosso {endosso.numero_endosso})"

    recipient_type = _get_participant_type(recipient)

    CommissionAccrual.objects.create(
        company=company,
        content_type=content_type,
        object_id=endosso.id,
        amount=delta,
        description=description,
        status=CommissionAccrual.STATUS_PAYABLE, # Negative payable nets out positive ones
        recipient=recipient,
        recipient_type=recipient_type,
    )


def reverse_on_cancellation(event: dict, company) -> None:
    """
    Reverses all positive accruals associated with a policy or endorsement
    by creating offsetting negative accruals.
    """
    # Event could provide policy_id or endosso_id
    policy_id = event.get("data", {}).get("apolice_id")
    
    if not policy_id:
        return

    # Find all accruals related to this policy (via Endossos)
    # This requires finding all Endossos for the policy first
    endossos = Endosso.objects.filter(company=company, apolice_id=policy_id)
    endosso_ct = ContentType.objects.get_for_model(Endosso)

    accruals_to_reverse = CommissionAccrual.objects.filter(
        company=company,
        content_type=endosso_ct,
        object_id__in=endossos.values_list("id", flat=True),
        amount__gt=0 # Only reverse positive amounts
    )

    new_accruals = []
    for accrual in accruals_to_reverse:
        new_accruals.append(CommissionAccrual(
            company=company,
            content_type=accrual.content_type,
            object_id=accrual.object_id,
            amount=-accrual.amount,
            description=f"Estorno por Cancelamento - Ref: {accrual.id}",
            status=CommissionAccrual.STATUS_PAYABLE,
            recipient=accrual.recipient,
            recipient_type=accrual.recipient_type,
        ))
    
    if new_accruals:
        CommissionAccrual.objects.bulk_create(new_accruals)


def create_commission_payout_batch(company, period_from, period_to, created_by, producer_id=None, participant_type=None):
    """
    Creates a draft payout batch including all eligible (PAYABLE) accruals
    within the period.
    """
    qs = CommissionAccrual.objects.filter(
        company=company,
        status=CommissionAccrual.STATUS_PAYABLE,
        created_at__date__gte=period_from,
        created_at__date__lte=period_to,
        payout_item__isnull=True # Ensure not already in a batch
    )

    if producer_id:
        qs = qs.filter(recipient_id=producer_id)
    
    if participant_type:
        qs = qs.filter(recipient_type=participant_type)

    if not qs.exists():
        return None

    with transaction.atomic():
        batch = CommissionPayoutBatch.objects.create(
            company=company,
            period_start=period_from,
            period_end=period_to,
            status=CommissionPayoutBatch.STATUS_DRAFT,
            created_by=created_by,
        )

        total = Decimal("0.00")
        items = []
        for accrual in qs:
            # Apply payout rules (e.g. retention)
            payout_amount = accrual.amount
            if accrual.recipient:
                profile = getattr(accrual.recipient, "commission_profile", None)
                if profile and profile.payout_rules:
                    retention = profile.payout_rules.get("retention_percent")
                    if retention:
                        factor = Decimal("1.0") - (Decimal(str(retention)) / Decimal("100.0"))
                        payout_amount = payout_amount * factor
            
            payout_amount = payout_amount.quantize(Decimal("0.01"))
            items.append(CommissionPayoutItem(
                company=company,
                batch=batch,
                accrual=accrual,
                amount=payout_amount
            ))
            total += payout_amount
        
        CommissionPayoutItem.objects.bulk_create(items)
        
        batch.total_amount = total
        batch.save(update_fields=["total_amount"])
        
        return batch


def approve_commission_payout_batch(batch_id, user, company):
    with transaction.atomic():
        batch = CommissionPayoutBatch.objects.select_for_update().get(
            id=batch_id, company=company
        )

        if batch.status != CommissionPayoutBatch.STATUS_DRAFT:
            raise ValidationError("Only DRAFT batches can be approved.")

        # SoD Check: Creator cannot approve
        if batch.created_by_id == user.id:
            raise PermissionDenied("Segregation of Duties: Creator cannot approve their own batch.")
        
        batch.status = CommissionPayoutBatch.STATUS_APPROVED
        batch.approved_by = user
        batch.approved_at = timezone.now()
        batch.save()


def generate_payables_for_payout_batch(batch_id, company):
    """
    Processes an APPROVED batch, generating consolidated Payables in the Finance app
    and marking accruals as PAID.
    """
    with transaction.atomic():
        batch = CommissionPayoutBatch.objects.select_for_update().get(
            id=batch_id, company=company
        )

        if batch.status != CommissionPayoutBatch.STATUS_APPROVED:
            raise ValidationError("Batch must be APPROVED to generate payables.")

        # Group items by recipient
        items = batch.items.select_related("accrual").all()
        totals_by_recipient = {}
        
        for item in items:
            recipient_id = item.accrual.recipient_id
            if not recipient_id:
                continue
            totals_by_recipient[recipient_id] = totals_by_recipient.get(recipient_id, Decimal(0)) + item.amount

        # Create Payables
        due_date = timezone.localdate() + timedelta(days=5) # Business rule: pay in 5 days
        payables = []
        for recipient_id, amount in totals_by_recipient.items():
            payables.append(Payable(
                company=company,
                recipient_id=recipient_id,
                amount=amount,
                due_date=due_date,
                description=f"Comissão Ref. Lote {batch.id}",
                source_ref=str(batch.id)
            ))
        
        Payable.objects.bulk_create(payables)

        # Update Batch and Accruals
        batch.status = CommissionPayoutBatch.STATUS_PROCESSED
        batch.save(update_fields=["status", "updated_at"])
        

def create_insurer_settlement_batch(company, insurer_name, period_start, period_end, created_by):
    """
    Creates a draft settlement batch for a specific insurer.
    """
    qs = InsurerPayableAccrual.objects.filter(
        company=company,
        insurer_name=insurer_name,
        status=InsurerPayableAccrual.STATUS_PENDING,
        created_at__date__gte=period_start,
        created_at__date__lte=period_end,
        settlement_item__isnull=True
    )

    if not qs.exists():
        return None

    with transaction.atomic():
        batch = InsurerSettlementBatch.objects.create(
            company=company,
            insurer_name=insurer_name,
            period_start=period_start,
            period_end=period_end,
            status=InsurerSettlementBatch.STATUS_DRAFT,
            created_by=created_by,
        )

        total = Decimal("0.00")
        items = []
        for accrual in qs:
            items.append(InsurerSettlementItem(
                company=company,
                batch=batch,
                accrual=accrual,
                amount=accrual.amount
            ))
            total += accrual.amount
        
        InsurerSettlementItem.objects.bulk_create(items)
        batch.total_amount = total
        batch.save(update_fields=["total_amount"])
        
        return batch


def approve_insurer_settlement_batch(batch_id, user, company):
    with transaction.atomic():
        batch = InsurerSettlementBatch.objects.select_for_update().get(id=batch_id, company=company)
        
        if batch.status != InsurerSettlementBatch.STATUS_DRAFT:
            raise ValidationError("Only DRAFT batches can be approved.")
        
        if batch.created_by_id == user.id:
            raise PermissionDenied("Segregation of Duties: Creator cannot approve their own batch.")
            
        batch.status = InsurerSettlementBatch.STATUS_APPROVED
        batch.approved_by = user
        batch.approved_at = timezone.now()
        batch.save()


def generate_payables_for_insurer_settlement(batch_id, company):
    with transaction.atomic():
        batch = InsurerSettlementBatch.objects.select_for_update().get(id=batch_id, company=company)
        if batch.status != InsurerSettlementBatch.STATUS_APPROVED:
            raise ValidationError("Batch must be APPROVED to generate payables.")

        Payable.objects.create(
            company=company,
            beneficiary_name=batch.insurer_name,
            amount=batch.total_amount,
            due_date=timezone.localdate() + timedelta(days=10),
            description=f"Repasse Seguradora {batch.insurer_name} - Lote {batch.id}",
            source_ref=str(batch.id)
        )

        batch.status = InsurerSettlementBatch.STATUS_PROCESSED
        batch.save(update_fields=["status", "updated_at"])


def confirm_commission_payout(event: dict, company) -> None:
    event_id = event.get("id")
    if not event_id:
        return

    if OperationalIntegrationInbox.objects.filter(company=company, event_id=event_id).exists():
        return

    batch_id = event.get("data", {}).get("batch_id")
    if not batch_id:
        return

    with transaction.atomic():
        OperationalIntegrationInbox.objects.create(
            company=company,
            event_id=event_id,
            event_type="COMMISSION_PAYOUT_CONFIRMED",
        )

        batch = CommissionPayoutBatch.objects.select_for_update().get(id=batch_id, company=company)
        if batch.status != CommissionPayoutBatch.STATUS_PROCESSED:
            # Only processed batches can be confirmed paid
            return

        batch.status = CommissionPayoutBatch.STATUS_PAID
        batch.save(update_fields=["status", "updated_at"])

        batch.items.update(status=CommissionPayoutItem.STATUS_PAID)

        accrual_ids = batch.items.values_list("accrual_id", flat=True)
        CommissionAccrual.objects.filter(id__in=accrual_ids).update(
            status=CommissionAccrual.STATUS_PAID,
            updated_at=timezone.now()
        )


def confirm_insurer_settlement(event: dict, company) -> None:
    event_id = event.get("id")
    if not event_id:
        return

    if OperationalIntegrationInbox.objects.filter(company=company, event_id=event_id).exists():
        return

    batch_id = event.get("data", {}).get("batch_id")
    if not batch_id:
        return

    with transaction.atomic():
        OperationalIntegrationInbox.objects.create(
            company=company,
            event_id=event_id,
            event_type="INSURER_SETTLEMENT_CONFIRMED",
        )

        batch = InsurerSettlementBatch.objects.select_for_update().get(id=batch_id, company=company)
        if batch.status != InsurerSettlementBatch.STATUS_PROCESSED:
            return

        batch.status = InsurerSettlementBatch.STATUS_PAID
        batch.save(update_fields=["status", "updated_at"])

        batch.items.update(status=InsurerSettlementItem.STATUS_PAID)

        accrual_ids = batch.items.values_list("accrual_id", flat=True)
        InsurerPayableAccrual.objects.filter(id__in=accrual_ids).update(
            status=InsurerPayableAccrual.STATUS_SETTLED,
            updated_at=timezone.now()
        )


def accrue_on_installment_paid(event: dict, company) -> None:
    event_id = event.get("id")
    if not event_id:
        return

    if OperationalIntegrationInbox.objects.filter(company=company, event_id=event_id).exists():
        return

    installment_id = event.get("data", {}).get("installment_id")
    if not installment_id:
        return

    with transaction.atomic():
        OperationalIntegrationInbox.objects.create(
            company=company,
            event_id=event_id,
            event_type="INSTALLMENT_PAID",
        )

        try:
            installment = Installment.objects.select_related("endosso__apolice").get(
                id=installment_id, company=company
            )
        except Installment.DoesNotExist:
            return

        endosso = installment.endosso
        plan = _get_applicable_plan(
            company, endosso.apolice.seguradora, endosso.apolice.ramo
        )

        if plan and plan.trigger_basis == CommissionPlanScope.BASIS_PAID:
            commission_amount = installment.amount * (
                plan.commission_percent / Decimal("100.0")
            )

            CommissionAccrual.objects.create(
                company=company,
                content_object=installment,
                amount=commission_amount,
                description=f"Comissão sobre Parcela {installment.number} - Endosso {endosso.numero_endosso}",
            )

            InsurerPayableAccrual.objects.create(
                company=company,
                content_object=installment,
                amount=commission_amount,
                insurer_name=endosso.apolice.seguradora,
            )