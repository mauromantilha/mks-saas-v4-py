from django.contrib.auth import get_user_model
from django.test import TestCase

from customers.models import Company, CompanyMembership
from operational.models import AiSuggestion

User = get_user_model()


class AiAssistantApiSmokeTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            username="ai-api-user-a",
            email="ai-api-a@test.com",
            password="testpass123",
        )
        self.user_b = User.objects.create_user(
            username="ai-api-user-b",
            email="ai-api-b@test.com",
            password="testpass123",
        )
        self.company_a = Company.objects.create(
            name="Tenant A",
            tenant_code="tenant-api-a",
            subdomain="tenant-api-a",
            is_active=True,
        )
        self.company_b = Company.objects.create(
            name="Tenant B",
            tenant_code="tenant-api-b",
            subdomain="tenant-api-b",
            is_active=True,
        )
        CompanyMembership.objects.create(
            company=self.company_a,
            user=self.user_a,
            role=CompanyMembership.ROLE_OWNER,
            is_active=True,
        )
        CompanyMembership.objects.create(
            company=self.company_b,
            user=self.user_b,
            role=CompanyMembership.ROLE_OWNER,
            is_active=True,
        )

    def test_consult_and_conversation_message_smoke(self):
        self.client.force_login(self.user_a)
        response = self.client.post(
            "/api/ai-assistant/consult/",
            data={"prompt": "Analise minha carteira de clientes."},
            content_type="application/json",
            HTTP_X_TENANT_ID="tenant-api-a",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertIn("conversation_id", payload)
        self.assertIn("answer", payload)
        self.assertIn("sources", payload)
        self.assertIn("metrics_used", payload)
        self.assertIn("suggestions", payload)

        conversation_id = payload["conversation_id"]
        message_response = self.client.post(
            f"/api/ai-assistant/conversations/{conversation_id}/message/",
            data={"prompt": "E os leads mais quentes?"},
            content_type="application/json",
            HTTP_X_TENANT_ID="tenant-api-a",
        )
        self.assertEqual(message_response.status_code, 201)
        message_payload = message_response.json()
        self.assertEqual(message_payload["conversation_id"], conversation_id)
        self.assertIn("answer", message_payload)

    def test_dashboard_suggestions_smoke_and_cache(self):
        self.client.force_login(self.user_a)
        first = self.client.get(
            "/api/ai-assistant/dashboard-suggestions/",
            HTTP_X_TENANT_ID="tenant-api-a",
        )
        self.assertEqual(first.status_code, 200)
        first_payload = first.json()
        self.assertIn("cache", first_payload)
        self.assertIn("results", first_payload)
        self.assertGreaterEqual(len(first_payload["results"]), 1)
        self.assertTrue(
            AiSuggestion.all_objects.filter(
                company=self.company_a,
                scope=AiSuggestion.Scope.DASHBOARD,
            ).exists()
        )

        second = self.client.get(
            "/api/ai-assistant/dashboard-suggestions/",
            HTTP_X_TENANT_ID="tenant-api-a",
        )
        self.assertEqual(second.status_code, 200)
        second_payload = second.json()
        self.assertTrue(second_payload["cache"]["cached"])

    def test_conversation_detail_is_tenant_isolated(self):
        self.client.force_login(self.user_a)
        consult = self.client.post(
            "/api/ai-assistant/consult/",
            data={"prompt": "Resumo do funil comercial."},
            content_type="application/json",
            HTTP_X_TENANT_ID="tenant-api-a",
        )
        self.assertEqual(consult.status_code, 201)
        conversation_id = consult.json()["conversation_id"]

        self.client.force_login(self.user_b)
        response = self.client.get(
            f"/api/ai-assistant/conversations/{conversation_id}/",
            HTTP_X_TENANT_ID="tenant-api-b",
        )
        self.assertEqual(response.status_code, 404)

