from __future__ import annotations

import hashlib
import hmac
import json
import logging
from uuid import uuid4

from django.conf import settings
from django.db import connection, transaction
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status as drf_status

from ledger.models import LedgerEntry
from ledger.services import append_ledger_entry
from finance.fiscal.models import FiscalDocument, FiscalJob
from finance.fiscal.services import _normalize_fiscal_status
from tenancy.logging import mask_cpf_cnpj

logger = logging.getLogger(__name__)


def _parse_signature(value: str) -> str:
    raw = (value or "").strip()
    if raw.lower().startswith("sha256="):
        raw = raw.split("=", 1)[1].strip()
    return raw


def _get_correlation_id(request) -> str:
    correlation_id = (request.headers.get("X-Correlation-ID") or "").strip()
    if not correlation_id:
        correlation_id = (request.headers.get("X-Request-ID") or "").strip()
    return correlation_id or str(uuid4())


class FiscalWebhookAPIView(APIView):
    """Webhook endpoint for fiscal providers.

    This endpoint is tenant-scoped (called on the tenant hostname / schema), and uses a shared secret
    signature check to authenticate the caller. Do NOT expose this endpoint without signature
    validation.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        correlation_id = _get_correlation_id(request)
        company = getattr(request, "company", None)
        tenant_id = getattr(company, "id", None)

        raw_body: bytes = request.body or b""
        secret = getattr(settings, "FISCAL_WEBHOOK_SECRET", "") or ""
        if not secret:
            logger.error(
                "fiscal.webhook.secret_missing tenant_id=%s correlation_id=%s",
                tenant_id,
                correlation_id,
            )
            return Response(
                {"detail": "Webhook secret is not configured."},
                status=drf_status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        provided = _parse_signature(request.headers.get("X-Fiscal-Signature", ""))
        expected = hmac.new(
            secret.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        if not provided or not hmac.compare_digest(provided, expected):
            logger.warning(
                "fiscal.webhook.signature_invalid tenant_id=%s correlation_id=%s",
                tenant_id,
                correlation_id,
            )
            return Response(
                {"detail": "Invalid signature."},
                status=drf_status.HTTP_401_UNAUTHORIZED,
            )

        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            logger.warning(
                "fiscal.webhook.json_invalid tenant_id=%s correlation_id=%s",
                tenant_id,
                correlation_id,
            )
            return Response({"detail": "Invalid JSON."}, status=drf_status.HTTP_400_BAD_REQUEST)

        provider_document_id = str(
            payload.get("provider_document_id") or payload.get("document_id") or ""
        ).strip()
        status_value = payload.get("status")
        xml_document_id = str(payload.get("xml_document_id") or "").strip()
        xml_content = str(payload.get("xml_content") or payload.get("xml") or "").strip()

        if not provider_document_id:
            return Response(
                {"detail": "provider_document_id is required."},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        if not status_value:
            return Response(
                {"detail": "status is required."},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        new_status = _normalize_fiscal_status(status_value)

        logger.info(
            "fiscal.webhook.received tenant_id=%s document_id=%s correlation_id=%s status=%s",
            tenant_id,
            provider_document_id,
            correlation_id,
            str(status_value).strip(),
        )

        # Apply the event inside a transaction.
        with transaction.atomic():
            doc_qs = FiscalDocument.objects
            job_qs = FiscalJob.all_objects
            if connection.features.has_select_for_update:
                doc_qs = doc_qs.select_for_update()
                job_qs = job_qs.select_for_update()

            doc = doc_qs.filter(provider_document_id=provider_document_id).first()
            if doc is None:
                return Response(
                    {"detail": "Fiscal document not found."},
                    status=drf_status.HTTP_404_NOT_FOUND,
                )

            before_status = doc.status
            changed_fields: list[str] = ["updated_at"]
            if new_status and new_status != doc.status:
                doc.status = new_status
                changed_fields.append("status")
            if xml_document_id and xml_document_id != (doc.xml_document_id or ""):
                doc.xml_document_id = xml_document_id
                changed_fields.append("xml_document_id")
            if xml_content and xml_content != (doc.xml_content or ""):
                doc.xml_content = xml_content
                changed_fields.append("xml_content")

            if len(changed_fields) > 1:
                doc.save(update_fields=sorted(set(changed_fields)))

            # If there is a job, mark it succeeded when the document reaches a final status.
            job_id = None
            job = job_qs.filter(fiscal_document_id=doc.id).first()
            if job is not None:
                job_id = job.id
                if doc.status in {
                    FiscalDocument.Status.AUTHORIZED,
                    FiscalDocument.Status.REJECTED,
                    FiscalDocument.Status.CANCELLED,
                }:
                    job.status = FiscalJob.Status.SUCCEEDED
                    job.next_retry_at = None
                    job.last_error = ""
                    job.save(update_fields=["status", "next_retry_at", "last_error", "updated_at"])

            append_ledger_entry(
                scope=LedgerEntry.SCOPE_TENANT,
                company=doc.company,
                actor=None,
                action=LedgerEntry.ACTION_UPDATE,
                resource_label="finance.fiscal.FiscalDocument",
                resource_pk=str(doc.id),
                request=request,
                event_type="finance.fiscal.webhook",
                data_before={"id": doc.id, "status": before_status},
                data_after={"id": doc.id, "status": doc.status},
                metadata={
                    "provider_document_id": provider_document_id,
                    "job_id": job_id,
                    "correlation_id": correlation_id,
                },
            )

        logger.info(
            "fiscal.webhook.applied tenant_id=%s document_id=%s job_id=%s correlation_id=%s old_status=%s new_status=%s",
            tenant_id,
            provider_document_id,
            job_id or "",
            correlation_id,
            before_status,
            new_status,
        )

        return Response(
            {
                "ok": True,
                "tenant_id": tenant_id,
                "document_id": provider_document_id,
                "job_id": job_id,
                "status": new_status,
                "correlation_id": correlation_id,
            },
            status=drf_status.HTTP_200_OK,
        )

    def handle_exception(self, exc):  # pragma: no cover
        error_msg = mask_cpf_cnpj(str(exc))
        logger.exception("fiscal.webhook.exception error=%s", error_msg)
        return Response(
            {"detail": "Webhook processing error."},
            status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

