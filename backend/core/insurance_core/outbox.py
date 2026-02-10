from uuid import uuid4
from insurance_core.models import DomainEventOutbox

def publish_domain_event(*, company, event_type: str, payload: dict, correlation_id: str = None):
    """
    Persists a domain event to the outbox within the current transaction.
    """
    DomainEventOutbox.objects.create(
        company=company,
        event_type=event_type,
        payload=payload,
        correlation_id=correlation_id or str(uuid4()),
    )