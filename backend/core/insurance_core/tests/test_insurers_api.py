from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from customers.models import Company, CompanyMembership


@override_settings(ALLOWED_HOSTS=["testserver", ".example.com"])
class InsurersAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.company = Company.objects.create(
            name="Acme",
            tenant_code="acme",
            subdomain="acme",
        )
        self.user_member = User.objects.create_user(
            username="member",
            password="pass-123",
        )
        self.user_manager = User.objects.create_user(
            username="manager",
            password="pass-123",
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

    def test_member_can_list_insurers(self):
        self.client.force_login(self.user_member)
        response = self.client.get("/api/insurance/insurers/", HTTP_X_TENANT_ID="acme")
        self.assertEqual(response.status_code, 200)

    def test_member_cannot_create_insurer(self):
        self.client.force_login(self.user_member)
        response = self.client.post(
            "/api/insurance/insurers/",
            data={"name": "Seguradora X"},
            content_type="application/json",
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_can_create_insurer(self):
        self.client.force_login(self.user_manager)
        response = self.client.post(
            "/api/insurance/insurers/",
            data={"name": "Seguradora X"},
            content_type="application/json",
            HTTP_X_TENANT_ID="acme",
        )
        self.assertEqual(response.status_code, 201)

