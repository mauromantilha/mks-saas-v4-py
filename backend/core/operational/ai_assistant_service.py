from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from django.utils import timezone

from customers.models import CompanyMembership
from ledger.services import append_ledger_entry
from operational.ai import lookup_cnpj_profile, sanitize_cnpj
from operational.ai_assistant_selectors import (
    build_internal_analytics_snapshot,
    build_system_health_snapshot,
    search_ai_document_chunks,
)
from operational.models import AiConversation, AiMessage
from tenancy.rbac import DEFAULT_TENANT_ROLE_MATRIX, get_resource_role_matrices, role_can

_CNPJ_PATTERN = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")

_WEB_MARKET_KEYWORDS = (
    "mercado",
    "benchmark",
    "tendencia",
    "tendência",
    "susep",
    "seguradora",
    "seguro",
    "ramos",
    "produto",
)
_INTERNAL_ANALYTICS_KEYWORDS = (
    "carteira",
    "lead",
    "funil",
    "oportunidade",
    "cliente",
    "parcela",
    "financeiro",
    "inadimpl",
    "apolice",
    "apólice",
    "venda",
)
_DOCS_RAG_KEYWORDS = (
    "documento",
    "pdf",
    "clausula",
    "cláusula",
    "condicoes gerais",
    "condições gerais",
    "apólice",
    "arquivo",
)
_SYSTEM_HEALTH_KEYWORDS = (
    "saude do sistema",
    "saúde do sistema",
    "monitor",
    "alerta",
    "latencia",
    "latência",
    "erro",
    "health",
)

_INTENT_ORDER = (
    AiMessage.Intent.INTERNAL_ANALYTICS,
    AiMessage.Intent.SYSTEM_HEALTH,
    AiMessage.Intent.CNPJ_ENRICH,
    AiMessage.Intent.DOCS_RAG,
    AiMessage.Intent.WEB_MARKET,
)


def _extract_cnpjs(text: str) -> list[str]:
    values: list[str] = []
    for match in _CNPJ_PATTERN.findall(text or ""):
        normalized = sanitize_cnpj(match)
        if normalized and normalized not in values:
            values.append(normalized)
    return values


def classify_ai_intents(
    prompt: str,
    *,
    include_market_research: bool = True,
    include_cnpj_enrichment: bool = True,
    explicit_cnpj: str = "",
) -> list[str]:
    text = str(prompt or "").strip().lower()
    intents: set[str] = set()

    if any(keyword in text for keyword in _INTERNAL_ANALYTICS_KEYWORDS):
        intents.add(AiMessage.Intent.INTERNAL_ANALYTICS)

    if any(keyword in text for keyword in _DOCS_RAG_KEYWORDS):
        intents.add(AiMessage.Intent.DOCS_RAG)

    if any(keyword in text for keyword in _SYSTEM_HEALTH_KEYWORDS):
        intents.add(AiMessage.Intent.SYSTEM_HEALTH)

    if include_market_research and any(keyword in text for keyword in _WEB_MARKET_KEYWORDS):
        intents.add(AiMessage.Intent.WEB_MARKET)

    raw_cnpj = sanitize_cnpj(explicit_cnpj) or (next(iter(_extract_cnpjs(text)), ""))
    if include_cnpj_enrichment and raw_cnpj:
        intents.add(AiMessage.Intent.CNPJ_ENRICH)

    if not intents:
        intents.add(AiMessage.Intent.INTERNAL_ANALYTICS)

    ordered = [intent for intent in _INTENT_ORDER if intent in intents]
    if len(ordered) > 1:
        ordered.append(AiMessage.Intent.MIXED)
    return ordered


class WebResearchUnavailable(RuntimeError):
    pass


class WebSearchProvider:
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        raise NotImplementedError


