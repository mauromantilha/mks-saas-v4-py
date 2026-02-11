from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone

from control_plane.models import (
    AdminAuditEvent,
    FeatureFlag,
    ContractEmailLog,
    Plan,
    PlanPrice,
    SystemHealthSnapshot,
    Tenant,
    TenantContractDocument,
    TenantHealthSnapshot,
    TenantFeatureFlag,
    TenantInternalNote,
    TenantImpersonationSession,
    TenantIntegrationSecretRef,
    TenantContract,
    TenantOperationalSettings,
    TenantPlanSubscription,
    TenantProvisioning,
    TenantReleaseRecord,
    TenantStatusHistory,
    TenantAlertEvent,
)
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
        execute_response = self.client.post(
            f"/platform/api/tenants/{self.company.id}/provision/execute/",
            data={},
            content_type="application/json",
        )
        self.assertEqual(execute_response.status_code, 403)

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
            TenantProvisioning.ISOLATION_SCHEMA_PER_TENANT,
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

    def test_platform_admin_can_execute_provisioning_with_noop_provider(self):
        self.provisioning.status = TenantProvisioning.STATUS_PENDING
        self.provisioning.provisioned_at = None
        self.provisioning.portal_url = ""
        self.provisioning.save(
            update_fields=["status", "provisioned_at", "portal_url", "updated_at"]
        )

        self.client.force_login(self.platform_admin)
        response = self.client.post(
            f"/platform/api/tenants/{self.company.id}/provision/execute/",
            data={},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["provisioning"]["status"], TenantProvisioning.STATUS_READY)
        self.assertIsNotNone(payload["provisioning"]["provisioned_at"])

    @override_settings(CONTROL_PLANE_PROVISIONER="unknown-provider")
    def test_execute_provisioning_with_unknown_provider_marks_failed(self):
        self.provisioning.status = TenantProvisioning.STATUS_PENDING
        self.provisioning.provisioned_at = None
        self.provisioning.last_error = ""
        self.provisioning.save(
            update_fields=["status", "provisioned_at", "last_error", "updated_at"]
        )

        self.client.force_login(self.platform_admin)
        response = self.client.post(
            f"/platform/api/tenants/{self.company.id}/provision/execute/",
            data={},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("Unknown control-plane provisioner", payload["detail"])
        self.company.refresh_from_db()
        self.assertEqual(
            self.company.provisioning.status,
            TenantProvisioning.STATUS_FAILED,
        )

    @override_settings(
        CONTROL_PLANE_PROVISIONER="cloudsql_postgres",
        CONTROL_PLANE_CLOUDSQL_ADMIN_USER="",
        CONTROL_PLANE_CLOUDSQL_ADMIN_PASSWORD="",
        CONTROL_PLANE_CLOUDSQL_ADMIN_HOST="127.0.0.1",
    )
    def test_execute_provisioning_cloudsql_without_admin_credentials_marks_failed(self):
        self.provisioning.status = TenantProvisioning.STATUS_PENDING
        self.provisioning.last_error = ""
        self.provisioning.save(update_fields=["status", "last_error", "updated_at"])

        self.client.force_login(self.platform_admin)
        response = self.client.post(
            f"/platform/api/tenants/{self.company.id}/provision/execute/",
            data={},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("CONTROL_PLANE_CLOUDSQL_ADMIN_USER", payload["detail"])
        self.company.refresh_from_db()
        self.assertEqual(self.company.provisioning.status, TenantProvisioning.STATUS_FAILED)

    @override_settings(
        CONTROL_PLANE_PROVISIONER="cloudsql_postgres",
        CONTROL_PLANE_CLOUDSQL_ADMIN_USER="admin",
        CONTROL_PLANE_CLOUDSQL_ADMIN_PASSWORD="admin-password",
        CONTROL_PLANE_CLOUDSQL_ADMIN_HOST="",
    )
    def test_execute_provisioning_cloudsql_without_host_marks_failed(self):
        self.provisioning.status = TenantProvisioning.STATUS_PENDING
        self.provisioning.last_error = ""
        self.provisioning.save(update_fields=["status", "last_error", "updated_at"])

        self.client.force_login(self.platform_admin)
        response = self.client.post(
            f"/platform/api/tenants/{self.company.id}/provision/execute/",
            data={},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("CONTROL_PLANE_CLOUDSQL_ADMIN_HOST", payload["detail"])
        self.company.refresh_from_db()
        self.assertEqual(self.company.provisioning.status, TenantProvisioning.STATUS_FAILED)

    @override_settings(TENANT_RESERVED_SUBDOMAINS=["sistema", "api"])
    def test_platform_admin_cannot_create_tenant_with_reserved_subdomain(self):
        self.client.force_login(self.platform_admin)
        response = self.client.post(
            "/platform/api/tenants/",
            data={
                "name": "Reserved Subdomain Inc",
                "tenant_code": "reserved-subdomain-inc",
                "subdomain": "sistema",
                "is_active": True,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("subdomain", payload)

    @override_settings(TENANT_RESERVED_SUBDOMAINS=["sistema", "api"])
    def test_platform_admin_cannot_patch_tenant_to_reserved_subdomain(self):
        self.client.force_login(self.platform_admin)
        response = self.client.patch(
            f"/platform/api/tenants/{self.company.id}/",
            data={"subdomain": "api"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("subdomain", payload)

    @override_settings(
        ALLOWED_HOSTS=["testserver", "sistema.mksbrasil.com", "acme-base.mksbrasil.com"],
        CONTROL_PLANE_ALLOWED_HOSTS=["sistema.mksbrasil.com"],
    )
    def test_control_plane_host_restriction_blocks_tenant_host(self):
        self.client.force_login(self.platform_admin)

        blocked_response = self.client.get(
            "/platform/api/tenants/",
            HTTP_HOST="acme-base.mksbrasil.com",
        )
        self.assertEqual(blocked_response.status_code, 403)

        allowed_response = self.client.get(
            "/platform/api/tenants/",
            HTTP_HOST="sistema.mksbrasil.com",
        )
        self.assertEqual(allowed_response.status_code, 200)

    @override_settings(
        CONTROL_PLANE_PROVISIONER="noop",
        CONTROL_PLANE_PORTAL_URL_TEMPLATE="",
        TENANT_BASE_DOMAIN="mksbrasil.com",
    )
    def test_execute_provisioning_generates_portal_url_from_tenant_base_domain(self):
        self.provisioning.status = TenantProvisioning.STATUS_PENDING
        self.provisioning.provisioned_at = None
        self.provisioning.portal_url = ""
        self.provisioning.save(
            update_fields=["status", "provisioned_at", "portal_url", "updated_at"]
        )

        self.client.force_login(self.platform_admin)
        response = self.client.post(
            f"/platform/api/tenants/{self.company.id}/provision/execute/",
            data={},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["provisioning"]["portal_url"],
            "https://acme-base.mksbrasil.com",
        )


class ControlPlaneModelConstraintsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Constraint Co",
            tenant_code="constraint-co",
            subdomain="constraint-co",
            is_active=True,
        )
        self.tenant = Tenant.objects.create(
            company=self.company,
            legal_name="Constraint Co Ltda",
            cnpj="12.345.678/0001-90",
            slug="constraint-co",
            subdomain="constraint-co",
            status=Tenant.STATUS_ACTIVE,
        )
        self.plan = Plan.objects.create(name="Pro", tier=Plan.TIER_GROWTH, is_active=True)

    def test_tenant_slug_must_be_unique(self):
        another_company = Company.objects.create(
            name="Another Co",
            tenant_code="another-co",
            subdomain="another-co",
            is_active=True,
        )
        with self.assertRaises(IntegrityError):
            Tenant.objects.create(
                company=another_company,
                legal_name="Another Co Ltda",
                slug="constraint-co",
                subdomain="another-co",
                status=Tenant.STATUS_ACTIVE,
            )

    def test_plan_price_rejects_values_outside_fixed_catalog(self):
        price = PlanPrice(plan=self.plan, monthly_price="199.00", setup_fee="25.00")
        with self.assertRaises(ValidationError):
            price.full_clean()

    def test_subscription_trial_date_must_be_coherent(self):
        subscription = TenantPlanSubscription(
            tenant=self.tenant,
            plan=self.plan,
            is_trial=True,
            start_date=timezone.localdate(),
            trial_ends_at=timezone.localdate() - timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            subscription.full_clean()

    def test_status_history_requires_distinct_statuses(self):
        user = get_user_model().objects.create_user(
            username="history-user",
            password="secure-pass-123",
        )
        with self.assertRaises(IntegrityError):
            TenantStatusHistory.objects.create(
                tenant=self.tenant,
                from_status=Tenant.STATUS_ACTIVE,
                to_status=Tenant.STATUS_ACTIVE,
                reason="noop",
                actor=user,
            )


class ControlPanelTenantManagementApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(
            username="cp-superadmin",
            password="strong-pass-123",
            is_staff=True,
            is_superuser=True,
        )
        self.saas_admin = User.objects.create_user(
            username="cp-saas-admin",
            password="strong-pass-234",
            is_staff=True,
        )
        saas_group, _ = Group.objects.get_or_create(name="SAAS_ADMIN")
        self.saas_admin.groups.add(saas_group)

        self.regular_user = User.objects.create_user(
            username="cp-regular",
            password="strong-pass-345",
        )

        self.plan = Plan.objects.create(name="Starter", tier=Plan.TIER_STARTER, is_active=True)
        PlanPrice.objects.create(plan=self.plan, monthly_price="150.00", setup_fee="0.00")

    def test_superadmin_can_crud_and_status_actions(self):
        self.client.force_login(self.superadmin)
        create_response = self.client.post(
            "/control-panel/tenants/",
            data={
                "legal_name": "Tenant API Test",
                "cnpj": "12.345.678/0001-99",
                "slug": "tenant-api-test",
                "subdomain": "tenant-api-test",
                "status": Tenant.STATUS_ACTIVE,
                "subscription": {
                    "plan_id": self.plan.id,
                    "is_trial": True,
                    "trial_ends_at": str(timezone.localdate() + timedelta(days=7)),
                    "is_courtesy": False,
                    "status": TenantPlanSubscription.STATUS_ACTIVE,
                },
            },
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        tenant_id = create_response.json()["id"]

        list_response = self.client.get("/control-panel/tenants/?status=ACTIVE&search=12.345")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)

        detail_response = self.client.get(f"/control-panel/tenants/{tenant_id}/")
        self.assertEqual(detail_response.status_code, 200)

        patch_response = self.client.patch(
            f"/control-panel/tenants/{tenant_id}/",
            data={"city": "Sao Paulo", "state": "SP"},
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()["city"], "Sao Paulo")

        suspend_response = self.client.post(
            f"/control-panel/tenants/{tenant_id}/suspend/",
            data={"reason": "payment overdue"},
            content_type="application/json",
        )
        self.assertEqual(suspend_response.status_code, 200)
        self.assertEqual(suspend_response.json()["status"], Tenant.STATUS_SUSPENDED)

        unsuspend_response = self.client.post(
            f"/control-panel/tenants/{tenant_id}/unsuspend/",
            data={"reason": "payment settled"},
            content_type="application/json",
        )
        self.assertEqual(unsuspend_response.status_code, 200)
        self.assertEqual(unsuspend_response.json()["status"], Tenant.STATUS_ACTIVE)

        delete_response = self.client.post(
            f"/control-panel/tenants/{tenant_id}/delete/",
            data={"reason": "requested by legal", "confirm_text": "DELETE"},
            content_type="application/json",
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["status"], Tenant.STATUS_DELETED)
        self.assertTrue(
            TenantStatusHistory.objects.filter(
                tenant_id=tenant_id,
                to_status=Tenant.STATUS_DELETED,
            ).exists()
        )

    def test_saas_admin_cannot_reactivate(self):
        self.client.force_login(self.superadmin)
        create_response = self.client.post(
            "/control-panel/tenants/",
            data={
                "legal_name": "Tenant Suspended",
                "slug": "tenant-suspended",
                "subdomain": "tenant-suspended",
                "status": Tenant.STATUS_ACTIVE,
            },
            content_type="application/json",
        )
        tenant_id = create_response.json()["id"]
        self.client.post(
            f"/control-panel/tenants/{tenant_id}/suspend/",
            data={"reason": "overdue"},
            content_type="application/json",
        )

        self.client.force_login(self.saas_admin)
        unsuspend_response = self.client.post(
            f"/control-panel/tenants/{tenant_id}/unsuspend/",
            data={"reason": "manual try"},
            content_type="application/json",
        )
        self.assertEqual(unsuspend_response.status_code, 403)

        patch_response = self.client.patch(
            f"/control-panel/tenants/{tenant_id}/",
            data={"status": Tenant.STATUS_ACTIVE},
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 403)

    def test_regular_user_forbidden(self):
        self.client.force_login(self.regular_user)
        response = self.client.get("/control-panel/tenants/")
        self.assertEqual(response.status_code, 403)

    def test_saas_admin_group_allowed(self):
        self.client.force_login(self.saas_admin)
        response = self.client.get("/control-panel/tenants/")
        self.assertEqual(response.status_code, 200)

    def test_soft_delete_requires_confirm_text(self):
        self.client.force_login(self.superadmin)
        create_response = self.client.post(
            "/control-panel/tenants/",
            data={
                "legal_name": "Tenant Delete Confirm",
                "slug": "tenant-delete-confirm",
                "subdomain": "tenant-delete-confirm",
                "status": Tenant.STATUS_ACTIVE,
            },
            content_type="application/json",
        )
        tenant_id = create_response.json()["id"]
        response = self.client.post(
            f"/control-panel/tenants/{tenant_id}/delete/",
            data={"reason": "without confirm"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_plans_list_and_create(self):
        self.client.force_login(self.superadmin)

        list_response = self.client.get("/control-panel/plans/")
        self.assertEqual(list_response.status_code, 200)
        self.assertGreaterEqual(len(list_response.json()), 1)

        create_response = self.client.post(
            "/control-panel/plans/",
            data={
                "name": "Enterprise Plus",
                "tier": Plan.TIER_ENTERPRISE,
                "is_active": True,
                "monthly_price": "350.00",
                "setup_fee": "150.00",
            },
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["name"], "Enterprise Plus")

    def test_change_tenant_subscription(self):
        self.client.force_login(self.superadmin)
        create_response = self.client.post(
            "/control-panel/tenants/",
            data={
                "legal_name": "Subscription Tenant",
                "cnpj": "12.345.678/0001-99",
                "slug": "subscription-tenant",
                "subdomain": "subscription-tenant",
                "status": Tenant.STATUS_ACTIVE,
            },
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        tenant_id = create_response.json()["id"]

        change_response = self.client.post(
            f"/control-panel/tenants/{tenant_id}/subscription/",
            data={
                "plan_id": self.plan.id,
                "is_trial": True,
                "trial_days": 7,
                "is_courtesy": False,
                "setup_fee_override": "0.00",
            },
            content_type="application/json",
        )
        self.assertEqual(change_response.status_code, 200)
        subscription = change_response.json()["subscription"]
        self.assertIsNotNone(subscription)
        self.assertTrue(subscription["is_trial"])

    def test_change_tenant_subscription_invalid_trial_payload(self):
        self.client.force_login(self.superadmin)
        create_response = self.client.post(
            "/control-panel/tenants/",
            data={
                "legal_name": "Invalid Trial Tenant",
                "slug": "invalid-trial-tenant",
                "subdomain": "invalid-trial-tenant",
                "status": Tenant.STATUS_ACTIVE,
            },
            content_type="application/json",
        )
        tenant_id = create_response.json()["id"]
        change_response = self.client.post(
            f"/control-panel/tenants/{tenant_id}/subscription/",
            data={
                "plan_id": self.plan.id,
                "is_trial": True,
                "is_courtesy": False,
            },
            content_type="application/json",
        )
        self.assertEqual(change_response.status_code, 400)

    def test_plans_forbidden_for_regular_user(self):
        self.client.force_login(self.regular_user)
        response = self.client.get("/control-panel/plans/")
        self.assertEqual(response.status_code, 403)

    def test_baseline_plan_catalog_is_auto_seeded(self):
        self.client.force_login(self.superadmin)
        response = self.client.get("/control-panel/plans/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        plan_names = {row["name"] for row in payload}
        self.assertTrue({"Básico", "Intermediário", "Premium"}.issubset(plan_names))

        basic = next(row for row in payload if row["name"] == "Básico")
        self.assertEqual(str(basic["price"]["monthly_price"]), "150.00")
        self.assertEqual(str(basic["price"]["setup_fee"]), "150.00")

    def test_companies_without_control_tenant_are_backfilled_in_tenant_list(self):
        Company.objects.create(
            name="Acme Legacy",
            tenant_code="acme",
            subdomain="acme",
            is_active=True,
        )
        self.client.force_login(self.superadmin)
        response = self.client.get("/control-panel/tenants/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(row["slug"] == "acme" for row in payload))
        self.assertTrue(Tenant.objects.filter(slug="acme").exists())


class ControlPanelCepLookupApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            username="cep-admin",
            password="strong-pass-123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.admin)

    @patch("control_plane.services.cep_lookup.urlopen")
    def test_cep_lookup_success(self, mocked_urlopen):
        mocked_response = Mock()
        mocked_response.read.return_value = (
            b'{"cep":"01001-000","logradouro":"Pra\xc3\xa7a da S\xc3\xa9","bairro":"S\xc3\xa9","localidade":"S\xc3\xa3o Paulo","uf":"SP"}'
        )
        mocked_urlopen.return_value.__enter__.return_value = mocked_response

        response = self.client.get("/control-panel/utils/cep/01001-000/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["cep"], "01001000")
        self.assertEqual(payload["cidade"], "São Paulo")
        self.assertEqual(payload["uf"], "SP")

    def test_cep_lookup_invalid_cep_returns_400(self):
        response = self.client.get("/control-panel/utils/cep/123/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())


class ControlPanelContractsApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(
            username="contracts-admin",
            password="strong-pass-123",
            is_staff=True,
            is_superuser=True,
            email="admin@test.com",
        )
        self.client.force_login(self.superadmin)

        self.plan = Plan.objects.create(name="Starter Contract", tier=Plan.TIER_STARTER, is_active=True)
        PlanPrice.objects.create(plan=self.plan, monthly_price="150.00", setup_fee="0.00")
        company = Company.objects.create(
            name="Contract Tenant Co",
            tenant_code="contract-tenant",
            subdomain="contract-tenant",
            is_active=True,
        )
        self.tenant = Tenant.objects.create(
            company=company,
            legal_name="Contract Tenant Co",
            cnpj="12.345.678/0001-99",
            slug="contract-tenant",
            subdomain="contract-tenant",
            status=Tenant.STATUS_ACTIVE,
            cep="01001000",
            street="Praca da Se",
            city="Sao Paulo",
            state="SP",
        )
        TenantPlanSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            is_trial=True,
            trial_ends_at=timezone.localdate() + timedelta(days=7),
            is_courtesy=False,
            status=TenantPlanSubscription.STATUS_ACTIVE,
        )

    def test_create_and_list_contracts(self):
        create_response = self.client.post(
            f"/control-panel/tenants/{self.tenant.id}/contracts/",
            data={},
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        contract_id = create_response.json()["id"]
        self.assertTrue(
            TenantContractDocument.objects.filter(id=contract_id, tenant=self.tenant).exists()
        )

        list_response = self.client.get(f"/control-panel/tenants/{self.tenant.id}/contracts/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)

    @patch("control_plane.services.contracts.send_email", return_value="re_msg_123")
    def test_send_contract_email(self, _mock_send_email):
        contract = TenantContractDocument.objects.create(
            tenant=self.tenant,
            status=TenantContractDocument.STATUS_DRAFT,
            contract_version=1,
            snapshot_json={"tenant_id": self.tenant.id},
        )
        response = self.client.post(
            f"/control-panel/contracts/{contract.id}/send/",
            data={"to_email": "financeiro@test.com", "force_send": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        contract.refresh_from_db()
        self.assertEqual(contract.status, TenantContractDocument.STATUS_SENT)
        self.assertTrue(
            ContractEmailLog.objects.filter(
                contract=contract,
                to_email="financeiro@test.com",
                status=ContractEmailLog.STATUS_SENT,
            ).exists()
        )

    @patch("control_plane.services.contracts.send_email", return_value="re_msg_456")
    def test_send_contract_idempotency_requires_force(self, _mock_send_email):
        contract = TenantContractDocument.objects.create(
            tenant=self.tenant,
            status=TenantContractDocument.STATUS_SENT,
            contract_version=2,
            snapshot_json={"tenant_id": self.tenant.id},
        )
        blocked = self.client.post(
            f"/control-panel/contracts/{contract.id}/send/",
            data={"to_email": "financeiro@test.com"},
            content_type="application/json",
        )
        self.assertEqual(blocked.status_code, 409)

        allowed = self.client.post(
            f"/control-panel/contracts/{contract.id}/send/",
            data={"to_email": "financeiro@test.com", "force_send": True},
            content_type="application/json",
        )
        self.assertEqual(allowed.status_code, 200)


class ControlPanelMonitoringApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(
            username="monitoring-admin",
            password="strong-pass-123",
            is_staff=True,
            is_superuser=True,
        )
        company = Company.objects.create(
            name="Monitoring Tenant Co",
            tenant_code="monitoring-tenant",
            subdomain="monitoring-tenant",
            is_active=True,
        )
        self.tenant = Tenant.objects.create(
            company=company,
            legal_name="Monitoring Tenant Co",
            slug="monitoring-tenant",
            subdomain="monitoring-tenant",
            status=Tenant.STATUS_ACTIVE,
        )

    def test_monitoring_list_returns_summary(self):
        SystemHealthSnapshot.objects.create(
            service_name="backend",
            status="UP",
            latency_ms=120,
            error_rate=0.01,
        )
        TenantHealthSnapshot.objects.create(
            tenant=self.tenant,
            request_rate=12.5,
            error_rate=0,
            p95_latency=230,
            jobs_pending=3,
        )
        self.client.force_login(self.superadmin)
        response = self.client.get("/control-panel/monitoring/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["total_services"], 1)
        self.assertEqual(payload["summary"]["total_tenants"], 1)
        self.assertEqual(len(payload["services"]), 1)
        self.assertEqual(len(payload["tenants"]), 1)

    def test_tenant_monitoring_detail(self):
        TenantHealthSnapshot.objects.create(
            tenant=self.tenant,
            request_rate=4,
            error_rate=0.02,
            p95_latency=500,
            jobs_pending=2,
        )
        self.client.force_login(self.superadmin)
        response = self.client.get(f"/control-panel/tenants/{self.tenant.id}/monitoring/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["tenant"]["id"], self.tenant.id)
        self.assertIsNotNone(payload["latest"])
        self.assertEqual(len(payload["history"]), 1)

    @override_settings(MONITORING_INGEST_TOKEN="heartbeat-token")
    def test_monitoring_heartbeat_creates_snapshots(self):
        response = self.client.post(
            "/monitoring/heartbeat/",
            data={
                "service_name": "worker",
                "status": "UP",
                "latency_ms": 82,
                "error_rate": 0,
                "tenant_slug": self.tenant.slug,
                "request_rate": 6.2,
                "p95_latency": 310,
                "jobs_pending": 1,
                "metadata_json": {"queue": "default"},
            },
            content_type="application/json",
            HTTP_X_MONITORING_TOKEN="heartbeat-token",
        )
        self.assertEqual(response.status_code, 202)
        self.assertTrue(SystemHealthSnapshot.objects.filter(service_name="worker").exists())
        self.assertTrue(TenantHealthSnapshot.objects.filter(tenant=self.tenant).exists())


class ControlPanelEnterpriseResourcesApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_user(
            username="enterprise-admin",
            password="strong-pass-123",
            is_staff=True,
            is_superuser=True,
        )
        company = Company.objects.create(
            name="Enterprise Tenant Co",
            tenant_code="enterprise-tenant",
            subdomain="enterprise-tenant",
            is_active=True,
        )
        self.tenant = Tenant.objects.create(
            company=company,
            legal_name="Enterprise Tenant Co",
            cnpj="12.345.678/0001-99",
            slug="enterprise-tenant",
            subdomain="enterprise-tenant",
            status=Tenant.STATUS_ACTIVE,
        )
        self.feature_finance = FeatureFlag.objects.create(
            key="finance",
            name="Financeiro",
            description="Modulo financeiro",
            is_active=True,
        )
        FeatureFlag.objects.create(
            key="commission",
            name="Comissoes",
            description="Modulo de comissoes",
            is_active=True,
        )
        self.client.force_login(self.superadmin)

    def test_notes_create_and_list(self):
        create_response = self.client.post(
            f"/control-panel/tenants/{self.tenant.id}/notes/",
            data={"note": "Tenant em onboarding enterprise."},
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertTrue(
            TenantInternalNote.objects.filter(
                tenant=self.tenant,
                note__icontains="onboarding",
            ).exists()
        )

        list_response = self.client.get(f"/control-panel/tenants/{self.tenant.id}/notes/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)

    def test_features_list_and_toggle(self):
        list_response = self.client.get(f"/control-panel/tenants/{self.tenant.id}/features/")
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertGreaterEqual(len(payload), 2)
        self.assertFalse(next(row for row in payload if row["feature"]["key"] == "finance")["enabled"])

        toggle_response = self.client.post(
            f"/control-panel/tenants/{self.tenant.id}/features/",
            data={"feature_key": "finance", "enabled": True},
            content_type="application/json",
        )
        self.assertEqual(toggle_response.status_code, 200)
        self.assertTrue(toggle_response.json()["enabled"])
        self.assertTrue(
            TenantFeatureFlag.objects.filter(
                tenant=self.tenant,
                feature=self.feature_finance,
                enabled=True,
            ).exists()
        )

    def test_audit_events_are_available_for_tenant(self):
        self.client.post(
            f"/control-panel/tenants/{self.tenant.id}/notes/",
            data={"note": "Evento de auditoria"},
            content_type="application/json",
        )
        audit_response = self.client.get(f"/control-panel/tenants/{self.tenant.id}/audit/")
        self.assertEqual(audit_response.status_code, 200)
        events = audit_response.json()
        self.assertGreaterEqual(len(events), 1)
        self.assertTrue(
            AdminAuditEvent.objects.filter(
                target_tenant=self.tenant,
                entity_type="tenant_internal_note",
            ).exists()
        )

    def test_export_tenant_data(self):
        TenantInternalNote.objects.create(
            tenant=self.tenant,
            note="Nota para exportacao",
            created_by=self.superadmin,
        )
        TenantFeatureFlag.objects.create(
            tenant=self.tenant,
            feature=self.feature_finance,
            enabled=True,
            updated_by=self.superadmin,
        )
        response = self.client.post(
            f"/control-panel/tenants/{self.tenant.id}/export/",
            data={},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["tenant"]["id"], self.tenant.id)
        self.assertGreaterEqual(len(payload["notes"]), 1)
        self.assertGreaterEqual(len(payload["features"]), 1)

    def test_limits_get_and_update(self):
        get_response = self.client.get(f"/control-panel/tenants/{self.tenant.id}/limits/")
        self.assertEqual(get_response.status_code, 200)
        self.assertIn("requests_per_minute", get_response.json())

        update_response = self.client.post(
            f"/control-panel/tenants/{self.tenant.id}/limits/",
            data={
                "requests_per_minute": 1200,
                "storage_limit_gb": "40.00",
                "docs_storage_limit_gb": "12.00",
                "module_limits_json": {"finance": {"max_records": 50000}},
            },
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["requests_per_minute"], 1200)
        self.assertTrue(
            TenantOperationalSettings.objects.filter(
                tenant=self.tenant,
                requests_per_minute=1200,
            ).exists()
        )

    def test_integrations_upsert_and_list(self):
        create_response = self.client.post(
            f"/control-panel/tenants/{self.tenant.id}/integrations/",
            data={
                "provider": "RESEND",
                "alias": "default",
                "secret_manager_ref": "projects/mks/secrets/resend-api",
                "metadata_json": {"from_email": "no-reply@test.com"},
                "is_active": True,
            },
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertTrue(
            TenantIntegrationSecretRef.objects.filter(
                tenant=self.tenant,
                provider="RESEND",
                alias="default",
            ).exists()
        )

        list_response = self.client.get(f"/control-panel/tenants/{self.tenant.id}/integrations/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)

    def test_changelog_create_and_list(self):
        create_response = self.client.post(
            f"/control-panel/tenants/{self.tenant.id}/changelog/",
            data={
                "backend_version": "2026.02.10",
                "frontend_version": "2026.02.10-ui",
                "git_sha": "abc123",
                "source": "cloud_run",
                "changelog": "Nova release com módulo de governança.",
                "is_current": True,
            },
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertTrue(
            TenantReleaseRecord.objects.filter(
                tenant=self.tenant,
                backend_version="2026.02.10",
                is_current=True,
            ).exists()
        )

        list_response = self.client.get(f"/control-panel/tenants/{self.tenant.id}/changelog/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)

    def test_alerts_list_and_resolve(self):
        alert = TenantAlertEvent.objects.create(
            tenant=self.tenant,
            alert_type=TenantAlertEvent.TYPE_HIGH_ERROR_RATE,
            severity=TenantAlertEvent.SEVERITY_WARNING,
            status=TenantAlertEvent.STATUS_OPEN,
            message="Erro alto",
            metrics_json={"error_rate": 0.31},
        )
        list_response = self.client.get(f"/control-panel/tenants/{self.tenant.id}/alerts/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)

        resolve_response = self.client.post(
            f"/control-panel/tenants/{self.tenant.id}/alerts/resolve/",
            data={"alert_id": alert.id},
            content_type="application/json",
        )
        self.assertEqual(resolve_response.status_code, 200)
        alert.refresh_from_db()
        self.assertEqual(alert.status, TenantAlertEvent.STATUS_RESOLVED)

    def test_impersonation_start_and_stop(self):
        start_response = self.client.post(
            f"/control-panel/tenants/{self.tenant.id}/impersonate/",
            data={"reason": "Suporte técnico", "duration_minutes": 15},
            content_type="application/json",
        )
        self.assertEqual(start_response.status_code, 201)
        session_id = start_response.json()["session"]["id"]
        self.assertTrue(
            TenantImpersonationSession.objects.filter(
                tenant=self.tenant,
                actor=self.superadmin,
                status=TenantImpersonationSession.STATUS_ACTIVE,
            ).exists()
        )

        stop_response = self.client.post(
            f"/control-panel/tenants/{self.tenant.id}/impersonate/stop/",
            data={"session_id": session_id},
            content_type="application/json",
        )
        self.assertEqual(stop_response.status_code, 200)
        self.assertEqual(stop_response.json()["ended_sessions"], 1)
