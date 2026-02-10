import datetime
from decimal import Decimal
from uuid import uuid4
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from insurance_core.models import Policy, Endorsement, Claim, PolicyDocument, PolicyBillingConfig
from insurance_core.events import publish_tenant_event
from insurance_core.outbox import publish_domain_event


def issue_policy(policy: Policy, user):
    if policy.status == Policy.STATUS_ISSUED:
        return

    with transaction.atomic():
        policy.status = Policy.STATUS_ISSUED
        policy.issue_date = timezone.localdate()
        policy.save(update_fields=["status", "issue_date", "updated_at"])

        publish_tenant_event(
            company=policy.company,
            actor=user,
            action="UPDATE",
            event_type="POLICY_ISSUED",
            resource_label="Policy",
            resource_pk=policy.pk,
            data_after={"status": policy.status, "policy_id": policy.id},
        )
        
        publish_domain_event(
            company=policy.company,
            event_type="POLICY_ISSUED",
            payload={"policy_id": policy.id}
        )


def create_endorsement(policy: Policy, endorsement_type: str, effective_date, premium_delta: Decimal = Decimal("0.00"), description: str = "", user=None):
    """
    Applies an endorsement to a policy, updating its state and publishing events for downstream systems.
    """
    with transaction.atomic():
        endorsement = Endorsement.objects.create(
            company=policy.company,
            policy=policy,
            endorsement_type=endorsement_type,
            premium_delta=premium_delta,
            issue_date=timezone.localdate(),
            effective_date=effective_date,
            description=description,
        )

        event_type = "ENDORSEMENT_APPLIED"
        event_data = {
            "endorsement_id": endorsement.id,
            "policy_id": policy.id,
            "endorsement_type": endorsement_type,
            "premium_delta": str(premium_delta),
            "effective_date": str(effective_date),
        }

        # Update Policy State
        if endorsement_type == Endorsement.TYPE_CANCEL:
            policy.status = Policy.STATUS_CANCELLED
            policy.end_date = effective_date  # Shorten validity
            policy.save(update_fields=["status", "end_date", "updated_at"])
            event_type = "POLICY_CANCELLED"
        
        elif endorsement_type in (Endorsement.TYPE_INCREASE, Endorsement.TYPE_DECREASE, Endorsement.TYPE_HEALTH_ADD_BENEFICIARY):
            if hasattr(policy, "billing_config"):
                policy.billing_config.premium_total += premium_delta
                policy.billing_config.save(update_fields=["premium_total", "updated_at"])

        publish_tenant_event(
            company=policy.company,
            actor=user,
            action="CREATE",
            event_type=event_type,
            resource_label="Endorsement",
            resource_pk=endorsement.pk,
            data_after=event_data,
        )

        publish_domain_event(
            company=policy.company,
            event_type=event_type,
            payload=event_data
        )

        return endorsement


def create_claim(policy: Policy, occurrence_date, report_date, description, amount_claimed=None, claim_number=None, user=None):
    if not claim_number:
        claim_number = f"CLM-{policy.id}-{int(timezone.now().timestamp())}"

    with transaction.atomic():
        claim = Claim.objects.create(
            company=policy.company,
            policy=policy,
            claim_number=claim_number,
            occurrence_date=occurrence_date,
            report_date=report_date,
            description=description,
            amount_claimed=amount_claimed,
            status=Claim.STATUS_OPEN,
        )

        publish_tenant_event(
            company=policy.company,
            actor=user,
            action="CREATE",
            event_type="CLAIM_OPENED",
            resource_label="Claim",
            resource_pk=claim.pk,
            data_after={
                "claim_number": claim.claim_number,
                "policy_id": policy.id,
                "status": claim.status,
            },
        )
        return claim


def transition_claim_status(claim: Claim, new_status: str, notes: str = "", amount_approved=None, user=None):
    valid_transitions = {
        Claim.STATUS_OPEN: {Claim.STATUS_IN_REVIEW, Claim.STATUS_CLOSED},
        Claim.STATUS_IN_REVIEW: {Claim.STATUS_APPROVED, Claim.STATUS_DENIED, Claim.STATUS_OPEN},
        Claim.STATUS_APPROVED: {Claim.STATUS_PAID, Claim.STATUS_CLOSED},
        Claim.STATUS_DENIED: {Claim.STATUS_CLOSED, Claim.STATUS_IN_REVIEW}, # Reopen review
        Claim.STATUS_PAID: {Claim.STATUS_CLOSED},
        Claim.STATUS_CLOSED: {Claim.STATUS_IN_REVIEW}, # Reopen
    }

    if new_status not in valid_transitions.get(claim.status, set()):
        raise ValidationError(f"Invalid transition from {claim.status} to {new_status}")

    with transaction.atomic():
        old_status = claim.status
        claim.status = new_status
        claim.status_notes = notes
        if amount_approved is not None and new_status == Claim.STATUS_APPROVED:
            claim.amount_approved = amount_approved
        
        claim.save(update_fields=["status", "status_notes", "amount_approved", "updated_at"])

        publish_tenant_event(
            company=claim.company,
            actor=user,
            action="UPDATE",
            event_type=f"CLAIM_{new_status}",
            resource_label="Claim",
            resource_pk=claim.pk,
            data_before={"status": old_status},
            data_after={"status": new_status, "notes": notes},
        )


