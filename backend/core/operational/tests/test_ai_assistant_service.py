from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from customers.models import Company, CompanyMembership
from operational.ai_assistant_selectors import search_ai_document_chunks
from operational.ai_assistant_service import AiAssistantService, classify_ai_intents
from operational.models import AiConversation, AiDocumentChunk, AiMessage
from tenancy.context import reset_current_company, set_current_company

User = get_user_model()


class AiAssistantClassifierTests(SimpleTestCase):
    def test_classifier_detects_mixed_market_and_internal(self):
        intents = classify_ai_intents(
            "Analise minha carteira de leads e compare com o mercado de seguros.",
            include_market_research=True,
        )
        self.assertIn(AiMessage.Intent.INTERNAL_ANALYTICS, intents)
        self.assertIn(AiMessage.Intent.WEB_MARKET, intents)
        self.assertIn(AiMessage.Intent.MIXED, intents)

    def test_classifier_detects_cnpj(self):
        intents = classify_ai_intents(
            "Pesquise o CNPJ 12.345.678/0001-99 e me dê um resumo.",
            include_cnpj_enrichment=True,
        )
        self.assertIn(AiMessage.Intent.CNPJ_ENRICH, intents)


class AiAssistantSelectorsAndServiceTests(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(
            name="Tenant A",
            tenant_code="tenant-a",
            subdomain="tenant-a",
            is_active=True,
        )
        self.company_b = Company.objects.create(
            name="Tenant B",
            tenant_code="tenant-b",
            subdomain="tenant-b",
            is_active=True,
        )
        self.user_a = User.objects.create_user(
            username="assistant_owner",
            email="assistant_owner@test.com",
            password="testpass123",
        )
        CompanyMembership.objects.create(
            company=self.company_a,
            user=self.user_a,
            role=CompanyMembership.ROLE_OWNER,
            is_active=True,
        )

        self._tenant_token = set_current_company(self.company_a)
        self.chunk_a = AiDocumentChunk.objects.create(
            source_type=AiDocumentChunk.SourceType.POLICY_DOCUMENT,
            source_id="policy-100",
            document_name="condicoes-gerais-auto.pdf",
            mime_type="application/pdf",
            chunk_text="Cobertura para incendio e colisao em veiculos.",
            chunk_order=0,
        )

        reset_current_company(self._tenant_token)
        self._tenant_token = set_current_company(self.company_b)
        self.chunk_b = AiDocumentChunk.objects.create(
            source_type=AiDocumentChunk.SourceType.POLICY_DOCUMENT,
            source_id="policy-200",
            document_name="condicoes-gerais-empresarial.pdf",
            mime_type="application/pdf",
            chunk_text="Cobertura para incendio em galpoes empresariais.",
            chunk_order=0,
        )

        reset_current_company(self._tenant_token)
        self._tenant_token = set_current_company(self.company_a)

    def tearDown(self):
        reset_current_company(self._tenant_token)
        super().tearDown()

    def test_docs_selector_is_tenant_scoped(self):
        results = search_ai_document_chunks(self.company_a, "incendio", limit=10)
        ids = [row.id for row in results]
        self.assertIn(self.chunk_a.id, ids)
        self.assertNotIn(self.chunk_b.id, ids)

    def test_consult_creates_conversation_and_messages(self):
        service = AiAssistantService()
        result = service.consult(
            company=self.company_a,
            user=self.user_a,
            prompt="Analise minha carteira de clientes e leads.",
            context={
                "include_market_research": False,
                "include_financial_context": False,
                "include_commercial_context": True,
            },
        )

        self.assertEqual(AiConversation.objects.count(), 1)
        self.assertEqual(AiMessage.objects.count(), 2)
        self.assertTrue(result.get("conversation_id"))
        self.assertTrue(result.get("assistant_message_id"))
        self.assertTrue(result.get("correlation_id"))

        assistant_msg = AiMessage.objects.filter(role=AiMessage.Role.ASSISTANT).first()
        self.assertIsNotNone(assistant_msg)
        self.assertEqual(
            assistant_msg.metadata.get("correlation_id"),
            result.get("correlation_id"),
        )