class DefaultWebSearchProvider(WebSearchProvider):
    def __init__(self):
        self.api_key = (
            os.getenv("SERPER_API_KEY")
            or os.getenv("AI_WEBSEARCH_API_KEY")
            or ""
        ).strip()
        self.endpoint = os.getenv("SERPER_ENDPOINT", "https://google.serper.dev/search").strip()
        self.timeout = float(os.getenv("SERPER_TIMEOUT_SECONDS", "8"))

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        if not self.api_key:
            raise WebResearchUnavailable("Web research indisponível: SERPER_API_KEY não configurada.")

        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise WebResearchUnavailable(
                "Web research indisponível: dependência httpx não encontrada."
            ) from exc

        normalized_limit = max(1, min(10, int(limit)))
        payload = {"q": query, "num": normalized_limit}
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}

        try:  # pragma: no cover - external integration
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.endpoint, headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
        except Exception as exc:  # pragma: no cover - external integration
            raise WebResearchUnavailable(f"Web research falhou: {exc}") from exc

        results: list[dict[str, str]] = []
        for row in body.get("organic", [])[:normalized_limit]:
            url = str(row.get("link") or "").strip()
            title = str(row.get("title") or "").strip()
            snippet = str(row.get("snippet") or "").strip()
            if not url:
                continue
            if len(snippet) > 280:
                snippet = f"{snippet[:277]}..."
            results.append({"url": url, "title": title, "snippet": snippet})
        return results


@dataclass
class CapabilityGate:
    company: Any
    user: Any
    role: str | None
    matrices: dict[str, dict[str, frozenset]]

    @classmethod
    def build(cls, company, user):
        role = None
        if user and getattr(user, "is_authenticated", False) and not getattr(user, "is_superuser", False):
            membership = (
                CompanyMembership.objects.filter(
                    company=company,
                    user=user,
                    is_active=True,
                )
                .only("role")
                .first()
            )
            role = membership.role if membership else None

        return cls(
            company=company,
            user=user,
            role=role,
            matrices=get_resource_role_matrices(company=company),
        )

    def can(self, resource: str, method: str = "GET") -> bool:
        if self.user and getattr(self.user, "is_superuser", False):
            return True
        if not self.role:
            return False
        matrix = self.matrices.get(resource, DEFAULT_TENANT_ROLE_MATRIX)
        return role_can(matrix, self.role, method.upper())

    def ai_capabilities(self) -> dict[str, bool]:
        crm_read = any(
            self.can(resource, "GET")
            for resource in ("customers", "leads", "opportunities", "activities")
        )
        return {
            "tenant.ai.use": self.can("ai_assistant", "POST"),
            "tenant.ai.web": self.can("ai_assistant", "POST"),
            "tenant.ai.docs": self.can("apolices", "GET") or self.can("policies", "GET"),
            "tenant.ai.finance": all(
                self.can(resource, "GET") for resource in ("payables", "installments", "invoices")
            ),
            "tenant.ai.crm": crm_read,
            "tenant.ai.admin": self.can("dashboard", "GET") or self.can("ledger", "GET"),
        }


class InternalAnalyticsTool:
    def run(
        self,
        *,
        company,
        include_financial_context: bool,
        include_commercial_context: bool,
    ) -> dict[str, Any]:
        snapshot = build_internal_analytics_snapshot(
            company,
            include_financial_context=include_financial_context,
            include_commercial_context=include_commercial_context,
        )
        summary = snapshot.get("summary", {})
        commercial = summary.get("commercial", {})
        financial = summary.get("financial", {})
        insurance = summary.get("insurance", {})

        highlights: list[str] = []
        if commercial:
            highlights.append(
                "CRM: "
                f"{commercial.get('customers_total', 0)} clientes, "
                f"{commercial.get('leads', {}).get('total', 0)} leads, "
                f"{commercial.get('opportunities', {}).get('total', 0)} oportunidades."
            )
        if financial:
            highlights.append(
                "Financeiro: "
                f"aberto em recebíveis R$ {financial.get('receivables_open_total', 0):.2f}, "
                f"aberto em pagamentos R$ {financial.get('payables_open_total', 0):.2f}."
            )
        if insurance:
            highlights.append(
                "Operação de seguros: "
                f"{insurance.get('legacy_apolices_active', 0)} apólices legadas ativas, "
                f"{insurance.get('core_policies_active', 0)} apólices core ativas."
            )

        return {
            "tool": "internal_analytics",
            "ok": True,
            "answer": " ".join(highlights).strip(),
            "metrics_used": snapshot.get("metrics", []),
            "internal_sources": snapshot.get("datasets", []),
            "warnings": [],
            "next_actions": [
                "Priorizar oportunidades com maior probabilidade de fechamento.",
                "Atacar inadimplência e parcelas vencidas com régua de cobrança ativa.",
            ],
            "cnpj_profile": {},
        }