def create_claim_document_upload_url(claim: Claim, file_name: str, content_type: str, file_size: int, user=None):
    """
    Generates a GCS Signed URL for direct upload and creates the PolicyDocument record.
    """
    bucket_name = getattr(settings, "CLOUD_STORAGE_BUCKET", "")
    storage_key = f"tenants/{claim.company.id}/claims/{claim.id}/{uuid4()}/{file_name}"

    try:
        from google.cloud import storage
        
        if not bucket_name:
            raise ValueError("CLOUD_STORAGE_BUCKET is not configured.")

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(storage_key)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            content_type=content_type,
        )
    except (ImportError, ValueError):
        # Fallback for local dev or missing creds
        if settings.DEBUG:
            url = f"http://localhost:8000/mock-upload/{storage_key}"
        else:
            raise

    doc = PolicyDocument.objects.create(
        company=claim.company,
        policy=claim.policy,
        claim=claim,
        document_type=PolicyDocument.TYPE_CLAIM,
        file_name=file_name,
        storage_key=storage_key,
        content_type=content_type,
        file_size=file_size,
    )
    
    return doc, url


def renew_policy(policy: Policy, user, start_date=None, end_date=None, policy_number=None, premium_total=None):
    if not start_date:
        start_date = policy.end_date + datetime.timedelta(days=1)
    if not end_date:
        # Default to same duration as previous policy
        duration = policy.end_date - policy.start_date
        end_date = start_date + duration
    
    if not policy_number:
        policy_number = f"{policy.policy_number}-REN"

    with transaction.atomic():
        new_policy = Policy.objects.create(
            company=policy.company,
            customer=policy.customer,
            insurer=policy.insurer,
            product=policy.product,
            branch=policy.branch,
            producer=policy.producer,
            policy_number=policy_number,
            start_date=start_date,
            end_date=end_date,
            status=Policy.STATUS_QUOTED,
            is_renewal=True,
        )

        if hasattr(policy, "billing_config"):
            old_config = policy.billing_config
            new_premium = premium_total if premium_total is not None else old_config.premium_total
            
            PolicyBillingConfig.objects.create(
                company=policy.company,
                policy=new_policy,
                first_installment_due_date=start_date + datetime.timedelta(days=30),
                installments_count=old_config.installments_count,
                premium_total=new_premium,
                commission_rate_percent=old_config.commission_rate_percent,
                original_premium_total=new_premium if policy.is_health_plan else None
            )
        
        publish_tenant_event(
            company=policy.company,
            actor=user,
            action="CREATE",
            event_type="POLICY_RENEWED",
            resource_label="Policy",
            resource_pk=new_policy.pk,
            data_after={"origin_policy_id": policy.id, "new_policy_id": new_policy.id},
        )
        
        return new_policy


def create_document_upload_url(company, entity, file_name, content_type, file_size, checksum="", user=None):
    """
    Generates a GCS Signed URL for direct upload and creates the PolicyDocument record (pending upload).
    Entity can be Policy, Endorsement, or Claim.
    """
    bucket_name = getattr(settings, "CLOUD_STORAGE_BUCKET", "")
    
    # Determine context and folder structure
    policy = None
    endorsement = None
    claim = None
    folder = "misc"

    if isinstance(entity, Policy):
        policy = entity
        folder = "policies"
    elif isinstance(entity, Endorsement):
        endorsement = entity
        policy = entity.policy
        folder = "endorsements"
    elif isinstance(entity, Claim):
        claim = entity
        policy = entity.policy
        folder = "claims"
    else:
        raise ValueError("Invalid entity type for document upload.")

    storage_key = f"tenants/{company.id}/{folder}/{entity.id}/{uuid4()}/{file_name}"

    try:
        from google.cloud import storage
        if not bucket_name:
            raise ValueError("CLOUD_STORAGE_BUCKET is not configured.")

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(storage_key)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            content_type=content_type,
        )
    except (ImportError, ValueError):
        if settings.DEBUG:
            url = f"http://localhost:8000/mock-upload/{storage_key}"
        else:
            raise

    doc = PolicyDocument.objects.create(
        company=company,
        policy=policy,
        endorsement=endorsement,
        claim=claim,
        document_type=PolicyDocument.TYPE_OTHER, # Can be updated later or inferred
        file_name=file_name,
        storage_key=storage_key,
        bucket_name=bucket_name,
        content_type=content_type,
        file_size=file_size,
        checksum=checksum,
    )
    
    return doc, url


def confirm_document_upload(document: PolicyDocument):
    """
    Marks the document as uploaded.
    """
    document.uploaded_at = timezone.now()
    document.save(update_fields=["uploaded_at", "updated_at"])
    return document


def get_document_download_url(document: PolicyDocument):
    """
    Generates a GCS Signed URL for downloading the document.
    """
    bucket_name = document.bucket_name or getattr(settings, "CLOUD_STORAGE_BUCKET", "")
    
    try:
        from google.cloud import storage
        if not bucket_name:
            raise ValueError("Bucket name not found.")

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(document.storage_key)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="GET",
        )
        return url
    except (ImportError, ValueError):
        if settings.DEBUG:
            return f"http://localhost:8000/mock-download/{document.storage_key}"
        return None