from django.contrib.auth import get_user_model
from django.test import TestCase

from customers.models import Company, CompanyMembership


class AuthEndpointsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user_member = User.objects.create_user(
            username="auth-user",
            password="test-pass-123",
            email="auth@example.com",
        )
        self.user_manager = User.objects.create_user(
            username="auth-manager",
            password="test-pass-456",
            email="auth-manager@example.com",
        )
        self.user_owner = User.objects.create_user(
            username="auth-owner",
            password="test-pass-789",
            email="auth-owner@example.com",
        )
        self.user_candidate = User.objects.create_user(
            username="auth-candidate",
            password="test-pass-901",
            email="auth-candidate@example.com",
        )
        self.user_foreign_owner = User.objects.create_user(
            username="foreign-owner",
            password="test-pass-000",
            email="foreign-owner@example.com",
        )
        self.company = Company.objects.create(
            name="Auth Company",
            tenant_code="auth-company",
            subdomain="auth-company",
        )
        self.company_b = Company.objects.create(
            name="Other Company",
            tenant_code="other-company",
            subdomain="other-company",
        )
        CompanyMembership.objects.create(
            company=self.company,
            user=self.user_member,
            role=CompanyMembership.ROLE_MEMBER,
        )
        CompanyMembership.objects.create(
            company=self.company,
            user=self.user_manager,
            role=CompanyMembership.ROLE_MANAGER,
        )
        CompanyMembership.objects.create(
            company=self.company,
            user=self.user_owner,
            role=CompanyMembership.ROLE_OWNER,
        )
        self.foreign_membership = CompanyMembership.objects.create(
            company=self.company_b,
            user=self.user_foreign_owner,
            role=CompanyMembership.ROLE_OWNER,
        )

    def test_auth_me_requires_authentication(self):
        response = self.client.get("/api/auth/me/")
        self.assertIn(response.status_code, (401, 403))

    def test_auth_me_returns_user_memberships(self):
        self.client.force_login(self.user_member)
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["username"], self.user_member.username)
        self.assertEqual(len(payload["memberships"]), 1)
        self.assertEqual(payload["memberships"][0]["tenant_code"], "auth-company")

    def test_auth_tenant_me_requires_tenant_identifier(self):
        self.client.force_login(self.user_member)
        response = self.client.get("/api/auth/tenant-me/")
        self.assertEqual(response.status_code, 400)

    def test_auth_tenant_me_returns_role(self):
        self.client.force_login(self.user_member)
        response = self.client.get(
            "/api/auth/tenant-me/",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["tenant_code"], "auth-company")
        self.assertEqual(payload["role"], CompanyMembership.ROLE_MEMBER)

    def test_auth_capabilities_requires_tenant_identifier(self):
        self.client.force_login(self.user_member)
        response = self.client.get("/api/auth/capabilities/")
        self.assertEqual(response.status_code, 400)

    def test_auth_capabilities_for_member(self):
        self.client.force_login(self.user_member)
        response = self.client.get(
            "/api/auth/capabilities/",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["role"], CompanyMembership.ROLE_MEMBER)
        self.assertTrue(payload["capabilities"]["customers"]["list"])
        self.assertFalse(payload["capabilities"]["customers"]["create"])
        self.assertFalse(payload["capabilities"]["customers"]["delete"])
        self.assertFalse(payload["capabilities"]["apolices"]["create"])
        self.assertFalse(payload["capabilities"]["endossos"]["create"])

    def test_auth_capabilities_for_manager(self):
        self.client.force_login(self.user_manager)
        response = self.client.get(
            "/api/auth/capabilities/",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["role"], CompanyMembership.ROLE_MANAGER)
        self.assertTrue(payload["capabilities"]["customers"]["create"])
        self.assertTrue(payload["capabilities"]["leads"]["create"])
        self.assertFalse(payload["capabilities"]["apolices"]["create"])
        self.assertFalse(payload["capabilities"]["endossos"]["create"])
        self.assertFalse(payload["capabilities"]["customers"]["delete"])

    def test_auth_capabilities_reflect_company_rbac_overrides(self):
        self.company.rbac_overrides = {"apolices": {"POST": ["OWNER", "MANAGER"]}}
        self.company.save(update_fields=["rbac_overrides"])

        self.client.force_login(self.user_manager)
        response = self.client.get(
            "/api/auth/capabilities/",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["capabilities"]["apolices"]["create"])

    def test_tenant_rbac_get_allowed_for_member(self):
        self.client.force_login(self.user_member)
        response = self.client.get(
            "/api/auth/tenant-rbac/",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["tenant_code"], "auth-company")
        self.assertEqual(payload["rbac_overrides"], {})
        self.assertIn("customers", payload["effective_role_matrices"])

    def test_tenant_rbac_put_denied_for_manager(self):
        self.client.force_login(self.user_manager)
        response = self.client.put(
            "/api/auth/tenant-rbac/",
            data={"apolices": {"POST": ["OWNER", "MANAGER"]}},
            content_type="application/json",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 403)

    def test_tenant_rbac_put_allowed_for_owner(self):
        self.client.force_login(self.user_owner)
        response = self.client.put(
            "/api/auth/tenant-rbac/",
            data={"apolices": {"post": ["owner", "manager"]}},
            content_type="application/json",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["rbac_overrides"]["apolices"]["POST"], ["MANAGER", "OWNER"])

        self.company.refresh_from_db()
        self.assertEqual(
            self.company.rbac_overrides,
            {"apolices": {"POST": ["MANAGER", "OWNER"]}},
        )

    def test_tenant_rbac_patch_merges_with_existing_overrides(self):
        self.company.rbac_overrides = {"apolices": {"POST": ["OWNER", "MANAGER"]}}
        self.company.save(update_fields=["rbac_overrides"])

        self.client.force_login(self.user_owner)
        response = self.client.patch(
            "/api/auth/tenant-rbac/",
            data={"endossos": {"POST": ["OWNER", "MANAGER"]}},
            content_type="application/json",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["rbac_overrides"],
            {
                "apolices": {"POST": ["MANAGER", "OWNER"]},
                "endossos": {"POST": ["MANAGER", "OWNER"]},
            },
        )

    def test_tenant_rbac_put_rejects_invalid_payload(self):
        self.client.force_login(self.user_owner)
        response = self.client.put(
            "/api/auth/tenant-rbac/",
            data={"unknown_resource": {"POST": ["OWNER"]}},
            content_type="application/json",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 400)

    def test_tenant_members_get_allowed_for_member(self):
        self.client.force_login(self.user_member)
        response = self.client.get(
            "/api/auth/tenant-members/",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["tenant_code"], "auth-company")
        usernames = [item["username"] for item in payload["results"]]
        self.assertIn("auth-owner", usernames)
        self.assertIn("auth-manager", usernames)
        self.assertIn("auth-user", usernames)

    def test_tenant_members_post_denied_for_manager(self):
        self.client.force_login(self.user_manager)
        response = self.client.post(
            "/api/auth/tenant-members/",
            data={
                "username": "auth-candidate",
                "role": CompanyMembership.ROLE_MEMBER,
                "is_active": True,
            },
            content_type="application/json",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 403)

    def test_tenant_members_post_allowed_for_owner(self):
        self.client.force_login(self.user_owner)
        response = self.client.post(
            "/api/auth/tenant-members/",
            data={
                "username": "auth-candidate",
                "role": CompanyMembership.ROLE_MEMBER,
                "is_active": True,
            },
            content_type="application/json",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["username"], "auth-candidate")
        self.assertEqual(payload["role"], CompanyMembership.ROLE_MEMBER)

    def test_tenant_members_post_rejects_unknown_user(self):
        self.client.force_login(self.user_owner)
        response = self.client.post(
            "/api/auth/tenant-members/",
            data={
                "username": "unknown-user",
                "role": CompanyMembership.ROLE_MEMBER,
                "is_active": True,
            },
            content_type="application/json",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 400)

    def test_tenant_members_patch_allowed_for_owner(self):
        membership = CompanyMembership.objects.create(
            company=self.company,
            user=self.user_candidate,
            role=CompanyMembership.ROLE_MEMBER,
        )
        self.client.force_login(self.user_owner)
        response = self.client.patch(
            f"/api/auth/tenant-members/{membership.id}/",
            data={"role": CompanyMembership.ROLE_MANAGER},
            content_type="application/json",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], CompanyMembership.ROLE_MANAGER)

    def test_tenant_members_patch_rejects_owner_self_demotion(self):
        own_membership = CompanyMembership.objects.get(
            company=self.company,
            user=self.user_owner,
        )
        self.client.force_login(self.user_owner)
        response = self.client.patch(
            f"/api/auth/tenant-members/{own_membership.id}/",
            data={"role": CompanyMembership.ROLE_MEMBER},
            content_type="application/json",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 400)

    def test_tenant_members_patch_isolated_by_tenant(self):
        self.client.force_login(self.user_owner)
        response = self.client.patch(
            f"/api/auth/tenant-members/{self.foreign_membership.id}/",
            data={"role": CompanyMembership.ROLE_MEMBER},
            content_type="application/json",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 404)

    def test_tenant_members_delete_owner_can_deactivate_other_member(self):
        membership = CompanyMembership.objects.create(
            company=self.company,
            user=self.user_candidate,
            role=CompanyMembership.ROLE_MEMBER,
            is_active=True,
        )
        self.client.force_login(self.user_owner)
        response = self.client.delete(
            f"/api/auth/tenant-members/{membership.id}/",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 204)
        membership.refresh_from_db()
        self.assertFalse(membership.is_active)

    def test_tenant_members_delete_rejects_owner_self_delete(self):
        own_membership = CompanyMembership.objects.get(
            company=self.company,
            user=self.user_owner,
        )
        self.client.force_login(self.user_owner)
        response = self.client.delete(
            f"/api/auth/tenant-members/{own_membership.id}/",
            HTTP_X_TENANT_ID="auth-company",
        )
        self.assertEqual(response.status_code, 400)
