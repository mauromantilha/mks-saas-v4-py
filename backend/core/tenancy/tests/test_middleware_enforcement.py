from django.test import TestCase

from control_plane.models import Tenant
from customers.models import Company


class TenantSuspensionMiddlewareTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Tenant Suspenso",
            tenant_code="tenant-suspenso",
            subdomain="tenant-suspenso",
            is_active=True,
        )
        self.control_tenant = Tenant.objects.create(
            company=self.company,
            legal_name="Tenant Suspenso Ltda",
            slug="tenant-suspenso",
            subdomain="tenant-suspenso",
            status=Tenant.STATUS_SUSPENDED,
        )

    def test_blocks_tenant_api_when_tenant_not_active(self):
        response = self.client.get(
            "/api/customers/",
            HTTP_X_TENANT_ID="tenant-suspenso",
            HTTP_X_CORRELATION_ID="corr-test-001",
        )
        self.assertEqual(response.status_code, 423)
        payload = response.json()
        self.assertEqual(payload["reason"], "SUSPENDED")
        self.assertEqual(payload["correlation_id"], "corr-test-001")
        self.assertEqual(response["X-Correlation-ID"], "corr-test-001")

    def test_allows_public_exempt_endpoint_when_tenant_suspended(self):
        response = self.client.post(
            "/api/auth/token/",
            data={"username": "x", "password": "y"},
            content_type="application/json",
            HTTP_X_TENANT_ID="tenant-suspenso",
        )
        # Endpoint can still reject credentials, but must not be blocked by suspension middleware.
        self.assertNotEqual(response.status_code, 423)
