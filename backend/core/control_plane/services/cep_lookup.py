import json
import logging
from urllib.error import URLError
from urllib.request import urlopen

from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_SECONDS = 3600


class CepLookupError(Exception):
    pass


def sanitize_cep(raw_cep: str) -> str:
    cep = "".join(ch for ch in (raw_cep or "") if ch.isdigit())
    if len(cep) != 8:
        raise CepLookupError("CEP must contain exactly 8 digits.")
    return cep


def lookup_cep(raw_cep: str) -> dict:
    cep = sanitize_cep(raw_cep)
    cache_key = f"control_panel:cep:{cep}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    endpoint = f"https://viacep.com.br/ws/{cep}/json/"
    try:
        with urlopen(endpoint, timeout=5) as response:  # nosec B310
            payload = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, URLError, OSError, ValueError) as exc:
        logger.warning("CEP lookup failed for %s: %s", cep, exc.__class__.__name__)
        raise CepLookupError("Unable to fetch CEP data right now.") from exc

    if payload.get("erro"):
        raise CepLookupError("CEP not found.")

    result = {
        "cep": cep,
        "logradouro": payload.get("logradouro", "") or "",
        "bairro": payload.get("bairro", "") or "",
        "cidade": payload.get("localidade", "") or "",
        "uf": payload.get("uf", "") or "",
    }
    cache.set(cache_key, result, _CACHE_SECONDS)

    # Keep logs minimal: do not log full address details.
    logger.info("CEP lookup success for %s", cep)
    return result
