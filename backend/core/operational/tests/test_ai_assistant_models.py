"""Model tests for tenant-scoped IA assistant persistence."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from customers.models import Company
from operational.models import (
    AiConversation,
    AiDocumentChunk,
    AiMessage,
    AiSuggestion,
)
from tenancy.context import reset_current_company, set_current_company

User = get_user_model()


class AiAssistantModelsTests(TestCase):
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
            username="ai_user_a",
            email="ai_user_a@test.com",
            password="testpass123",
        )
        self.user_b = User.objects.create_user(
            username="ai_user_b",
            email="ai_user_b@test.com",
            password="testpass123",
        )

        self._tenant_token = set_current_company(self.company_a)
        self.conv_a = AiConversation.objects.create(
            title="Conversa A",
            status=AiConversation.Status.OPEN,
            created_by=self.user_a,
        )
        self.msg_a = AiMessage.objects.create(
            conversation=self.conv_a,
            role=AiMessage.Role.USER,
            content="Como melhorar conversao?",
            intent=AiMessage.Intent.INTERNAL_ANALYTICS,
            metadata={"source": "test"},
        )
        self.suggestion_a = AiSuggestion.objects.create(
            scope=AiSuggestion.Scope.DASHBOARD,
            title="Priorizar leads quentes",
            body="Contatar leads quentes com mais de 7 dias sem retorno.",
            severity="MEDIUM",
        )
        self.chunk_a = AiDocumentChunk.objects.create(
            source_type=AiDocumentChunk.SourceType.POLICY_DOCUMENT,
            source_id="101",
            document_name="condicoes-gerais-auto.pdf",
            mime_type="application/pdf",
            chunk_text="Cobertura de colisao e incendio.",
            chunk_order=0,
        )

        reset_current_company(self._tenant_token)
        self._tenant_token = set_current_company(self.company_b)
        self.conv_b = AiConversation.objects.create(
            title="Conversa B",
            status=AiConversation.Status.OPEN,
            created_by=self.user_b,
        )

        reset_current_company(self._tenant_token)
        self._tenant_token = set_current_company(self.company_a)

    def tearDown(self):
        reset_current_company(self._tenant_token)
        super().tearDown()

    def test_message_company_is_inherited_from_conversation(self):
        self.assertEqual(self.msg_a.company_id, self.company_a.id)
        self.assertEqual(self.msg_a.conversation_id, self.conv_a.id)

    def test_tenant_manager_scopes_queries_by_current_company(self):
        self.assertEqual(AiConversation.objects.count(), 1)
        self.assertEqual(AiConversation.objects.first().id, self.conv_a.id)
        self.assertEqual(AiMessage.objects.count(), 1)
        self.assertEqual(AiSuggestion.objects.count(), 1)
        self.assertEqual(AiDocumentChunk.objects.count(), 1)

        reset_current_company(self._tenant_token)
        self._tenant_token = set_current_company(self.company_b)
        self.assertEqual(AiConversation.objects.count(), 1)
        self.assertEqual(AiConversation.objects.first().id, self.conv_b.id)
        self.assertEqual(AiMessage.objects.count(), 0)
        self.assertEqual(AiSuggestion.objects.count(), 0)
        self.assertEqual(AiDocumentChunk.objects.count(), 0)

    def test_all_objects_can_access_cross_tenant_records(self):
        self.assertEqual(AiConversation.all_objects.count(), 2)
        self.assertEqual(AiMessage.all_objects.count(), 1)
        self.assertEqual(AiSuggestion.all_objects.count(), 1)
        self.assertEqual(AiDocumentChunk.all_objects.count(), 1)

    def test_cross_tenant_message_write_is_blocked(self):
        reset_current_company(self._tenant_token)
        self._tenant_token = set_current_company(self.company_b)

        with self.assertRaises(ValidationError):
            AiMessage.objects.create(
                conversation=self.conv_a,
                role=AiMessage.Role.USER,
                content="Tentativa cross-tenant",
                intent=AiMessage.Intent.MIXED,
            )