class SystemHealthTool:
    def run(self, *, company) -> dict[str, Any]:
        health = build_system_health_snapshot(company)
        if not health.get("available"):
            return {
                "tool": "system_health",
                "ok": False,
                "answer": "",
                "metrics_used": [],
                "internal_sources": [],
                "warnings": [health.get("reason") or "Health snapshot indisponível."],
                "next_actions": ["Validar ingestão de monitoramento do tenant."],
                "cnpj_profile": {},
            }

        summary = health.get("summary", {})
        answer = (
            "Saúde do tenant: "
            f"status={health.get('status')}, "
            f"erro={summary.get('error_rate', 0):.2%}, "
            f"latência p95={summary.get('p95_latency', 0):.0f}ms, "
            f"jobs pendentes={summary.get('jobs_pending', 0)}."
        )
        metrics = [
            {
                "key": "system.error_rate",
                "value": summary.get("error_rate", 0),
                "source": "control_plane.tenant_health",
                "period": "latest",
            },
            {
                "key": "system.p95_latency",
                "value": summary.get("p95_latency", 0),
                "source": "control_plane.tenant_health",
                "period": "latest",
            },
        ]
        return {
            "tool": "system_health",
            "ok": True,
            "answer": answer,
            "metrics_used": metrics,
            "internal_sources": [
                {"name": "control_plane.tenant_health", "ids": []},
                {
                    "name": "control_plane.alerts",
                    "ids": [row.get("id") for row in health.get("alerts", []) if row.get("id")],
                },
            ],
            "warnings": [],
            "next_actions": list(health.get("recommendations") or []),
            "cnpj_profile": {},
        }


class CnpjEnrichTool:
    def run(self, *, prompt: str, explicit_cnpj: str = "") -> dict[str, Any]:
        cnpj = sanitize_cnpj(explicit_cnpj)
        if not cnpj:
            extracted = _extract_cnpjs(prompt)
            cnpj = extracted[0] if extracted else ""

        if not cnpj:
            return {
                "tool": "cnpj_enrich",
                "ok": False,
                "answer": "",
                "metrics_used": [],
                "internal_sources": [],
                "warnings": ["Nenhum CNPJ válido encontrado para enriquecimento."],
                "next_actions": ["Informe um CNPJ válido para enriquecer empresa/sócios."],
                "cnpj_profile": {},
            }

        profile = lookup_cnpj_profile(cnpj)
        if not profile.get("success"):
            return {
                "tool": "cnpj_enrich",
                "ok": False,
                "answer": "",
                "metrics_used": [],
                "internal_sources": [],
                "warnings": [str(profile.get("error") or "Falha ao consultar CNPJ.")],
                "next_actions": ["Verificar endpoint de CNPJ e tentar novamente."],
                "cnpj_profile": profile,
            }

        payload = profile.get("payload") if isinstance(profile.get("payload"), dict) else {}
        company_name = (
            payload.get("razao_social")
            or payload.get("nome")
            or payload.get("nome_fantasia")
            or "empresa"
        )
        partners = payload.get("socios") or payload.get("qsa") or []
        partners_count = len(partners) if isinstance(partners, list) else 0

        return {
            "tool": "cnpj_enrich",
            "ok": True,
            "answer": (
                f"Enriquecimento CNPJ concluído para {company_name}. "
                f"Sócios identificados: {partners_count}."
            ),
            "metrics_used": [
                {
                    "key": "cnpj.partners_count",
                    "value": partners_count,
                    "source": str(profile.get("provider") or "cnpj_lookup"),
                    "period": "current",
                }
            ],
            "internal_sources": [
                {
                    "name": "cnpj_lookup",
                    "ids": [cnpj],
                }
            ],
            "warnings": [],
            "next_actions": [
                "Validar decisores e canais oficiais antes de avançar na proposta.",
            ],
            "cnpj_profile": profile,
        }


