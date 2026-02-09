import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


def sanitize_cep(raw_value: str) -> str:
    digits = re.sub(r"\D", "", raw_value or "")
    return digits if len(digits) == 8 else ""


def lookup_cep(cep: str) -> dict[str, Any]:
    """Lookup a Brazilian CEP (postal code) and normalize address fields.

    Default provider is ViaCEP, unless CEP_LOOKUP_ENDPOINT is configured.
    """

    normalized_cep = sanitize_cep(cep)
    if not normalized_cep:
        return {
            "success": False,
            "provider": "cep_lookup",
            "error": "Invalid CEP.",
            "cep": "",
        }

    endpoint_template = getattr(settings, "CEP_LOOKUP_ENDPOINT", "").strip()
    if not endpoint_template:
        endpoint_template = "https://viacep.com.br/ws/{cep}/json/"

    endpoint = (
        endpoint_template.format(cep=normalized_cep)
        if "{cep}" in endpoint_template
        else f"{endpoint_template.rstrip('/')}/{normalized_cep}"
    )

    timeout_seconds = float(getattr(settings, "CEP_LOOKUP_TIMEOUT_SECONDS", 6.0))
    request = Request(
        endpoint,
        headers={
            "Accept": "application/json",
            "User-Agent": "mks-address-lookup/1.0",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return {
            "success": False,
            "provider": "cep_lookup",
            "error": f"CEP service returned HTTP {exc.code}.",
            "cep": normalized_cep,
        }
    except URLError as exc:
        return {
            "success": False,
            "provider": "cep_lookup",
            "error": f"CEP service unreachable: {exc.reason}",
            "cep": normalized_cep,
        }
    except (ValueError, json.JSONDecodeError):
        return {
            "success": False,
            "provider": "cep_lookup",
            "error": "CEP service returned a non-JSON response.",
            "cep": normalized_cep,
        }

    if isinstance(payload, dict) and payload.get("erro"):
        return {
            "success": False,
            "provider": "cep_lookup",
            "error": "CEP not found.",
            "cep": normalized_cep,
            "payload": payload,
        }

    if not isinstance(payload, dict):
        return {
            "success": False,
            "provider": "cep_lookup",
            "error": "CEP service returned an unexpected payload.",
            "cep": normalized_cep,
        }

    return {
        "success": True,
        "provider": "cep_lookup",
        "cep": normalized_cep,
        "zip_code": str(payload.get("cep") or normalized_cep).strip(),
        "street": str(payload.get("logradouro") or "").strip(),
        "neighborhood": str(payload.get("bairro") or "").strip(),
        "city": str(payload.get("localidade") or "").strip(),
        "state": str(payload.get("uf") or "").strip(),
        "payload": payload,
    }

