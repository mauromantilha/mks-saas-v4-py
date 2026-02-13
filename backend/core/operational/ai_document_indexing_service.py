from __future__ import annotations

import re
from dataclasses import dataclass

from django.contrib.postgres.search import SearchVector
from django.db import connection, transaction

from operational.models import AiDocumentChunk


@dataclass(frozen=True)
class ChunkOptions:
    max_chars: int = 900
    max_chunks: int = 40


def _normalize_text(value: str) -> str:
    text = str(value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_chunks(text: str, *, options: ChunkOptions) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", normalized) if p.strip()]
    if not paragraphs:
        paragraphs = [normalized]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > options.max_chars:
            while len(paragraph) > options.max_chars:
                head = paragraph[: options.max_chars].strip()
                if head:
                    chunks.append(head)
                    if len(chunks) >= options.max_chunks:
                        return chunks
                paragraph = paragraph[options.max_chars :].strip()
            if not paragraph:
                continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= options.max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            if len(chunks) >= options.max_chunks:
                return chunks
        current = paragraph

    if current and len(chunks) < options.max_chunks:
        chunks.append(current)

    return chunks


def index_document_source(
    *,
    company,
    source_type: str,
    source_id: str,
    document_name: str,
    mime_type: str = "",
    text: str,
    options: ChunkOptions | None = None,
) -> list[AiDocumentChunk]:
    opts = options or ChunkOptions()
    chunks = _split_chunks(text, options=opts)
    if not chunks:
        chunks = ["[GAP] Extração de conteúdo indisponível; indexado apenas por metadados."]

    source_id_str = str(source_id)
    with transaction.atomic():
        AiDocumentChunk.all_objects.filter(
            company=company,
            source_type=source_type,
            source_id=source_id_str,
        ).delete()

        objects = [
            AiDocumentChunk(
                company=company,
                source_type=source_type,
                source_id=source_id_str,
                document_name=str(document_name or "documento"),
                mime_type=str(mime_type or ""),
                chunk_text=chunk_text,
                chunk_order=idx,
            )
            for idx, chunk_text in enumerate(chunks)
        ]
        created = AiDocumentChunk.all_objects.bulk_create(objects)

        if connection.vendor == "postgresql" and created:
            AiDocumentChunk.all_objects.filter(id__in=[row.id for row in created]).update(
                search_vector=SearchVector("chunk_text", config="portuguese"),
            )
    return created


def index_policy_document(policy_document) -> list[AiDocumentChunk]:
    if not getattr(policy_document, "uploaded_at", None):
        return []
    if getattr(policy_document, "deleted_at", None):
        return []

    policy = getattr(policy_document, "policy", None)
    policy_label = ""
    if policy is not None:
        policy_label = str(getattr(policy, "policy_number", "") or f"Policy #{policy.pk}")

    text = "\n\n".join(
        filter(
            None,
            [
                f"Documento: {getattr(policy_document, 'file_name', '')}",
                f"Tipo: {getattr(policy_document, 'document_type', '')}",
                f"Policy: {policy_label}",
                f"Storage key: {getattr(policy_document, 'storage_key', '')}",
                "[GAP] Conteúdo binário do arquivo não foi extraído neste ambiente.",
            ],
        )
    )

    return index_document_source(
        company=policy_document.company,
        source_type=AiDocumentChunk.SourceType.POLICY_DOCUMENT,
        source_id=str(policy_document.pk),
        document_name=str(getattr(policy_document, "file_name", "") or f"policy-document-{policy_document.pk}"),
        mime_type=str(getattr(policy_document, "content_type", "") or ""),
        text=text,
    )


def index_special_project_document(project_document) -> list[AiDocumentChunk]:
    file_name = ""
    file_obj = getattr(project_document, "file", None)
    if file_obj:
        file_name = getattr(file_obj, "name", "")

    text = "\n\n".join(
        filter(
            None,
            [
                f"Documento: {getattr(project_document, 'title', '')}",
                f"Arquivo: {file_name}",
                f"Projeto: {getattr(getattr(project_document, 'project', None), 'name', '')}",
                str(getattr(project_document, "notes", "") or "").strip(),
                "[GAP] Conteúdo do arquivo não foi extraído automaticamente; indexação por metadados.",
            ],
        )
    )

    return index_document_source(
        company=project_document.company,
        source_type=AiDocumentChunk.SourceType.SPECIAL_PROJECT_DOCUMENT,
        source_id=str(project_document.pk),
        document_name=str(getattr(project_document, "title", "") or file_name or f"special-project-document-{project_document.pk}"),
        mime_type="",
        text=text,
    )