class DocsRagTool:
    def run(self, *, company, query: str, limit: int = 6) -> dict[str, Any]:
        chunks = search_ai_document_chunks(company, query, limit=limit)
        if not chunks:
            return {
                "tool": "docs_rag",
                "ok": False,
                "answer": "",
                "metrics_used": [],
                "internal_sources": [],
                "warnings": ["Nenhum trecho interno encontrado para a pergunta."],
                "next_actions": ["Indexar documentos relevantes para ampliar base interna."],
                "cnpj_profile": {},
            }

        internal_sources = []
        excerpts: list[str] = []
        for chunk in chunks:
            internal_sources.append(
                {
                    "name": "ai_document_chunk",
                    "document_name": chunk.document_name,
                    "source_type": chunk.source_type,
                    "source_id": chunk.source_id,
                    "chunk_order": chunk.chunk_order,
                    "ids": [chunk.id],
                }
            )
            text = (chunk.chunk_text or "").strip()
            if text:
                excerpts.append(text[:220])

        answer = (
            f"Baseado em {len(chunks)} trechos internos, os documentos apontam: "
            f"{' '.join(excerpts[:2])}"
        )
        return {
            "tool": "docs_rag",
            "ok": True,
            "answer": answer.strip(),
            "metrics_used": [
                {
                    "key": "docs.chunks_used",
                    "value": len(chunks),
                    "source": "operational.ai_document_chunk",
                    "period": "current",
                }
            ],
            "internal_sources": internal_sources,
            "warnings": [],
            "next_actions": [
                "Revisar cláusulas citadas e validar impacto na proposta/apólice.",
            ],
            "cnpj_profile": {},
        }


class WebResearchTool:
    def __init__(self, provider: WebSearchProvider | None = None):
        self.provider = provider or DefaultWebSearchProvider()

    def run(self, *, query: str) -> dict[str, Any]:
        try:
            results = self.provider.search(query, limit=5)
        except WebResearchUnavailable as exc:
            return {
                "tool": "web_research",
                "ok": False,
                "answer": "Web research indisponível no ambiente atual.",
                "metrics_used": [],
                "internal_sources": [],
                "web_sources": [],
                "warnings": [str(exc)],
                "next_actions": ["Configurar SERPER_API_KEY para habilitar pesquisa web."],
                "cnpj_profile": {},
            }

        if not results:
            return {
                "tool": "web_research",
                "ok": False,
                "answer": "Nenhuma fonte pública encontrada para esta consulta.",
                "metrics_used": [],
                "internal_sources": [],
                "web_sources": [],
                "warnings": ["Consulta web retornou vazio."],
                "next_actions": ["Refinar termos de mercado/produto para nova busca."],
                "cnpj_profile": {},
            }

        lead_titles = [row["title"] for row in results if row.get("title")]
        answer = "Pesquisa de mercado concluída. Principais fontes: " + "; ".join(lead_titles[:3])
        return {
            "tool": "web_research",
            "ok": True,
            "answer": answer,
            "metrics_used": [
                {
                    "key": "web.sources_count",
                    "value": len(results),
                    "source": "web_search",
                    "period": "current",
                }
            ],
            "internal_sources": [],
            "web_sources": results,
            "warnings": [],
            "next_actions": [
                "Comparar achados públicos com indicadores internos do tenant.",
            ],
            "cnpj_profile": {},
        }


