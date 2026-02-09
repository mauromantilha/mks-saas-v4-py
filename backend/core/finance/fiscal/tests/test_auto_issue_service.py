from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings

from customers.models import Company
from finance.fiscal.models import FiscalProvider, FiscalDocument, TenantFiscalConfig
from finance.fiscal.services import auto_issue_nf_from_invoice
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
class FiscalAutoIssueServiceTests(TestCase):
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
        self.config = TenantFiscalConfig.all_objects.create(
            company=self.company,
            provider=self.provider,
            environment=TenantFiscalConfig.Environment.SANDBOX,
            active=True,
            auto_issue=True,
        )

    def tearDown(self):
        reset_current_company(self._tenant_token)
        _reset_public_schema()

    def test_auto_issue_creates_document_when_paid(self):
        doc = auto_issue_nf_from_invoice(999, actor=self.actor, request=None)
        self.assertIsNotNone(doc)
        self.assertEqual(doc.invoice_id, 999)
        self.assertEqual(doc.company_id, self.company.id)
        self.assertEqual(doc.status, "AUTHORIZED")
        self.assertTrue(doc.provider_document_id)

        # Idempotent: same invoice does not create another doc.
        again = auto_issue_nf_from_invoice(999, actor=self.actor, request=None)
        self.assertEqual(again.id, doc.id)
        self.assertEqual(
            FiscalDocument.all_objects.filter(company=self.company, invoice_id=999).count(),
            1,
        )

    def test_auto_issue_skips_when_disabled(self):
        self.config.auto_issue = False
        self.config.save(update_fields=["auto_issue", "updated_at"])

        before = FiscalDocument.all_objects.filter(company=self.company).count()
        result = auto_issue_nf_from_invoice(1000, actor=self.actor, request=None)
        after = FiscalDocument.all_objects.filter(company=self.company).count()
        self.assertIsNone(result)
        self.assertEqual(after, before)


@override_settings(
    ALLOWED_HOSTS=["testserver", ".example.com"],
    FISCAL_INVOICE_RESOLVER="finance.fiscal.tests.resolvers.mock_invoice_resolver_unpaid",
)
class FiscalAutoIssueUnpaidTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Empresa A",
            tenant_code="acme",
            subdomain="acme",
        )
        _set_tenant_schema(self.company)
        self._tenant_token = set_current_company(self.company)
        self.provider = FiscalProvider.objects.create(name="Mock", provider_type="mock")
        self.config = TenantFiscalConfig.all_objects.create(
            company=self.company,
            provider=self.provider,
            environment=TenantFiscalConfig.Environment.SANDBOX,
            active=True,
            auto_issue=True,
        )

    def tearDown(self):
        reset_current_company(self._tenant_token)
        _reset_public_schema()

    def test_auto_issue_skips_when_invoice_not_paid(self):
        result = auto_issue_nf_from_invoice(123, actor=None, request=None)
        self.assertIsNone(result)
        self.assertEqual(
            FiscalDocument.all_objects.filter(company=self.company, invoice_id=123).count(),
            0,
        )

