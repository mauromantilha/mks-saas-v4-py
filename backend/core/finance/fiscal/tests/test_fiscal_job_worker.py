from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings

from customers.models import Company
from finance.fiscal.adapters import FiscalAdapterBase, FiscalAdapterFiscalRejectionError, FiscalAdapterTimeoutError
from finance.fiscal.models import FiscalDocument, FiscalJob, FiscalProvider, TenantFiscalConfig
from finance.fiscal.services import enqueue_fiscal_job, process_fiscal_job
from tenancy.context import reset_current_company, set_current_company


def _set_tenant_schema(company: Company) -> None:
    # Works with django-tenants when enabled; no-op otherwise.
    setter = getattr(connection, "set_tenant", None)
    if callable(setter):
        setter(company)


def _reset_public_schema() -> None:
    setter = getattr(connection, "set_schema_to_public", None)
    if callable(setter):
        setter()


@override_settings(
    ALLOWED_HOSTS=["testserver", ".example.com"],
    FISCAL_INVOICE_RESOLVER="finance.fiscal.tests.resolvers.mock_invoice_resolver",
)
class FiscalJobWorkerTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.company = Company.objects.create(
            name="Empresa A",
            tenant_code="acme",
            subdomain="acme",
        )
        self.actor = User.objects.create_user(
            username="actor",
            email="actor@acme.com",
            password="pass",
        )

        _set_tenant_schema(self.company)
        self._tenant_token = set_current_company(self.company)

        self.provider = FiscalProvider.objects.create(name="Mock", provider_type="mock")
        TenantFiscalConfig.all_objects.create(
            company=self.company,
            provider=self.provider,
            environment=TenantFiscalConfig.Environment.SANDBOX,
            active=True,
            auto_issue=True,
        )

    def tearDown(self):
        reset_current_company(self._tenant_token)
        _reset_public_schema()

    def test_process_job_issues_document_and_succeeds(self):
        doc = FiscalDocument.all_objects.create(
            company=self.company,
            invoice_id=555,
            amount=Decimal("0.00"),
            status=FiscalDocument.Status.DRAFT,
        )

        job = enqueue_fiscal_job(doc.id, actor=self.actor, request=None)
        self.assertEqual(job.status, FiscalJob.Status.QUEUED)

        processed = process_fiscal_job(job.id, actor=self.actor, request=None)
        self.assertEqual(processed.status, FiscalJob.Status.SUCCEEDED)

        doc.refresh_from_db()
        self.assertEqual(doc.status, FiscalDocument.Status.AUTHORIZED)
        self.assertTrue(doc.provider_document_id)
        self.assertTrue(doc.xml_content)
        self.assertEqual(doc.amount, Decimal("555.00"))

    def test_process_job_marks_failed_when_provider_not_supported(self):
        unsupported = FiscalProvider.objects.create(name="VendorX", provider_type="vendorx")
        TenantFiscalConfig.all_objects.filter(company=self.company, active=True).update(active=False)
        TenantFiscalConfig.all_objects.create(
            company=self.company,
            provider=unsupported,
            environment=TenantFiscalConfig.Environment.PRODUCTION,
            active=True,
            auto_issue=False,
        )

        doc = FiscalDocument.all_objects.create(
            company=self.company,
            invoice_id=777,
            amount=Decimal("0.00"),
            status=FiscalDocument.Status.DRAFT,
        )
        job = enqueue_fiscal_job(doc.id, actor=self.actor, request=None)

        processed = process_fiscal_job(job.id, actor=self.actor, request=None)
        self.assertEqual(processed.status, FiscalJob.Status.FAILED)
        self.assertEqual(processed.attempts, 1)
        self.assertTrue(processed.last_error)
        self.assertIsNotNone(processed.next_retry_at)

        # Retry schedule: first retry is ~1 minute.
        delta_seconds = (processed.next_retry_at - processed.updated_at).total_seconds()
        self.assertGreaterEqual(delta_seconds, 55)
        self.assertLessEqual(delta_seconds, 90)

    def test_process_job_marks_rejected_when_adapter_raises_rejection(self):
        class RejectingAdapter(FiscalAdapterBase):
            def issue_invoice(self, data):
                raise FiscalAdapterFiscalRejectionError("Rejeitado: CFOP invalido", code="CFOP_INVALID")

            def cancel_invoice(self, document_id):
                raise NotImplementedError

            def check_status(self, document_id):
                raise NotImplementedError

        from unittest.mock import patch

        doc = FiscalDocument.all_objects.create(
            company=self.company,
            invoice_id=888,
            amount=Decimal("0.00"),
            status=FiscalDocument.Status.DRAFT,
        )
        job = enqueue_fiscal_job(doc.id, actor=self.actor, request=None)

        with patch("finance.fiscal.services.get_fiscal_adapter", return_value=RejectingAdapter()):
            processed = process_fiscal_job(job.id, actor=self.actor, request=None)

        self.assertEqual(processed.status, FiscalJob.Status.SUCCEEDED)
        self.assertIsNone(processed.next_retry_at)
        self.assertTrue(processed.last_error)

        doc.refresh_from_db()
        self.assertEqual(doc.status, FiscalDocument.Status.REJECTED)

    def test_process_job_marks_failed_when_adapter_times_out(self):
        class TimeoutAdapter(FiscalAdapterBase):
            def issue_invoice(self, data):
                raise FiscalAdapterTimeoutError("timeout")

            def cancel_invoice(self, document_id):
                raise NotImplementedError

            def check_status(self, document_id):
                raise NotImplementedError

        from unittest.mock import patch

        doc = FiscalDocument.all_objects.create(
            company=self.company,
            invoice_id=889,
            amount=Decimal("0.00"),
            status=FiscalDocument.Status.DRAFT,
        )
        job = enqueue_fiscal_job(doc.id, actor=self.actor, request=None)

        with patch("finance.fiscal.services.get_fiscal_adapter", return_value=TimeoutAdapter()):
            processed = process_fiscal_job(job.id, actor=self.actor, request=None)

        self.assertEqual(processed.status, FiscalJob.Status.FAILED)
        self.assertIsNotNone(processed.next_retry_at)
