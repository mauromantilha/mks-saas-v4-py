from django.contrib.auth import get_user_model
from django.test import TestCase

from control_plane.models import TenantContract, TenantProvisioning
from customers.models import Company


class ControlPlaneTenantTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.platform_admin = User.objects.create_user(
            username="platform-admin",
            password="strong-pass-123",
            email="platform-admin@test.com",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            username="regular-user",
            password="strong-pass-456",
            email="regular-user@test.com",
        )

        self.company = Company.objects.create(
            name="Acme Base",
            tenant_code="acme-base",
            subdomain="acme-base",
            is_active=True,
        )
        self.contract = TenantContract.objects.create(
            company=self.company,
            plan=TenantContract.PLAN_PRO,
            status=TenantContract.STATUS_ACTIVE,
            seats=20,
            monthly_fee=499,
        )
        self.provisioning = TenantProvisioning.objects.create(
            company=self.company,
            status=TenantProvisioning.STATUS_READY,
            database_alias="acme-base",
            database_name="crm_acme_base",
            database_host="127.0.0.1",
            database_port=5432,
            database_user="acme_base_user",
        )

    def test_control_plane_requires_authentication(self):
        response = self.client.get("/platform/api/tenants/")
        self.assertIn(response.status_code, (401, 403))

    def test_control_plane_requires_platform_admin(self):
        self.client.force_login(self.regular_user)
        response = self.client.get("/platform/api/tenants/")
        self.assertEqual(response.status_code, 403)

    def test_platform_admin_can_list_tenants(self):
        self.client.force_login(self.platform_admin)
        response = self.client.get("/platform/api/tenants/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["tenant_code"], "acme-base")
        self.assertEqual(payload[0]["contract"]["plan"], TenantContract.PLAN_PRO)
        self.assertEqual(
            payload[0]["provisioning"]["status"],
            TenantProvisioning.STATUS_READY,
        )

    def test_platform_admin_can_create_tenant(self):
        self.client.force_login(self.platform_admin)
        response = self.client.post(
            "/platform/api/tenants/",
            data={
                "name": "Beta Corp",
                "tenant_code": "beta-corp",
                "subdomain": "beta",
                "is_active": True,
                "contract": {
                    "plan": TenantContract.PLAN_ENTERPRISE,
                    "status": TenantContract.STATUS_ACTIVE,
                    "seats": 50,
                    "monthly_fee": "1299.90",
                },
                "provisioning": {
                    "database_alias": "beta-corp",
                    "database_name": "crm_beta_corp",
                    "database_user": "beta_user",
                },
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["tenant_code"], "beta-corp")
        self.assertEqual(payload["contract"]["plan"], TenantContract.PLAN_ENTERPRISE)
        self.assertEqual(
            payload["provisioning"]["isolation_model"],
            TenantProvisioning.ISOLATION_DATABASE_PER_TENANT,
        )
        self.assertTrue(
            TenantProvisioning.objects.filter(
                company__tenant_code="beta-corp",
                database_name="crm_beta_corp",
            ).exists()
        )

    def test_platform_admin_can_patch_tenant_contract_and_provisioning(self):
        self.client.force_login(self.platform_admin)
        response = self.client.patch(
            f"/platform/api/tenants/{self.company.id}/",
            data={
                "name": "Acme Updated",
                "contract": {
                    "status": TenantContract.STATUS_SUSPENDED,
                    "seats": 10,
                },
                "provisioning": {
                    "status": TenantProvisioning.STATUS_FAILED,
                    "last_error": "Cloud SQL quota exceeded",
                },
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["name"], "Acme Updated")
        self.assertEqual(payload["contract"]["status"], TenantContract.STATUS_SUSPENDED)
        self.assertEqual(payload["contract"]["seats"], 10)
        self.assertEqual(payload["provisioning"]["status"], TenantProvisioning.STATUS_FAILED)
        self.assertEqual(payload["provisioning"]["last_error"], "Cloud SQL quota exceeded")

    def test_platform_admin_can_update_provisioning_status(self):
        self.provisioning.status = TenantProvisioning.STATUS_PROVISIONING
        self.provisioning.provisioned_at = None
        self.provisioning.save(update_fields=["status", "provisioned_at", "updated_at"])

        self.client.force_login(self.platform_admin)
        response = self.client.post(
            f"/platform/api/tenants/{self.company.id}/provision/",
            data={
                "status": TenantProvisioning.STATUS_READY,
                "portal_url": "https://acme.crm.example.com",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["provisioning"]["status"], TenantProvisioning.STATUS_READY)
        self.assertEqual(payload["provisioning"]["portal_url"], "https://acme.crm.example.com")
        self.assertIsNotNone(payload["provisioning"]["provisioned_at"])
