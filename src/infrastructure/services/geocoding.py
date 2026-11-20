"""Geocodificação reversa (coordenadas → endereço legível).

Fonte principal: base local de endereços oficiais de Quixadá (IBGE/Correios,
ver ``src/infrastructure/services/cnefe.py``):
- Bairro: limites oficiais do IBGE (bairro na sede, distrito na zona rural).
- Rua e CEP: endereço do CNEFE mais próximo, se a até
  ``GEOCODING_LOCAL_RAIO_M`` (150 m).

Fallback: Nominatim (OSM).
- Na área coberta pela base, mas sem endereço próximo, só a rua vem do
  Nominatim; o bairro e o CEP dele são descartados (em Quixadá o OSM não tem
  limites de bairro e conhece poucos CEPs genéricos — eram palpites).
- Fora da área coberta, o resultado do Nominatim é usado inteiro.

O serviço é tolerante a falhas (graceful degradation): qualquer problema com o
provedor externo (timeout, falha de rede, rate limit, resposta inválida ou
coordenada sem endereço) resulta em ``None`` em ``reverse_geocode`` e é apenas
registrado em log. Assim o cadastro de placas não depende do provedor.
"""

import logging
import re
from collections.abc import Iterable
from dataclasses import replace
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from src.application.schemas.placa_schema import EnderecoSugerido
from src.core.config import settings
from src.infrastructure.database.functions.endereco_referencia import (
    buscar_divisoes,
    buscar_vizinhos,
)
from src.infrastructure.services.cnefe import (
    MUNICIPIOS,
    EnderecoEscolhido,
    escolher_endereco,
    resolver_bairro,
)

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


async def lookup_local(
    db: AsyncSession, latitude: float, longitude: float
) -> EnderecoEscolhido | None:
    """Sugere o endereço a partir da base local de endereços oficiais.

    - Bairro: limite oficial que contém o ponto (bairro ou, na zona rural,
      distrito); na sede fora dos bairros oficiais, o bairro mais frequente
      entre os vizinhos (ex.: Cedro).
    - Rua e CEP: do endereço do CNEFE mais próximo, se estiver a até
      ``GEOCODING_LOCAL_RAIO_M``; caso contrário o resultado é parcial
      (``completo=False``) e a rua deve vir de outra fonte.

    Retorna ``None`` fora da área coberta (sem divisão oficial que contenha o
    ponto e sem endereço a até ``GEOCODING_LOCAL_RAIO_BAIRRO_M``).
    """
    divisoes = await buscar_divisoes(db, latitude, longitude)
    vizinhos = await buscar_vizinhos(
        db,
        latitude,
        longitude,
        limite=settings.GEOCODING_LOCAL_VIZINHOS,
        raio_m=settings.GEOCODING_LOCAL_RAIO_BAIRRO_M,
    )
    escolhido = escolher_endereco(
        vizinhos, raio_endereco_m=settings.GEOCODING_LOCAL_RAIO_M
    )
    municipio = MUNICIPIOS.get(divisoes.codigo_municipio or "")
    if escolhido is None and municipio is None:
        return None

    bairro = resolver_bairro(divisoes, escolhido.bairro if escolhido else None)
    if escolhido is None:
        return EnderecoEscolhido(
            logradouro=None,
            bairro=bairro,
            cep=None,
            cidade=municipio[0],
            estado=municipio[1],
            completo=False,
        )
    return replace(escolhido, bairro=bairro)


async def lookup_nominatim(
    latitude: float, longitude: float
) -> EnderecoSugerido | None:
    """Consulta o Nominatim (OSM) para as coordenadas.

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


async def lookup_address(
    latitude: float, longitude: float, db: AsyncSession | None = None
) -> EnderecoSugerido | None:
    """Sugere o endereço: base local do CNEFE primeiro, depois o Nominatim.

    Raises:
        GeocodingUnavailableError: a base local não cobre o ponto e o
            Nominatim está indisponível.
    """
    local = await lookup_local(db, latitude, longitude) if db is not None else None
    if local is not None and local.completo:
        return _to_sugerido(local)

    try:
        externo = await lookup_nominatim(latitude, longitude)
    except GeocodingUnavailableError:
        if local is None:
            raise
        # Sem provedor externo, o bairro da base local ainda é útil.
        return _to_sugerido(local)

    if local is None:
        return externo
    # Área coberta pela base local, mas sem endereço próximo (ex.: avenida
    # longa, loteamento novo): a rua vem do Nominatim (geometria da via) e o
    # bairro da base local. O bairro e o CEP do Nominatim são descartados:
    # em Quixadá eles são palpites por proximidade (sem limites de bairro no
    # OSM e poucos CEPs genéricos), justamente o problema que a base resolve.
    return EnderecoSugerido(
        logradouro=externo.logradouro if externo else None,
        bairro=local.bairro,
        cep=None,
        cidade=local.cidade,
        estado=local.estado,
    )


def _to_sugerido(escolhido: EnderecoEscolhido) -> EnderecoSugerido:
    return EnderecoSugerido(
        logradouro=escolhido.logradouro,
        bairro=escolhido.bairro,
        cep=escolhido.cep,
        cidade=escolhido.cidade,
        estado=escolhido.estado,
    )


async def reverse_geocode(
    latitude: float, longitude: float, db: AsyncSession | None = None
) -> EnderecoSugerido | None:
    """Versão tolerante a falhas de :func:`lookup_address`.

    Nunca levanta exceção por falha do provedor externo: se ele estiver
    indisponível ou não houver endereço para o ponto, retorna ``None``.
    """
    try:
        return await lookup_address(latitude, longitude, db)
    except GeocodingUnavailableError:
        return None
