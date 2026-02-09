from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from customers.models import Company, CompanyMembership
from finance.fiscal.adapters.mock import MockFiscalAdapter
from finance.fiscal.crypto import decrypt_token
from finance.fiscal.models import FiscalCustomerSnapshot, FiscalDocument, FiscalJob, TenantFiscalConfig


@override_settings(
    ALLOWED_HOSTS=["testserver", ".example.com"],
    FISCAL_INVOICE_RESOLVER="finance.fiscal.tests.resolvers.mock_invoice_resolver",
)
class FiscalTenantIsolationAPITests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.company_a = Company.objects.create(
            name="Empresa A",
            tenant_code="acme",
            subdomain="acme",
        )
        self.company_b = Company.objects.create(
            name="Empresa B",
            tenant_code="beta",
            subdomain="beta",
        )

        self.owner_a = User.objects.create_user(
            username="owner-a",
            email="owner-a@acme.com",
            password="pass-a",
        )
        self.manager_a = User.objects.create_user(
            username="manager-a",
            email="manager-a@acme.com",
            password="pass-mgr",
        )
        self.member_a = User.objects.create_user(
            username="member-a",
            email="member-a@acme.com",
            password="pass-member",
        )
        self.owner_b = User.objects.create_user(
            username="owner-b",
            email="owner-b@beta.com",
            password="pass-b",
        )

        CompanyMembership.objects.create(
            company=self.company_a, user=self.owner_a, role=CompanyMembership.ROLE_OWNER
        )
        CompanyMembership.objects.create(
            company=self.company_a,
            user=self.manager_a,
            role=CompanyMembership.ROLE_MANAGER,
        )
        CompanyMembership.objects.create(
            company=self.company_a,
            user=self.member_a,
            role=CompanyMembership.ROLE_MEMBER,
        )
        CompanyMembership.objects.create(
            company=self.company_b, user=self.owner_b, role=CompanyMembership.ROLE_OWNER
        )

        adapter = MockFiscalAdapter()
        issued_a = adapter.issue_invoice(
            {
                "invoice_id": 10,
                "amount": "100.00",
                "issue_date": "2026-02-09",
                "customer": {
                    "name": "Cliente A",
                    "cpf_cnpj": "123.456.789-09",
                    "address": "Rua A, 100",
                },
            }
        )
        issued_b = adapter.issue_invoice(
            {
                "invoice_id": 20,
                "amount": "200.00",
                "issue_date": "2026-02-09",
                "customer": {
                    "name": "Cliente B",
                    "cpf_cnpj": "12.345.678/0001-90",
                    "address": "Rua B, 200",
                },
            }
        )

        self.doc_a = FiscalDocument.all_objects.create(
            company=self.company_a,
            invoice_id=10,
            provider_document_id=issued_a["document_id"],
            number=issued_a["number"],
            series=issued_a["series"],
            issue_date="2026-02-09",
            amount=Decimal("100.00"),
            status="AUTHORIZED",
            xml_content=issued_a["xml_content"],
        )
        FiscalCustomerSnapshot.all_objects.create(
            fiscal_document=self.doc_a,
            name="Cliente A",
            cpf_cnpj="123.456.789-09",
            address="Rua A, 100",
        )

        self.doc_b = FiscalDocument.all_objects.create(
            company=self.company_b,
            invoice_id=20,
            provider_document_id=issued_b["document_id"],
            number=issued_b["number"],
            series=issued_b["series"],
            issue_date="2026-02-09",
            amount=Decimal("200.00"),
            status="AUTHORIZED",
            xml_content=issued_b["xml_content"],
        )
        FiscalCustomerSnapshot.all_objects.create(
            fiscal_document=self.doc_b,
            name="Cliente B",
            cpf_cnpj="12.345.678/0001-90",
            address="Rua B, 200",
        )

    def test_list_isolated_by_tenant_header(self):
        self.client.force_login(self.owner_a)
        response = self.client.get("/api/finance/fiscal/", HTTP_X_TENANT_ID="acme")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], self.doc_a.id)

    def test_user_from_other_tenant_is_denied(self):
        self.client.force_login(self.owner_b)
        response = self.client.get("/api/finance/fiscal/", HTTP_X_TENANT_ID="acme")
        self.assertEqual(response.status_code, 403)

    def test_config_owner_only_and_encrypts_token(self):
        self.client.force_login(self.member_a)
        denied = self.client.post(
            "/api/finance/fiscal/config/",
            data={
                "provider": "mock",
                "token": "plain-token",
                "environment": "SANDBOX",
                "auto_issue": True,
            },
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.owner_a)
        ok = self.client.post(
            "/api/finance/fiscal/config/",
            data={
                "provider": "mock",
                "token": "plain-token",
                "environment": "SANDBOX",
                "auto_issue": True,
            },
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(ok.status_code, 201)
        self.assertNotIn("token", ok.json())
        self.assertTrue(ok.json()["auto_issue"])

        cfg = TenantFiscalConfig.all_objects.get(company=self.company_a, active=True)
        self.assertNotEqual(cfg.api_token, "plain-token")
        self.assertEqual(decrypt_token(cfg.api_token), "plain-token")

    def test_config_single_active(self):
        self.client.force_login(self.owner_a)
        self.client.post(
            "/api/finance/fiscal/config/",
            data={"provider": "mock", "token": "t1", "environment": "SANDBOX", "auto_issue": True},
            HTTP_X_TENANT_ID="acme",
        )
        self.client.post(
            "/api/finance/fiscal/config/",
            data={"provider": "dummy", "token": "t2", "environment": "PRODUCTION", "auto_issue": False},
            HTTP_X_TENANT_ID="acme",
        )

        active = TenantFiscalConfig.all_objects.filter(company=self.company_a, active=True)
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first().provider.provider_type, "dummy")

    def test_issue_nf_mock_and_cancel(self):
        # Owner configures provider, manager issues.
        self.client.force_login(self.owner_a)
        self.client.post(
            "/api/finance/fiscal/config/",
            data={"provider": "mock", "token": "t1", "environment": "SANDBOX", "auto_issue": True},
            HTTP_X_TENANT_ID="acme",
        )

        self.client.force_login(self.manager_a)
        issue = self.client.post(
            "/api/finance/fiscal/issue/",
            data={"invoice_id": 123},
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(issue.status_code, 201)
        payload = issue.json()
        self.assertEqual(payload["invoice_id"], 123)
        self.assertEqual(payload["status"], "AUTHORIZED")
        self.assertTrue(payload["provider_document_id"].startswith("mock:"))
        self.assertTrue(payload["has_xml"])
        self.assertEqual(payload["customer_snapshot"]["cpf_cnpj"], "123.456.789-09")

        doc_id = payload["id"]

        # Cancel as manager (POST permission).
        cancel_1 = self.client.post(
            f"/api/finance/fiscal/{doc_id}/cancel/",
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(cancel_1.status_code, 200)
        self.assertEqual(cancel_1.json()["status"], "CANCELLED")

        cancel_2 = self.client.post(
            f"/api/finance/fiscal/{doc_id}/cancel/",
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(cancel_2.status_code, 409)

    def test_member_cannot_issue(self):
        self.client.force_login(self.member_a)
        response = self.client.post(
            "/api/finance/fiscal/issue/",
            data={"invoice_id": 123},
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(response.status_code, 403)

    def test_issue_is_denied_for_user_from_other_tenant(self):
        self.client.force_login(self.owner_b)
        response = self.client.post(
            "/api/finance/fiscal/issue/",
            data={"invoice_id": 123},
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(response.status_code, 403)

    def test_provider_switch_allows_new_issues(self):
        self.client.force_login(self.owner_a)
        self.client.post(
            "/api/finance/fiscal/config/",
            data={"provider": "mock", "token": "t1", "environment": "SANDBOX", "auto_issue": True},
            HTTP_X_TENANT_ID="acme",
        )

        self.client.force_login(self.manager_a)
        issue_1 = self.client.post(
            "/api/finance/fiscal/issue/",
            data={"invoice_id": 101},
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(issue_1.status_code, 201)

        self.client.force_login(self.owner_a)
        self.client.post(
            "/api/finance/fiscal/config/",
            data={"provider": "dummy", "token": "t2", "environment": "PRODUCTION", "auto_issue": False},
            HTTP_X_TENANT_ID="acme",
        )
        active = TenantFiscalConfig.all_objects.get(company=self.company_a, active=True)
        self.assertEqual(active.provider.provider_type, "dummy")

        self.client.force_login(self.manager_a)
        issue_2 = self.client.post(
            "/api/finance/fiscal/issue/",
            data={"invoice_id": 102},
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(issue_2.status_code, 201)

    def test_cancel_endpoint_and_prevent_double_cancel(self):
        self.client.force_login(self.owner_a)
        self.client.post(
            "/api/finance/fiscal/config/",
            data={"provider": "mock", "token": "t1", "environment": "SANDBOX", "auto_issue": True},
            HTTP_X_TENANT_ID="acme",
        )

        cancel_1 = self.client.post(
            f"/api/finance/fiscal/{self.doc_a.id}/cancel/",
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(cancel_1.status_code, 200)
        self.assertEqual(cancel_1.json()["status"], "CANCELLED")

        cancel_2 = self.client.post(
            f"/api/finance/fiscal/{self.doc_a.id}/cancel/",
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(cancel_2.status_code, 409)

    def test_member_cannot_cancel(self):
        self.client.force_login(self.member_a)
        response = self.client.post(
            f"/api/finance/fiscal/{self.doc_a.id}/cancel/",
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(response.status_code, 403)

    def test_retry_only_allowed_for_failed_jobs(self):
        failed_doc = FiscalDocument.all_objects.create(
            company=self.company_a,
            invoice_id=999,
            amount=Decimal("10.00"),
            status=FiscalDocument.Status.EMITTING,
        )
        job = FiscalJob.all_objects.create(
            fiscal_document=failed_doc,
            status=FiscalJob.Status.FAILED,
            attempts=1,
            last_error="timeout",
        )

        self.client.force_login(self.manager_a)
        ok = self.client.post(
            f"/api/finance/fiscal/{failed_doc.id}/retry/",
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(ok.status_code, 202)
        payload = ok.json()
        self.assertEqual(payload["document_id"], failed_doc.id)
        self.assertEqual(payload["job_id"], job.id)
        self.assertEqual(payload["job_status"], FiscalJob.Status.QUEUED)
        self.assertIsNotNone(payload["next_retry_at"])

        job.refresh_from_db()
        self.assertEqual(job.status, FiscalJob.Status.QUEUED)
        self.assertEqual(job.last_error, "")
        self.assertIsNotNone(job.next_retry_at)

        # Not failed anymore => cannot retry.
        deny = self.client.post(
            f"/api/finance/fiscal/{failed_doc.id}/retry/",
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(deny.status_code, 409)

    def test_retry_requires_existing_job(self):
        doc = FiscalDocument.all_objects.create(
            company=self.company_a,
            invoice_id=1001,
            amount=Decimal("10.00"),
            status=FiscalDocument.Status.EMITTING,
        )

        self.client.force_login(self.manager_a)
        resp = self.client.post(
            f"/api/finance/fiscal/{doc.id}/retry/",
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(resp.status_code, 409)

    def test_retry_isolated_by_tenant(self):
        failed_doc = FiscalDocument.all_objects.create(
            company=self.company_a,
            invoice_id=1002,
            amount=Decimal("10.00"),
            status=FiscalDocument.Status.EMITTING,
        )
        FiscalJob.all_objects.create(
            fiscal_document=failed_doc,
            status=FiscalJob.Status.FAILED,
            attempts=1,
            last_error="timeout",
        )

        self.client.force_login(self.owner_b)
        resp = self.client.post(
            f"/api/finance/fiscal/{failed_doc.id}/retry/",
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(resp.status_code, 403)