class AiAssistantService:
    def __init__(self, *, web_provider: WebSearchProvider | None = None):
        self.web_tool = WebResearchTool(provider=web_provider)
        self.internal_analytics_tool = InternalAnalyticsTool()
        self.system_health_tool = SystemHealthTool()
        self.cnpj_tool = CnpjEnrichTool()
        self.docs_tool = DocsRagTool()

    @staticmethod
    def _message_intent(intents: list[str]) -> str:
        non_mixed = [intent for intent in intents if intent != AiMessage.Intent.MIXED]
        if len(non_mixed) > 1:
            return AiMessage.Intent.MIXED
        return non_mixed[0] if non_mixed else AiMessage.Intent.MIXED

    @staticmethod
    def _build_title(prompt: str) -> str:
        normalized = re.sub(r"\s+", " ", str(prompt or "").strip())
        if len(normalized) <= 120:
            return normalized
        return f"{normalized[:117]}..."

    @staticmethod
    def _extract_correlation_id(context: dict[str, Any], request=None) -> str:
        correlation_id = str(context.get("correlation_id") or "").strip()
        if correlation_id:
            return correlation_id

        if request is not None:
            header_id = str(request.headers.get("X-Request-ID", "")).strip()
            if header_id:
                return header_id
        return str(uuid4())

    @staticmethod
    def _dedupe_rows(rows: list[dict[str, Any]], *, key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
        seen = set()
        deduped: list[dict[str, Any]] = []
        for row in rows:
            key = tuple(str(row.get(field, "")) for field in key_fields)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped

    @staticmethod
    def _sanitize_web_sources(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sanitized: list[dict[str, Any]] = []
        for row in rows:
            url = str(row.get("url") or "").strip()
            if not url:
                continue
            title = str(row.get("title") or "").strip()
            snippet = str(row.get("snippet") or "").strip()
            if len(title) > 220:
                title = f"{title[:217]}..."
            if len(snippet) > 280:
                snippet = f"{snippet[:277]}..."
            sanitized.append(
                {
                    "url": url,
                    "title": title,
                    "snippet": snippet,
                }
            )
        return sanitized

    @staticmethod
    def _sanitize_internal_sources(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sanitized: list[dict[str, Any]] = []
        for row in rows:
            entry = {
                "name": str(row.get("name") or "").strip(),
                "document_name": str(row.get("document_name") or "").strip(),
                "source_type": str(row.get("source_type") or "").strip(),
                "source_id": str(row.get("source_id") or "").strip(),
                "chunk_order": row.get("chunk_order"),
                "ids": row.get("ids") if isinstance(row.get("ids"), list) else [],
            }
            if not any(
                (
                    entry["name"],
                    entry["document_name"],
                    entry["source_type"],
                    entry["source_id"],
                    entry["ids"],
                )
            ):
                continue
            sanitized.append(entry)
        return sanitized

    @staticmethod
    def _sanitize_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sanitized: list[dict[str, Any]] = []
        for row in rows:
            key = str(row.get("key") or "").strip()
            if not key:
                continue
            value = row.get("value")
            if isinstance(value, str) and len(value) > 120:
                value = f"{value[:117]}..."
            sanitized.append(
                {
                    "key": key,
                    "value": value,
                    "source": str(row.get("source") or "").strip(),
                    "period": str(row.get("period") or "").strip(),
                }
            )
        return sanitized

    def _resolve_conversation(self, *, company, user, prompt: str, context: dict[str, Any]):
        conversation_id = context.get("conversation_id")
        conversation = None
        if conversation_id:
            conversation = AiConversation.all_objects.filter(
                company=company,
                id=conversation_id,
            ).first()

        if conversation is None:
            conversation = AiConversation.objects.create(
                company=company,
                created_by=user if getattr(user, "is_authenticated", False) else None,
                title=self._build_title(prompt),
                status=AiConversation.Status.OPEN,
            )
        return conversation

    def consult(
        self,
        *,
        company,
        user,
        prompt: str,
        context: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        context_payload = context if isinstance(context, dict) else {}
        prompt_text = str(prompt or "").strip()
        if not prompt_text:
            raise ValueError("prompt is required")

        gate = CapabilityGate.build(company, user)
        ai_caps = gate.ai_capabilities()
        correlation_id = self._extract_correlation_id(context_payload, request=request)

        intents = classify_ai_intents(
            prompt_text,
            include_market_research=bool(context_payload.get("include_market_research", True)),
            include_cnpj_enrichment=bool(context_payload.get("include_cnpj_enrichment", True)),
            explicit_cnpj=str(context_payload.get("cnpj") or ""),
        )
        message_intent = self._message_intent(intents)

        conversation = self._resolve_conversation(
            company=company,
            user=user,
            prompt=prompt_text,
            context=context_payload,
        )
        user_message = AiMessage.objects.create(
            company=company,
            conversation=conversation,
            role=AiMessage.Role.USER,
            content=prompt_text,
            intent=message_intent,
            metadata={
                "correlation_id": correlation_id,
                "intents": intents,
                "context": {
                    "focus": context_payload.get("focus", ""),
                    "include_market_research": bool(
                        context_payload.get("include_market_research", True)
                    ),
                    "include_cnpj_enrichment": bool(
                        context_payload.get("include_cnpj_enrichment", True)
                    ),
                    "include_financial_context": bool(
                        context_payload.get("include_financial_context", True)
                    ),
                    "include_commercial_context": bool(
                        context_payload.get("include_commercial_context", True)
                    ),
                },
            },
        )

        tool_results: list[dict[str, Any]] = []
        warnings: list[str] = []

        run_internal = (
            AiMessage.Intent.INTERNAL_ANALYTICS in intents or AiMessage.Intent.MIXED in intents
        )
        run_health = (
            AiMessage.Intent.SYSTEM_HEALTH in intents or AiMessage.Intent.MIXED in intents
        )
        run_cnpj = (
            AiMessage.Intent.CNPJ_ENRICH in intents or AiMessage.Intent.MIXED in intents
        )
        run_docs = AiMessage.Intent.DOCS_RAG in intents or AiMessage.Intent.MIXED in intents
        run_web = (
            AiMessage.Intent.WEB_MARKET in intents and bool(context_payload.get("include_market_research", True))
        )

        if run_internal:
            include_financial_context = bool(context_payload.get("include_financial_context", True))
            include_commercial_context = bool(context_payload.get("include_commercial_context", True))

            if include_financial_context and not ai_caps.get("tenant.ai.finance", False):
                include_financial_context = False
                warnings.append("Sem permissão para contexto financeiro (tenant.ai.finance).")
            if include_commercial_context and not ai_caps.get("tenant.ai.crm", False):
                include_commercial_context = False
                warnings.append("Sem permissão para contexto CRM (tenant.ai.crm).")

            if include_financial_context or include_commercial_context:
                tool_results.append(
                    self.internal_analytics_tool.run(
                        company=company,
                        include_financial_context=include_financial_context,
                        include_commercial_context=include_commercial_context,
                    )
                )

        if run_health:
            if ai_caps.get("tenant.ai.admin", False):
                tool_results.append(self.system_health_tool.run(company=company))
            else:
                warnings.append("Sem permissão para consultar saúde do sistema (tenant.ai.admin).")

        if run_cnpj:
            if ai_caps.get("tenant.ai.crm", False):
                tool_results.append(
                    self.cnpj_tool.run(
                        prompt=prompt_text,
                        explicit_cnpj=str(context_payload.get("cnpj") or ""),
                    )
                )
            else:
                warnings.append("Sem permissão para enriquecimento de CNPJ (tenant.ai.crm).")

        if run_docs:
            if ai_caps.get("tenant.ai.docs", False):
                tool_results.append(
                    self.docs_tool.run(
                        company=company,
                        query=prompt_text,
                        limit=int(context_payload.get("docs_limit") or 6),
                    )
                )
            else:
                warnings.append("Sem permissão para consultar documentos internos (tenant.ai.docs).")

        if run_web:
            if ai_caps.get("tenant.ai.web", False):
                tool_results.append(self.web_tool.run(query=prompt_text))
            else:
                warnings.append("Sem permissão para pesquisa web (tenant.ai.web).")

        answer_blocks = [row.get("answer", "").strip() for row in tool_results if row.get("answer")]
        if not answer_blocks:
            answer_blocks.append(
                "Não foi possível montar análise detalhada com os dados/permissões disponíveis."
            )
        if warnings:
            answer_blocks.append("Restrições aplicadas: " + " | ".join(warnings))

        metrics_used: list[dict[str, Any]] = []
        internal_sources: list[dict[str, Any]] = []
        web_sources: list[dict[str, Any]] = []
        next_actions: list[str] = []
        cnpj_profile: dict[str, Any] = {}

        for result in tool_results:
            metrics_used.extend(result.get("metrics_used") or [])
            internal_sources.extend(result.get("internal_sources") or [])
            web_sources.extend(result.get("web_sources") or [])
            next_actions.extend(result.get("next_actions") or [])
            warnings.extend(result.get("warnings") or [])
            profile = result.get("cnpj_profile")
            if isinstance(profile, dict) and profile:
                cnpj_profile = profile

        internal_sources = self._dedupe_rows(
            internal_sources,
            key_fields=("name", "document_name", "source_type", "source_id", "chunk_order"),
        )
        web_sources = self._dedupe_rows(web_sources, key_fields=("url",))
        internal_sources = self._sanitize_internal_sources(internal_sources)
        web_sources = self._sanitize_web_sources(web_sources)
        metrics_used = self._sanitize_metrics(metrics_used)
        next_actions = [item for item in dict.fromkeys([str(item).strip() for item in next_actions]) if item]
        warnings = [item for item in dict.fromkeys([str(item).strip() for item in warnings]) if item]

        answer_text = "\n".join(answer_blocks).strip()
        assistant_payload = {
            "summary": answer_text[:1500],
            "risks": warnings[:6],
            "opportunities": [],
            "next_actions": next_actions[:8],
            "qualification_score": None,
            "provider": "ai_assistant_orchestrator",
            "generated_at": timezone.now().isoformat(),
            "focus": str(context_payload.get("focus") or ""),
            "intent": message_intent,
            "intents": intents,
            "sources": {
                "web_sources": web_sources,
                "internal_sources": internal_sources,
                "metrics_used": metrics_used,
            },
            "correlation_id": correlation_id,
            "capabilities": ai_caps,
        }

        assistant_message = AiMessage.objects.create(
            company=company,
            conversation=conversation,
            role=AiMessage.Role.ASSISTANT,
            content=answer_text,
            intent=message_intent,
            metadata=assistant_payload,
        )

        append_ledger_entry(
            scope="TENANT",
            company=company,
            actor=user,
            action="CREATE",
            resource_label=AiConversation._meta.label,
            resource_pk=str(conversation.pk),
            request=request,
            event_type="AiAssistant.CONSULT",
            data_after={
                "conversation_id": conversation.id,
                "user_message_id": user_message.id,
                "assistant_message_id": assistant_message.id,
                "intent": message_intent,
                "intents": intents,
            },
            metadata={
                "tenant_resource_key": "ai_assistant",
                "correlation_id": correlation_id,
                "intent": message_intent,
                "intents": intents,
                "sources_summary": {
                    "web_sources_count": len(web_sources),
                    "internal_sources_count": len(internal_sources),
                    "metrics_count": len(metrics_used),
                },
                "capabilities": ai_caps,
                "tool_trace": [
                    {
                        "tool": row.get("tool"),
                        "ok": bool(row.get("ok")),
                    }
                    for row in tool_results
                ],
            },
        )

        return {
            "conversation_id": conversation.id,
            "user_message_id": user_message.id,
            "assistant_message_id": assistant_message.id,
            "intent": message_intent,
            "intents": intents,
            "correlation_id": correlation_id,
            "assistant": assistant_payload,
            "sources": assistant_payload["sources"],
            "next_actions": next_actions[:8],
            "warnings": warnings[:8],
            "capabilities": ai_caps,
            "cnpj_profile": cnpj_profile,
        }
