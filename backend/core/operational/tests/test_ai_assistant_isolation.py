from django.contrib.auth import get_user_model
from django.test import TestCase

from customers.models import Company, CompanyMembership
from operational.models import AiDocumentChunk, AiMessage, AiSuggestion

User = get_user_model()


class AiAssistantIsolationTests(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(
            name="Tenant Isolation A",
            tenant_code="tenant-iso-a",
            subdomain="tenant-iso-a",
            is_active=True,
        )
        self.company_b = Company.objects.create(
            name="Tenant Isolation B",
            tenant_code="tenant-iso-b",
            subdomain="tenant-iso-b",
            is_active=True,
        )

        self.user_a = User.objects.create_user(
            username="iso-user-a",
            email="iso-user-a@test.com",
            password="testpass123",
        )
        self.user_b = User.objects.create_user(
            username="iso-user-b",
            email="iso-user-b@test.com",
            password="testpass123",
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

        self.chunk_a = AiDocumentChunk.all_objects.create(
            company=self.company_a,
            source_type=AiDocumentChunk.SourceType.POLICY_DOCUMENT,
            source_id="policy-a-001",
            document_name="condicoes-gerais-a.pdf",
            mime_type="application/pdf",
            chunk_text="Cláusula de incêndio e assistência 24h para automóveis.",
            chunk_order=0,
        )
        self.chunk_b = AiDocumentChunk.all_objects.create(
            company=self.company_b,
            source_type=AiDocumentChunk.SourceType.POLICY_DOCUMENT,
            source_id="policy-b-001",
            document_name="condicoes-gerais-b.pdf",
            mime_type="application/pdf",
            chunk_text="Cobertura empresarial para incêndio e responsabilidade civil.",
            chunk_order=0,
        )

    def _consult(self, *, user, tenant_code: str, prompt: str):
        self.client.force_login(user)
        return self.client.post(
            "/api/ai-assistant/consult/",
            data={"prompt": prompt},
            content_type="application/json",
            HTTP_X_TENANT_ID=tenant_code,
        )

    def test_conversations_and_messages_do_not_leak_between_tenants(self):
        res_a = self._consult(
            user=self.user_a,
            tenant_code="tenant-iso-a",
            prompt="Analise minha carteira comercial.",
        )
        self.assertEqual(res_a.status_code, 201)
        conversation_id_a = res_a.json()["conversation_id"]

        res_b = self._consult(
            user=self.user_b,
            tenant_code="tenant-iso-b",
            prompt="Analise meu funil de vendas.",
        )
        self.assertEqual(res_b.status_code, 201)
        conversation_id_b = res_b.json()["conversation_id"]

        self.client.force_login(self.user_a)
        list_a = self.client.get(
            "/api/ai-assistant/conversations/",
            HTTP_X_TENANT_ID="tenant-iso-a",
        )
        self.assertEqual(list_a.status_code, 200)
        ids_a = {row["id"] for row in list_a.json().get("results", [])}
        self.assertIn(conversation_id_a, ids_a)
        self.assertNotIn(conversation_id_b, ids_a)

        self.client.force_login(self.user_b)
        list_b = self.client.get(
            "/api/ai-assistant/conversations/",
            HTTP_X_TENANT_ID="tenant-iso-b",
        )
        self.assertEqual(list_b.status_code, 200)
        ids_b = {row["id"] for row in list_b.json().get("results", [])}
        self.assertIn(conversation_id_b, ids_b)
        self.assertNotIn(conversation_id_a, ids_b)

        cross_detail = self.client.get(
            f"/api/ai-assistant/conversations/{conversation_id_a}/",
            HTTP_X_TENANT_ID="tenant-iso-b",
        )
        self.assertEqual(cross_detail.status_code, 404)

    def test_dashboard_suggestions_are_tenant_scoped(self):
        self.client.force_login(self.user_a)
        response_a = self.client.get(
            "/api/ai-assistant/dashboard-suggestions/",
            HTTP_X_TENANT_ID="tenant-iso-a",
        )
        self.assertEqual(response_a.status_code, 200)
        ids_a = {row["id"] for row in response_a.json().get("results", [])}

        self.client.force_login(self.user_b)
        response_b = self.client.get(
            "/api/ai-assistant/dashboard-suggestions/",
            HTTP_X_TENANT_ID="tenant-iso-b",
        )
        self.assertEqual(response_b.status_code, 200)
        ids_b = {row["id"] for row in response_b.json().get("results", [])}

        company_a_ids = set(
            AiSuggestion.all_objects.filter(company=self.company_a).values_list("id", flat=True)
        )
        company_b_ids = set(
            AiSuggestion.all_objects.filter(company=self.company_b).values_list("id", flat=True)
        )

        self.assertTrue(ids_a.issubset(company_a_ids))
        self.assertTrue(ids_b.issubset(company_b_ids))
        self.assertFalse(ids_a & company_b_ids)
        self.assertFalse(ids_b & company_a_ids)

    def test_consult_registers_correlation_intent_and_source_metadata(self):
        response = self._consult(
            user=self.user_a,
            tenant_code="tenant-iso-a",
            prompt="Mostre documento e cláusula de incêndio desta apólice.",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        conversation_id = payload["conversation_id"]
        correlation_id = payload.get("correlation_id")

        messages = list(
            AiMessage.all_objects.filter(
                company=self.company_a,
                conversation_id=conversation_id,
            ).order_by("created_at", "id")
        )
        self.assertEqual(len(messages), 2)

        user_msg, assistant_msg = messages
        self.assertEqual(user_msg.role, AiMessage.Role.USER)
        self.assertEqual(assistant_msg.role, AiMessage.Role.ASSISTANT)

        self.assertEqual(user_msg.metadata.get("correlation_id"), correlation_id)
        self.assertTrue(isinstance(user_msg.metadata.get("intents"), list))

        self.assertEqual(assistant_msg.metadata.get("correlation_id"), correlation_id)
        self.assertTrue(assistant_msg.metadata.get("intent"))
        self.assertTrue(isinstance(assistant_msg.metadata.get("intents"), list))

        sources = assistant_msg.metadata.get("sources") or {}
        internal_sources = sources.get("internal_sources") or []
        web_sources = sources.get("web_sources") or []

        for source in internal_sources:
            self.assertNotIn("chunk_text", source)
            self.assertNotIn("content", source)

        for source in web_sources:
            snippet = str(source.get("snippet") or "")
            self.assertLessEqual(len(snippet), 280)
