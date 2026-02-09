import hashlib
import hmac
import json
from decimal import Decimal

from django.test import TestCase, override_settings

from customers.models import Company
from finance.fiscal.models import FiscalDocument, FiscalJob


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256).hexdigest()


@override_settings(
    ALLOWED_HOSTS=["testserver", ".example.com"],
    FISCAL_WEBHOOK_SECRET="test-secret",
)
class FiscalWebhookTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Empresa A",
            tenant_code="acme",
            subdomain="acme",
        )

        self.doc = FiscalDocument.all_objects.create(
            company=self.company,
            invoice_id=1,
            provider_document_id="mock:abc",
            amount=Decimal("10.00"),
            status=FiscalDocument.Status.EMITTING,
        )
        self.job = FiscalJob.all_objects.create(
            fiscal_document=self.doc,
            status=FiscalJob.Status.FAILED,
            attempts=1,
            last_error="timeout",
        )

    def test_webhook_rejects_invalid_signature(self):
        body = json.dumps(
            {"provider_document_id": "mock:abc", "status": "AUTHORIZED"},
            separators=(",", ":"),
        ).encode("utf-8")
        resp = self.client.post(
            "/api/finance/fiscal/webhook/",
            data=body,
            content_type="application/json",
            HTTP_X_TENANT_ID="acme",
            HTTP_X_FISCAL_SIGNATURE="bad",
        )
        self.assertEqual(resp.status_code, 401)

    def test_webhook_updates_status_and_xml_and_marks_job_succeeded(self):
        payload = {
            "provider_document_id": "mock:abc",
            "status": "AUTHORIZED",
            "xml_content": "<xml/>",
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        sig = _sign("test-secret", body)

        resp = self.client.post(
            "/api/finance/fiscal/webhook/",
            data=body,
            content_type="application/json",
            HTTP_X_TENANT_ID="acme",
            HTTP_X_FISCAL_SIGNATURE=sig,
            HTTP_X_CORRELATION_ID="corr-1",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

        self.doc.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(self.doc.status, FiscalDocument.Status.AUTHORIZED)
        self.assertEqual(self.doc.xml_content, "<xml/>")
        self.assertEqual(self.job.status, FiscalJob.Status.SUCCEEDED)
        self.assertIsNone(self.job.next_retry_at)

