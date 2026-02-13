from django.test import TestCase

from customers.models import Company
from operational.ai_assistant_selectors import search_ai_document_chunks
from operational.ai_document_indexing_service import index_document_source
from operational.models import AiDocumentChunk


class AiDocumentIndexSearchTests(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(
            name="Docs Tenant A",
            tenant_code="docs-tenant-a",
            subdomain="docs-tenant-a",
            is_active=True,
        )
        self.company_b = Company.objects.create(
            name="Docs Tenant B",
            tenant_code="docs-tenant-b",
            subdomain="docs-tenant-b",
            is_active=True,
        )

    def test_search_is_tenant_scoped(self):
        chunk_a = AiDocumentChunk.all_objects.create(
            company=self.company_a,
            source_type=AiDocumentChunk.SourceType.GENERIC_DOCUMENT,
            source_id="gen-a-01",
            document_name="manual-a.txt",
            mime_type="text/plain",
            chunk_text="Regra de sinistro para carteira automotiva.",
            chunk_order=0,
        )
        chunk_b = AiDocumentChunk.all_objects.create(
            company=self.company_b,
            source_type=AiDocumentChunk.SourceType.GENERIC_DOCUMENT,
            source_id="gen-b-01",
            document_name="manual-b.txt",
            mime_type="text/plain",
            chunk_text="Regra de sinistro para carteira empresarial.",
            chunk_order=0,
        )

        results_a = search_ai_document_chunks(self.company_a, "sinistro", limit=10)
        ids_a = {row.id for row in results_a}
        self.assertIn(chunk_a.id, ids_a)
        self.assertNotIn(chunk_b.id, ids_a)

        results_b = search_ai_document_chunks(self.company_b, "sinistro", limit=10)
        ids_b = {row.id for row in results_b}
        self.assertIn(chunk_b.id, ids_b)
        self.assertNotIn(chunk_a.id, ids_b)

    def test_search_limit_is_enforced(self):
        AiDocumentChunk.all_objects.create(
            company=self.company_a,
            source_type=AiDocumentChunk.SourceType.GENERIC_DOCUMENT,
            source_id="gen-a-limit-1",
            document_name="A-doc.txt",
            mime_type="text/plain",
            chunk_text="alpha texto 1",
            chunk_order=1,
        )
        AiDocumentChunk.all_objects.create(
            company=self.company_a,
            source_type=AiDocumentChunk.SourceType.GENERIC_DOCUMENT,
            source_id="gen-a-limit-2",
            document_name="A-doc.txt",
            mime_type="text/plain",
            chunk_text="alpha texto 2",
            chunk_order=0,
        )
        AiDocumentChunk.all_objects.create(
            company=self.company_a,
            source_type=AiDocumentChunk.SourceType.GENERIC_DOCUMENT,
            source_id="gen-a-limit-3",
            document_name="B-doc.txt",
            mime_type="text/plain",
            chunk_text="alpha texto 3",
            chunk_order=0,
        )

        results = search_ai_document_chunks(self.company_a, "alpha", limit=2)
        self.assertEqual(len(results), 2)

    def test_index_document_source_replaces_previous_chunks_for_same_source(self):
        created_first = index_document_source(
            company=self.company_a,
            source_type=AiDocumentChunk.SourceType.GENERIC_DOCUMENT,
            source_id="policy-reindex-1",
            document_name="condicoes-reindex-v1.txt",
            mime_type="text/plain",
            text="versao antiga do documento\n\nsem o termo especial",
        )
        self.assertGreaterEqual(len(created_first), 1)

        created_second = index_document_source(
            company=self.company_a,
            source_type=AiDocumentChunk.SourceType.GENERIC_DOCUMENT,
            source_id="policy-reindex-1",
            document_name="condicoes-reindex-v2.txt",
            mime_type="text/plain",
            text="versao nova com termo gamaespecial para busca",
        )
        self.assertGreaterEqual(len(created_second), 1)

        persisted = list(
            AiDocumentChunk.all_objects.filter(
                company=self.company_a,
                source_type=AiDocumentChunk.SourceType.GENERIC_DOCUMENT,
                source_id="policy-reindex-1",
            ).order_by("chunk_order", "id")
        )
        self.assertEqual(len(persisted), len(created_second))

        found = search_ai_document_chunks(self.company_a, "gamaespecial", limit=10)
        self.assertTrue(found)
        self.assertTrue(any(row.source_id == "policy-reindex-1" for row in found))
