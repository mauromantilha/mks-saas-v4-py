from dataclasses import dataclass

from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from control_plane.models import (
    ContractEmailLog,
    Tenant,
    TenantContractDocument,
    TenantPlanSubscription,
)
from control_plane.services.resend_client import ResendError, send_email


class ContractServiceError(Exception):
    pass


@dataclass(frozen=True)
class ContractSendResult:
    contract: TenantContractDocument
    email_log: ContractEmailLog


def _build_snapshot(tenant: Tenant, subscription: TenantPlanSubscription | None) -> dict:
    plan_name = ""
    monthly_price = None
    setup_fee = None
    trial_ends_at = None
    is_trial = False
    is_courtesy = False
    setup_fee_override = None

    if subscription is not None:
        plan_name = subscription.plan.name
        if getattr(subscription.plan, "price", None) is not None:
            monthly_price = str(subscription.plan.price.monthly_price)
            setup_fee = str(subscription.plan.price.setup_fee)
        trial_ends_at = str(subscription.trial_ends_at) if subscription.trial_ends_at else None
        is_trial = bool(subscription.is_trial)
        is_courtesy = bool(subscription.is_courtesy)
        setup_fee_override = (
            str(subscription.setup_fee_override) if subscription.setup_fee_override is not None else None
        )

    # LGPD: keep only strictly necessary contract metadata.
    return {
        "tenant_id": tenant.id,
        "legal_name": tenant.legal_name,
        "cnpj": tenant.cnpj,
        "subdomain": tenant.subdomain,
        "address": {
            "cep": tenant.cep,
            "street": tenant.street,
            "number": tenant.number,
            "complement": tenant.complement,
            "district": tenant.district,
            "city": tenant.city,
            "state": tenant.state,
        },
        "plan": {
            "name": plan_name,
            "monthly_price": monthly_price,
            "setup_fee": setup_fee,
            "is_trial": is_trial,
            "trial_ends_at": trial_ends_at,
            "is_courtesy": is_courtesy,
            "setup_fee_override": setup_fee_override,
        },
        "generated_at": timezone.now().isoformat(),
    }


def generate_contract(tenant_id: int) -> TenantContractDocument:
    tenant = Tenant.objects.select_related("company").get(id=tenant_id)
    latest = tenant.contracts.order_by("-contract_version").first()
    next_version = (latest.contract_version + 1) if latest else 1
    subscription = tenant.subscriptions.filter(status=TenantPlanSubscription.STATUS_ACTIVE).select_related(
        "plan", "plan__price"
    ).first()
    snapshot = _build_snapshot(tenant, subscription)

    contract = TenantContractDocument.objects.create(
        tenant=tenant,
        status=TenantContractDocument.STATUS_DRAFT,
        contract_version=next_version,
        snapshot_json=snapshot,
    )
    return contract


def send_contract_email(contract_id: int, *, to_email: str, force_send: bool = False) -> ContractSendResult:
    with transaction.atomic():
        contract = TenantContractDocument.objects.select_for_update().select_related("tenant").get(id=contract_id)

        if contract.status == TenantContractDocument.STATUS_SENT and not force_send:
            raise ContractServiceError("Contract already sent. Set force_send=true to resend intentionally.")
        if contract.status == TenantContractDocument.STATUS_CANCELLED:
            raise ContractServiceError("Cancelled contracts cannot be sent.")

        email_log = ContractEmailLog.objects.create(
            contract=contract,
            to_email=to_email,
            status=ContractEmailLog.STATUS_PENDING,
            sent_at=None,
        )

        context = {
            "contract": contract,
            "tenant": contract.tenant,
            "snapshot": contract.snapshot_json,
        }
        subject = f"Contrato SaaS - {contract.tenant.legal_name} (v{contract.contract_version})"
        html = render_to_string("control_plane/email/contract_email.html", context)
        text = render_to_string("control_plane/email/contract_email.txt", context)

        try:
            message_id = send_email(
                to_email=to_email,
                subject=subject,
                html=html,
                text=text,
            )
        except ResendError as exc:
            email_log.status = ContractEmailLog.STATUS_FAILED
            email_log.error = str(exc)
            email_log.sent_at = timezone.now()
            email_log.save(update_fields=["status", "error", "sent_at"])
            raise ContractServiceError(str(exc)) from exc

        email_log.status = ContractEmailLog.STATUS_SENT
        email_log.resend_message_id = message_id
        email_log.error = ""
        email_log.sent_at = timezone.now()
        email_log.save(update_fields=["status", "resend_message_id", "error", "sent_at"])

        contract.status = TenantContractDocument.STATUS_SENT
        contract.save(update_fields=["status"])
        return ContractSendResult(contract=contract, email_log=email_log)
