import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


def sanitize_cnpj(raw_value: str) -> str:
    digits = re.sub(r"\D", "", raw_value or "")
    return digits if len(digits) == 14 else ""


def lookup_cnpj_profile(cnpj: str) -> dict[str, Any]:
    normalized_cnpj = sanitize_cnpj(cnpj)
    if not normalized_cnpj:
        return {
            "success": False,
            "provider": "cnpj_lookup",
            "error": "Invalid CNPJ.",
            "cnpj": "",
        }

    endpoint_template = getattr(settings, "CNPJ_LOOKUP_ENDPOINT", "").strip()
    if not endpoint_template:
        return {
            "success": False,
            "provider": "cnpj_lookup",
            "error": "CNPJ lookup endpoint is not configured.",
            "cnpj": normalized_cnpj,
        }

    endpoint = (
        endpoint_template.format(cnpj=normalized_cnpj)
        if "{cnpj}" in endpoint_template
        else f"{endpoint_template.rstrip('/')}/{normalized_cnpj}"
    )

    timeout_seconds = float(getattr(settings, "CNPJ_LOOKUP_TIMEOUT_SECONDS", 8.0))
    request = Request(
        endpoint,
        headers={
            "Accept": "application/json",
            "User-Agent": "mks-commercial-intelligence/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return {
                "success": True,
                "provider": "cnpj_lookup",
                "cnpj": normalized_cnpj,
                "payload": payload,
            }
    except HTTPError as exc:
        return {
            "success": False,
            "provider": "cnpj_lookup",
            "error": f"CNPJ service returned HTTP {exc.code}.",
            "cnpj": normalized_cnpj,
        }
    except URLError as exc:
        return {
            "success": False,
            "provider": "cnpj_lookup",
            "error": f"CNPJ service unreachable: {exc.reason}",
            "cnpj": normalized_cnpj,
        }
    except (ValueError, json.JSONDecodeError):
        return {
            "success": False,
            "provider": "cnpj_lookup",
            "error": "CNPJ service returned a non-JSON response.",
            "cnpj": normalized_cnpj,
        }


def _extract_json_object(text: str) -> dict[str, Any]:
    if not text:
        return {}
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            value = json.loads(stripped)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        value = json.loads(stripped[start : end + 1])
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _normalize_insight_payload(payload: dict[str, Any]) -> dict[str, Any]:
    summary = str(payload.get("summary") or "").strip()
    risks = payload.get("risks") or []
    opportunities = payload.get("opportunities") or []
    next_actions = payload.get("next_actions") or []
    qualification_score = payload.get("qualification_score")

    if not isinstance(risks, list):
        risks = []
    if not isinstance(opportunities, list):
        opportunities = []
    if not isinstance(next_actions, list):
        next_actions = []

    normalized_score = None
    if isinstance(qualification_score, (int, float)):
        normalized_score = max(0, min(100, int(round(qualification_score))))

    return {
        "summary": summary,
        "risks": [str(item).strip() for item in risks if str(item).strip()],
        "opportunities": [
            str(item).strip() for item in opportunities if str(item).strip()
        ],
        "next_actions": [
            str(item).strip() for item in next_actions if str(item).strip()
        ],
        "qualification_score": normalized_score,
    }


def _heuristic_insights(entity_type: str, payload: dict[str, Any], focus: str) -> dict[str, Any]:
    non_empty_fields = sum(
        1
        for value in payload.values()
        if value not in (None, "", [], {}, ())
    )
    completeness_score = min(100, int((non_empty_fields / max(len(payload), 1)) * 100))

    summary_parts = [
        f"Análise automática para {entity_type.lower()} com {non_empty_fields} campos preenchidos.",
    ]
    if focus:
        summary_parts.append(f"Foco solicitado: {focus}.")
    summary = " ".join(summary_parts)

    risks = []
    if not payload.get("email"):
        risks.append("Contato sem email principal para follow-up.")
    if not payload.get("phone") and not payload.get("whatsapp"):
        risks.append("Contato sem telefone/WhatsApp para abordagem comercial.")
    if not payload.get("cnpj"):
        risks.append("Sem CNPJ informado para validação cadastral.")
    if not payload.get("estimated_budget") and entity_type == "LEAD":
        risks.append("Lead sem orçamento estimado informado.")

    opportunities = []
    if payload.get("cnpj"):
        opportunities.append("Usar CNPJ para validar atividade econômica e porte.")
    if payload.get("linkedin_url"):
        opportunities.append("Mapear decisores via LinkedIn para acelerar abordagem.")
    if payload.get("products_of_interest"):
        opportunities.append("Personalizar proposta com base no interesse declarado.")
    if payload.get("industry"):
        opportunities.append("Usar benchmark setorial no argumento de venda.")

    next_actions = [
        "Validar dados de contato e confirmar decisor principal.",
        "Agendar próxima interação com objetivo comercial claro.",
        "Registrar objeções e plano de contorno na atividade.",
    ]

    return {
        "summary": summary,
        "risks": risks,
        "opportunities": opportunities,
        "next_actions": next_actions,
        "qualification_score": completeness_score,
    }


def _vertex_ai_insights(entity_type: str, payload: dict[str, Any], focus: str) -> dict[str, Any]:
    from vertexai import init
    from vertexai.generative_models import GenerationConfig, GenerativeModel

    project_id = getattr(settings, "VERTEX_AI_PROJECT_ID", "").strip()
    location = getattr(settings, "VERTEX_AI_LOCATION", "us-central1").strip()
    model_name = getattr(settings, "VERTEX_AI_MODEL", "gemini-1.5-pro-002").strip()
    temperature = float(getattr(settings, "VERTEX_AI_TEMPERATURE", 0.2))

    if not project_id:
        raise RuntimeError("VERTEX_AI_PROJECT_ID is required when VERTEX_AI_ENABLED=true.")

    init(project=project_id, location=location)
    model = GenerativeModel(model_name)

    prompt = (
        "Você é um analista comercial B2B. "
        "Retorne apenas JSON válido com as chaves: "
        "summary(string), risks(array de strings), opportunities(array de strings), "
        "next_actions(array de strings), qualification_score(int 0-100).\n"
        f"Tipo de entidade: {entity_type}\n"
        f"Foco adicional: {focus or 'geral'}\n"
        "Dados:\n"
        f"{json.dumps(payload, ensure_ascii=False, default=str)}"
    )

    response = model.generate_content(
        prompt,
        generation_config=GenerationConfig(
            temperature=temperature,
            top_p=0.8,
            max_output_tokens=1024,
        ),
    )
    text = getattr(response, "text", "") or ""
    parsed_payload = _extract_json_object(text)
    if not parsed_payload:
        raise RuntimeError("Vertex AI returned a non-JSON response.")
    return _normalize_insight_payload(parsed_payload)


def generate_commercial_insights(
    *,
    entity_type: str,
    payload: dict[str, Any],
    focus: str = "",
    cnpj_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    use_vertex = bool(getattr(settings, "VERTEX_AI_ENABLED", False))
    provider = "heuristic"
    errors = []

    if use_vertex:
        try:
            insights = _vertex_ai_insights(entity_type, payload, focus)
            provider = "vertex_ai"
        except Exception as exc:  # pragma: no cover - external provider fallback
            errors.append(str(exc))
            insights = _heuristic_insights(entity_type, payload, focus)
            provider = "heuristic_fallback"
    else:
        insights = _heuristic_insights(entity_type, payload, focus)

    normalized = _normalize_insight_payload(insights)
    normalized.update(
        {
            "provider": provider,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "focus": focus,
            "cnpj_profile": cnpj_profile or None,
        }
    )
    if errors:
        normalized["provider_errors"] = errors
    return normalized


def apply_cnpj_profile_to_lead(lead, cnpj_profile: dict[str, Any]) -> list[str]:
    payload = cnpj_profile.get("payload", {}) if isinstance(cnpj_profile, dict) else {}
    if not isinstance(payload, dict):
        return []

    updated_fields = []

    lead_cnpj = sanitize_cnpj(cnpj_profile.get("cnpj", ""))
    if lead_cnpj and not lead.cnpj:
        lead.cnpj = lead_cnpj
        updated_fields.append("cnpj")

    if not lead.company_name:
        lead.company_name = (
            payload.get("razao_social")
            or payload.get("nome_fantasia")
            or payload.get("nome")
            or ""
        )
        if lead.company_name:
            updated_fields.append("company_name")

    if payload.get("qsa"):
        # Many providers do not expose website directly. Keep social research hints in notes.
        qsa_names = ", ".join(
            member.get("nome_socio", "")
            for member in payload.get("qsa", [])
            if isinstance(member, dict) and member.get("nome_socio")
        )
        if qsa_names:
            note_line = f"Sócios identificados: {qsa_names}"
            lead.notes = (f"{lead.notes}\n{note_line}" if lead.notes else note_line).strip()
            updated_fields.append("notes")

    if updated_fields:
        lead.save(update_fields=tuple(sorted(set(updated_fields + ["updated_at"]))))
    return updated_fields


def apply_cnpj_profile_to_customer(customer, cnpj_profile: dict[str, Any]) -> list[str]:
    payload = cnpj_profile.get("payload", {}) if isinstance(cnpj_profile, dict) else {}
    if not isinstance(payload, dict):
        return []

    updated_fields = []

    customer_cnpj = sanitize_cnpj(cnpj_profile.get("cnpj", ""))
    if customer_cnpj and not customer.cnpj:
        customer.cnpj = customer_cnpj
        updated_fields.append("cnpj")

    if not customer.legal_name and payload.get("razao_social"):
        customer.legal_name = payload["razao_social"]
        updated_fields.append("legal_name")
    if not customer.trade_name and payload.get("nome_fantasia"):
        customer.trade_name = payload["nome_fantasia"]
        updated_fields.append("trade_name")
    if not customer.industry:
        customer.industry = payload.get("descricao_situacao_cadastral", "")
        if customer.industry:
            updated_fields.append("industry")
    if not customer.city:
        customer.city = payload.get("municipio", "")
        if customer.city:
            updated_fields.append("city")
    if not customer.state:
        customer.state = payload.get("uf", "")
        if customer.state:
            updated_fields.append("state")

    if updated_fields:
        customer.save(update_fields=tuple(sorted(set(updated_fields + ["updated_at"]))))
    return updated_fields
