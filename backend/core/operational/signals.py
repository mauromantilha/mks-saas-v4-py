import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from insurance_core.models import PolicyDocument
from operational.ai_document_indexing_service import (
    index_policy_document,
    index_special_project_document,
)
from operational.models import SpecialProjectDocument

logger = logging.getLogger(__name__)


@receiver(post_save, sender=PolicyDocument)
def index_policy_document_on_confirm_upload(sender, instance, created, **kwargs):
    if kwargs.get("raw"):
        return
    if not instance.uploaded_at or instance.deleted_at:
        return
    try:
        index_policy_document(instance)
    except Exception:
        logger.exception("Failed to index policy document id=%s", instance.pk)


@receiver(post_save, sender=SpecialProjectDocument)
def index_special_project_document_on_save(sender, instance, created, **kwargs):
    if kwargs.get("raw"):
        return
    if not getattr(instance, "file", None):
        return
    try:
        index_special_project_document(instance)
    except Exception:
        logger.exception("Failed to index special project document id=%s", instance.pk)

