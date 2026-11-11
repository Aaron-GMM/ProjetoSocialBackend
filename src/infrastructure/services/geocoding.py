"""Geocodificação reversa (coordenadas → endereço legível) via Nominatim (OSM).

O serviço é tolerante a falhas (graceful degradation): qualquer problema com o
provedor externo (timeout, falha de rede, rate limit, resposta inválida ou
coordenada sem endereço) resulta em ``None`` e é apenas registrado em log,
nunca propagado para quem chamou. Assim o cadastro de placas não depende da
disponibilidade do provedor.
"""

import logging
import re
from collections.abc import Iterable
from typing import Any

import httpx

from src.application.schemas.placa_schema import EnderecoSugerido
from src.core.config import settings

logger = logging.getLogger(__name__)

# Ordem de prioridade dos campos de `address` retornados pelo Nominatim.
LOGRADOURO_KEYS = ("road", "pedestrian")
# `village`/`hamlet` são o último recurso: em zonas rurais o provedor não tem
# bairro, apenas o distrito/localidade (ex.: "São João dos Queirozes").
BAIRRO_KEYS = ("suburb", "neighbourhood", "city_district", "village", "hamlet")
# No Brasil, `municipality` é o município (admin_level 8). Ele vem antes de
# `village`, que em áreas rurais é o nome do distrito (ex.: distritos de
# Quixadá retornam village="São João dos Queirozes", municipality="Quixadá").
CIDADE_KEYS = ("municipality", "city", "town", "village")
ESTADO_KEYS = ("state",)

_CEP_DIGITS = 8


def _first_value(
    address: dict[str, Any], keys: Iterable[str], exclude: str | None = None
) -> str | None:
    """Retorna o primeiro valor não vazio de ``address`` seguindo ``keys``.

    Valores iguais a ``exclude`` (sem diferenciar maiúsculas) são ignorados.
    """
    excluded = exclude.casefold() if exclude else None
    for key in keys:
        value = address.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        if excluded is not None and value.strip().casefold() == excluded:
            continue
        return value.strip()
    return None


def normalize_cep(raw: str | None) -> str | None:
    """Normaliza um CEP para ``00000-000``; retorna ``None`` se for inválido."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) != _CEP_DIGITS:
        return None
    return f"{digits[:5]}-{digits[5:]}"


def parse_nominatim_response(payload: Any) -> EnderecoSugerido | None:
    """Converte o JSON do Nominatim em ``EnderecoSugerido``.

    Retorna ``None`` quando o payload não contém nenhum campo de endereço útil
    (ex.: ``{"error": "Unable to geocode"}`` para pontos no oceano).
    """
    if not isinstance(payload, dict):
        return None
    address = payload.get("address")
    if not isinstance(address, dict):
        return None

    cidade = _first_value(address, CIDADE_KEYS)
    endereco = EnderecoSugerido(
        logradouro=_first_value(address, LOGRADOURO_KEYS),
        # Em cidades sem bairros mapeados o provedor costuma repetir o nome da
        # cidade em `city_district`; isso não é um bairro.
        bairro=_first_value(address, BAIRRO_KEYS, exclude=cidade),
        cep=normalize_cep(address.get("postcode")),
        cidade=cidade,
        estado=_first_value(address, ESTADO_KEYS),
    )
    if not endereco.model_dump(exclude_none=True):
        return None
    return endereco


class GeocodingUnavailableError(Exception):
    """O provedor de geocodificação não respondeu de forma utilizável."""


async def lookup_address(latitude: float, longitude: float) -> EnderecoSugerido | None:
    """Consulta o provedor de geocodificação reversa para as coordenadas.

    Returns:
        O endereço encontrado ou ``None`` se não houver endereço para o ponto.

    Raises:
        GeocodingUnavailableError: timeout, falha de rede, status HTTP de erro
            (inclusive 429 por rate limit) ou resposta não-JSON do provedor.
    """
    params = {
        "lat": latitude,
        "lon": longitude,
        "format": "jsonv2",
        "addressdetails": 1,
        "zoom": 18,
    }
    headers = {
        "User-Agent": settings.GEOCODING_USER_AGENT,
        "Accept-Language": "pt-BR",
    }

    try:
        async with httpx.AsyncClient(
            timeout=settings.GEOCODING_TIMEOUT, headers=headers
        ) as client:
            response = await client.get(settings.GEOCODING_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException as exc:
        logger.warning(
            "Timeout na geocodificação reversa (lat=%s, lon=%s, timeout=%ss)",
            latitude,
            longitude,
            settings.GEOCODING_TIMEOUT,
        )
        raise GeocodingUnavailableError("Timeout no provedor") from exc
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Provedor de geocodificação respondeu HTTP %s (lat=%s, lon=%s)",
            exc.response.status_code,
            latitude,
            longitude,
        )
        raise GeocodingUnavailableError(
            f"Provedor respondeu HTTP {exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning(
            "Falha de rede na geocodificação reversa (lat=%s, lon=%s): %r",
            latitude,
            longitude,
            exc,
        )
        raise GeocodingUnavailableError("Falha de rede") from exc
    except ValueError as exc:
        logger.warning(
            "Resposta não-JSON do provedor de geocodificação (lat=%s, lon=%s)",
            latitude,
            longitude,
        )
        raise GeocodingUnavailableError("Resposta inválida do provedor") from exc

    endereco = parse_nominatim_response(payload)
    if endereco is None:
        logger.info(
            "Nenhum endereço encontrado para as coordenadas (lat=%s, lon=%s)",
            latitude,
            longitude,
        )
    return endereco


async def reverse_geocode(latitude: float, longitude: float) -> EnderecoSugerido | None:
    """Versão tolerante a falhas de :func:`lookup_address`.

    Nunca levanta exceção: se o provedor estiver indisponível ou não houver
    endereço para o ponto, retorna ``None`` silenciosamente.
    """
    try:
        return await lookup_address(latitude, longitude)
    except GeocodingUnavailableError:
        return None
