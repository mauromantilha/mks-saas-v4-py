from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from finance.models import ReceivableInstallment
from operational.models import OperationalIntegrationInbox
from commission.engine import CommissionEngine
from commission.models import ParticipantProfile, CommissionAccrual


def process_installment_paid_event(event: dict, company) -> None:
    event_id = event.get("id")
    if not event_id:
        return

    # Idempotency check
    if OperationalIntegrationInbox.objects.filter(company=company, event_id=event_id).exists():
        return

    installment_id = event.get("data", {}).get("installment_id")
    if not installment_id:
        return

    with transaction.atomic():
        OperationalIntegrationInbox.objects.create(
            company=company,
            event_id=event_id,
            event_type="INSTALLMENT_PAID_COMMISSION",
        )

        try:
            # Fetch the finance installment
            installment = ReceivableInstallment.objects.select_related(
                "invoice__policy__branch",
                "invoice__policy__billing_config"
            ).get(id=installment_id, company=company)
        except ReceivableInstallment.DoesNotExist:
            return

        policy = installment.invoice.policy
        if not policy:
            return

        # Calculate Commission
        engine = CommissionEngine()
        commission_amount = engine.calculate(
            policy=policy,
            installment_number=installment.number,
            paid_amount=installment.amount
        )

        if commission_amount <= 0:
            return

        # Create Accrual
        # We link the accrual to the ReceivableInstallment from finance
        content_type = ContentType.objects.get_for_model(ReceivableInstallment)
        
        # Determine recipient (e.g. from Policy -> Customer -> Assigned To)
        recipient = policy.customer.assigned_to
        recipient_type = ""
        if recipient:
            try:
                profile = recipient.commission_profile
                recipient_type = profile.participant_type
            except ParticipantProfile.DoesNotExist:
                pass

        CommissionAccrual.objects.create(
            company=company,
            content_type=content_type,
            object_id=installment.id,
            amount=commission_amount,
            description=f"Comissão Parc. {installment.number}/{policy.billing_config.installments_count} - Apólice {policy.policy_number}",
            status=CommissionAccrual.STATUS_PAYABLE # Paid basis means it becomes payable immediately upon receipt
            recipient=recipient,
            recipient_type=recipient_type,
        )


def process_endorsement_commission_impact(event: dict, company) -> None:
    """
    Handles endorsement events. For PAID basis commissions, the financial adjustment
    on installments will automatically adjust future commissions.
    For CANCELLATION, we might need to log or handle specific reversals.
    """
    event_id = event.get("id")
    if not event_id or OperationalIntegrationInbox.objects.filter(company=company, event_id=event_id).exists():
        return

    with transaction.atomic():
        OperationalIntegrationInbox.objects.create(
            company=company,
            event_id=event_id,
            event_type="ENDORSEMENT_COMMISSION_IMPACT",
        )
        # Logic for reversals (e.g. clawback on unearned premium) would go here.
        # Currently, adjusting future installments in Finance handles the 'future' aspect.