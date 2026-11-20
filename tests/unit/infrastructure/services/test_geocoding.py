import json

import httpx
import pytest

from src.application.schemas.placa_schema import EnderecoSugerido
from src.core.config import settings
from src.infrastructure.database.functions.endereco_referencia import (
    inserir_divisoes,
    inserir_enderecos,
)
from src.infrastructure.services import geocoding

LATITUDE = -4.9714
LONGITUDE = -39.0154

NOMINATIM_FULL_RESPONSE = {
    "place_id": 123,
    "lat": "-4.9714",
    "lon": "-39.0154",
    "display_name": "Rua Basílio Pinto, Centro, Quixadá, Ceará, 63900-000, Brasil",
    "address": {
        "road": "Rua Basílio Pinto",
        "suburb": "Centro",
        "city": "Quixadá",
        "state": "Ceará",
        "postcode": "63900-000",
        "country": "Brasil",
        "country_code": "br",
    },
}


def mock_async_client(monkeypatch, handler):
    """
    Substitui httpx.AsyncClient no serviço por um cliente cujo transporte é
    simulado por ``handler``. Retorna um dict com os kwargs usados na criação
    do cliente e a última requisição enviada.
    """
    real_async_client = httpx.AsyncClient
    captured: dict = {}

    def recording_handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return handler(request)

    def factory(*args, **kwargs):
        captured["client_kwargs"] = kwargs
        return real_async_client(
            *args, transport=httpx.MockTransport(recording_handler), **kwargs
        )

    monkeypatch.setattr(geocoding.httpx, "AsyncClient", factory)
    return captured


def json_handler(payload, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return handler


def raising_handler(exc: Exception):
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return handler


# ---------------------------------------------------------------------------
# Sucesso
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reverse_geocode_success_maps_all_fields(monkeypatch):
    mock_async_client(monkeypatch, json_handler(NOMINATIM_FULL_RESPONSE))

    result = await geocoding.reverse_geocode(LATITUDE, LONGITUDE)

    assert result == EnderecoSugerido(
        logradouro="Rua Basílio Pinto",
        bairro="Centro",
        cep="63900-000",
        cidade="Quixadá",
        estado="Ceará",
    )


@pytest.mark.asyncio
async def test_reverse_geocode_sends_expected_request(monkeypatch):
    captured = mock_async_client(monkeypatch, json_handler(NOMINATIM_FULL_RESPONSE))

    await geocoding.reverse_geocode(LATITUDE, LONGITUDE)

    request = captured["request"]
    assert str(request.url).startswith(settings.GEOCODING_URL)
    assert request.url.params["lat"] == str(LATITUDE)
    assert request.url.params["lon"] == str(LONGITUDE)
    assert request.url.params["format"] == "jsonv2"
    assert request.url.params["addressdetails"] == "1"
    assert request.headers["User-Agent"] == settings.GEOCODING_USER_AGENT
    assert request.headers["Accept-Language"] == "pt-BR"
    assert captured["client_kwargs"]["timeout"] == settings.GEOCODING_TIMEOUT


@pytest.mark.asyncio
async def test_reverse_geocode_uses_fallback_keys(monkeypatch):
    payload = {
        "address": {
            "pedestrian": "Calçadão da Praça",
            "neighbourhood": "Campo Velho",
            "town": "Quixadá",
            "state": "Ceará",
            "postcode": "63900000",
        }
    }
    mock_async_client(monkeypatch, json_handler(payload))

    result = await geocoding.reverse_geocode(LATITUDE, LONGITUDE)

    assert result is not None
    assert result.logradouro == "Calçadão da Praça"
    assert result.bairro == "Campo Velho"
    assert result.cidade == "Quixadá"
    assert result.cep == "63900-000"


@pytest.mark.asyncio
async def test_reverse_geocode_prefers_suburb_over_city_district(monkeypatch):
    payload = {
        "address": {
            "road": "Rua A",
            "city_district": "Distrito Sede",
            "suburb": "Centro",
        }
    }
    mock_async_client(monkeypatch, json_handler(payload))

    result = await geocoding.reverse_geocode(LATITUDE, LONGITUDE)

    assert result is not None
    assert result.bairro == "Centro"


@pytest.mark.asyncio
async def test_reverse_geocode_uses_city_district_as_last_resort(monkeypatch):
    payload = {"address": {"road": "Rua A", "city_district": "Distrito Sede"}}
    mock_async_client(monkeypatch, json_handler(payload))

    result = await geocoding.reverse_geocode(LATITUDE, LONGITUDE)

    assert result is not None
    assert result.bairro == "Distrito Sede"


# Payloads reais capturados do Nominatim em 2026-11-10 (campos irrelevantes
# omitidos), usados como regressão do mapeamento.


@pytest.mark.asyncio
async def test_reverse_geocode_rural_district_uses_municipality_as_cidade(
    monkeypatch,
):
    # Distrito de Juatama (zona rural de Quixadá)
    payload = {
        "address": {
            "hamlet": "Daniel de Queiroz",
            "village": "São João dos Queirozes",
            "municipality": "Quixadá",
            "state": "Ceará",
            "country_code": "br",
        }
    }
    mock_async_client(monkeypatch, json_handler(payload))

    result = await geocoding.reverse_geocode(-4.817, -38.979)

    assert result is not None
    assert result.cidade == "Quixadá"
    assert result.bairro == "São João dos Queirozes"


@pytest.mark.asyncio
async def test_reverse_geocode_uses_hamlet_as_bairro_when_no_village(monkeypatch):
    payload = {
        "address": {
            "hamlet": "Sítio Riacho Verde",
            "municipality": "Quixadá",
            "state": "Ceará",
        }
    }
    mock_async_client(monkeypatch, json_handler(payload))

    result = await geocoding.reverse_geocode(-4.85, -39.05)

    assert result is not None
    assert result.bairro == "Sítio Riacho Verde"


@pytest.mark.asyncio
async def test_reverse_geocode_prefers_suburb_over_village(monkeypatch):
    # Lisboa: o provedor envia suburb e village; o bairro urbano tem prioridade
    payload = {
        "address": {
            "road": "Rua da Assunção",
            "suburb": "Santa Maria Maior",
            "village": "Madalena",
            "city": "Lisboa",
        }
    }
    mock_async_client(monkeypatch, json_handler(payload))

    result = await geocoding.reverse_geocode(38.7139, -9.1394)

    assert result is not None
    assert result.bairro == "Santa Maria Maior"


@pytest.mark.asyncio
async def test_reverse_geocode_ignores_village_equal_to_cidade(monkeypatch):
    payload = {"address": {"village": "Ibicuitinga", "municipality": "Ibicuitinga"}}
    mock_async_client(monkeypatch, json_handler(payload))

    result = await geocoding.reverse_geocode(-4.97, -38.64)

    assert result is not None
    assert result.cidade == "Ibicuitinga"
    assert result.bairro is None


@pytest.mark.asyncio
async def test_reverse_geocode_ignores_bairro_equal_to_cidade(monkeypatch):
    # Caapiranga (AM): city_district repete o nome da cidade
    payload = {
        "address": {
            "city_district": "Caapiranga",
            "town": "Caapiranga",
            "state": "Amazonas",
        }
    }
    mock_async_client(monkeypatch, json_handler(payload))

    result = await geocoding.reverse_geocode(-3.0, -62.0)

    assert result is not None
    assert result.cidade == "Caapiranga"
    assert result.bairro is None


@pytest.mark.asyncio
async def test_reverse_geocode_skips_repeated_cidade_and_uses_next_bairro_key(
    monkeypatch,
):
    payload = {
        "address": {
            "road": "Avenida Alfredo Lisboa",
            "neighbourhood": "recife",
            "city_district": "Bairro do Recife",
            "city": "Recife",
        }
    }
    mock_async_client(monkeypatch, json_handler(payload))

    result = await geocoding.reverse_geocode(-8.0631, -34.8711)

    assert result is not None
    assert result.bairro == "Bairro do Recife"


@pytest.mark.asyncio
async def test_reverse_geocode_real_quixada_payload(monkeypatch):
    # Centro de Quixadá: o provedor usa `town` + `municipality`, não `city`
    payload = {
        "category": "highway",
        "address": {
            "road": "Rua Pascoal Crispino",
            "suburb": "Sitiá Oeste",
            "town": "Quixadá",
            "municipality": "Quixadá",
            "state": "Ceará",
            "region": "Região Nordeste",
            "postcode": "63900-209",
            "country": "Brasil",
            "country_code": "br",
        },
    }
    mock_async_client(monkeypatch, json_handler(payload))

    result = await geocoding.reverse_geocode(-4.9702, -39.0156)

    assert result == EnderecoSugerido(
        logradouro="Rua Pascoal Crispino",
        bairro="Sitiá Oeste",
        cep="63900-209",
        cidade="Quixadá",
        estado="Ceará",
    )


# ---------------------------------------------------------------------------
# Endereço parcial / sem endereço
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reverse_geocode_partial_address(monkeypatch):
    payload = {"address": {"suburb": "Centro", "city": "Quixadá", "state": "Ceará"}}
    mock_async_client(monkeypatch, json_handler(payload))

    result = await geocoding.reverse_geocode(LATITUDE, LONGITUDE)

    assert result == EnderecoSugerido(
        logradouro=None,
        bairro="Centro",
        cep=None,
        cidade="Quixadá",
        estado="Ceará",
    )


@pytest.mark.asyncio
async def test_reverse_geocode_discards_invalid_postcode(monkeypatch):
    payload = {"address": {"road": "Rua A", "postcode": "63900"}}
    mock_async_client(monkeypatch, json_handler(payload))

    result = await geocoding.reverse_geocode(LATITUDE, LONGITUDE)

    assert result is not None
    assert result.logradouro == "Rua A"
    assert result.cep is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"error": "Unable to geocode"},
        {"address": {}},
        {"address": {"country": "Brasil", "country_code": "br"}},
        {"address": {"road": "   "}},
        [],
    ],
    ids=["unable-to-geocode", "empty-address", "only-country", "blank", "not-dict"],
)
async def test_reverse_geocode_returns_none_without_useful_address(
    monkeypatch, payload
):
    mock_async_client(monkeypatch, json_handler(payload))

    assert await geocoding.reverse_geocode(LATITUDE, LONGITUDE) is None
    assert await geocoding.lookup_address(LATITUDE, LONGITUDE) is None


# ---------------------------------------------------------------------------
# Falhas do provedor (graceful degradation)
# ---------------------------------------------------------------------------

PROVIDER_FAILURES = [
    pytest.param(raising_handler(httpx.ReadTimeout("timeout")), id="read-timeout"),
    pytest.param(
        raising_handler(httpx.ConnectTimeout("timeout")), id="connect-timeout"
    ),
    pytest.param(raising_handler(httpx.ConnectError("sem rede")), id="sem-rede"),
    pytest.param(
        raising_handler(httpx.RemoteProtocolError("conexão encerrada")),
        id="protocol-error",
    ),
    pytest.param(json_handler({"detail": "erro"}, 500), id="http-500"),
    pytest.param(json_handler({"detail": "erro"}, 503), id="http-503"),
    pytest.param(json_handler({"detail": "rate limit"}, 429), id="http-429"),
    pytest.param(json_handler({"detail": "bloqueado"}, 403), id="http-403"),
    pytest.param(
        lambda request: httpx.Response(200, text="<html>manutenção</html>"),
        id="resposta-nao-json",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", PROVIDER_FAILURES)
async def test_reverse_geocode_returns_none_on_provider_failure(
    monkeypatch, caplog, handler
):
    mock_async_client(monkeypatch, handler)

    with caplog.at_level("WARNING", logger=geocoding.__name__):
        result = await geocoding.reverse_geocode(LATITUDE, LONGITUDE)

    assert result is None
    assert caplog.records, "a falha do provedor deve ser registrada em log"


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", PROVIDER_FAILURES)
async def test_lookup_address_raises_unavailable_on_provider_failure(
    monkeypatch, handler
):
    mock_async_client(monkeypatch, handler)

    with pytest.raises(geocoding.GeocodingUnavailableError):
        await geocoding.lookup_address(LATITUDE, LONGITUDE)


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("63900-000", "63900-000"),
        ("63900000", "63900-000"),
        (" 63.900-000 ", "63900-000"),
        ("63900", None),
        ("639000001", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_cep(raw, expected):
    assert geocoding.normalize_cep(raw) == expected


def test_parse_nominatim_response_ignores_non_string_values():
    payload = {"address": {"road": 123, "pedestrian": "Beco X", "suburb": None}}

    result = geocoding.parse_nominatim_response(payload)

    assert result == EnderecoSugerido(logradouro="Beco X")


# ---------------------------------------------------------------------------
# Base local (CNEFE/IBGE) antes do Nominatim
# ---------------------------------------------------------------------------


async def inserir_referencia(db_session, linhas):
    conn = await db_session.connection()
    await inserir_enderecos(conn, linhas)
    await db_session.commit()


def referencia(cod, dlat, bairro="Centro", logradouro="Rua Rui Barbosa"):
    return {
        "cod_unico_endereco": cod,
        "codigo_municipio": "2311306",
        "codigo_distrito": "231130605",
        "logradouro": logradouro,
        "bairro": bairro,
        "cep": "63900-207",
        "cidade": "Quixadá",
        "estado": "Ceará",
        "lat": LATITUDE + dlat,
        "lng": LONGITUDE,
    }


def nominatim_nao_pode_ser_chamado(monkeypatch):
    def handler(request):
        raise AssertionError("o Nominatim não deveria ser consultado")

    mock_async_client(monkeypatch, handler)


@pytest.mark.asyncio
async def test_lookup_address_usa_base_local_sem_chamar_nominatim(
    monkeypatch, db_session
):
    await inserir_referencia(
        db_session,
        [
            referencia(1, 0.0001),
            referencia(2, 0.0002, bairro="Combate", logradouro="Rua X"),
            referencia(3, 0.0003),
        ],
    )
    nominatim_nao_pode_ser_chamado(monkeypatch)

    result = await geocoding.lookup_address(LATITUDE, LONGITUDE, db_session)

    assert result == EnderecoSugerido(
        logradouro="Rua Rui Barbosa",
        bairro="Centro",
        cep="63900-207",
        cidade="Quixadá",
        estado="Ceará",
    )


@pytest.mark.asyncio
async def test_lookup_address_cai_no_nominatim_fora_do_raio(monkeypatch, db_session):
    await inserir_referencia(db_session, [referencia(1, 0.01)])  # ~1,1 km
    captured = mock_async_client(monkeypatch, json_handler(NOMINATIM_FULL_RESPONSE))

    result = await geocoding.lookup_address(LATITUDE, LONGITUDE, db_session)

    assert "request" in captured
    assert result.logradouro == "Rua Basílio Pinto"


@pytest.mark.asyncio
async def test_lookup_address_cai_no_nominatim_com_base_vazia(monkeypatch, db_session):
    captured = mock_async_client(monkeypatch, json_handler(NOMINATIM_FULL_RESPONSE))

    result = await geocoding.lookup_address(LATITUDE, LONGITUDE, db_session)

    assert "request" in captured
    assert result.bairro == "Centro"


@pytest.mark.asyncio
async def test_reverse_geocode_base_local_funciona_com_provedor_fora(
    monkeypatch, db_session
):
    await inserir_referencia(db_session, [referencia(1, 0.0001)])
    mock_async_client(monkeypatch, raising_handler(httpx.ConnectError("sem rede")))

    result = await geocoding.reverse_geocode(LATITUDE, LONGITUDE, db_session)

    assert result is not None
    assert result.bairro == "Centro"


@pytest.mark.asyncio
async def test_reverse_geocode_fora_da_base_e_provedor_fora_retorna_none(
    monkeypatch, db_session
):
    mock_async_client(monkeypatch, raising_handler(httpx.ConnectError("sem rede")))

    assert await geocoding.reverse_geocode(LATITUDE, LONGITUDE, db_session) is None
    with pytest.raises(geocoding.GeocodingUnavailableError):
        await geocoding.lookup_address(LATITUDE, LONGITUDE, db_session)


@pytest.mark.asyncio
async def test_lookup_local_faixas_de_distancia(monkeypatch, db_session):
    await inserir_referencia(db_session, [referencia(1, 0.0005)])  # ~55 m

    monkeypatch.setattr(settings, "GEOCODING_LOCAL_RAIO_M", 60.0)
    completo = await geocoding.lookup_local(db_session, LATITUDE, LONGITUDE)
    assert completo.completo is True
    assert completo.logradouro == "Rua Rui Barbosa"

    monkeypatch.setattr(settings, "GEOCODING_LOCAL_RAIO_M", 50.0)
    parcial = await geocoding.lookup_local(db_session, LATITUDE, LONGITUDE)
    assert parcial.completo is False
    assert (parcial.logradouro, parcial.cep) == (None, None)
    assert parcial.bairro == "Centro"

    monkeypatch.setattr(settings, "GEOCODING_LOCAL_RAIO_BAIRRO_M", 50.0)
    assert await geocoding.lookup_local(db_session, LATITUDE, LONGITUDE) is None


# Ponto a ~300 m do endereço de referência: só o bairro vem da base local.
DLAT_300M = 0.0027


@pytest.mark.asyncio
async def test_lookup_address_faixa_intermediaria_combina_fontes(
    monkeypatch, db_session
):
    await inserir_referencia(db_session, [referencia(1, DLAT_300M, bairro="Herval")])
    mock_async_client(monkeypatch, json_handler(NOMINATIM_FULL_RESPONSE))

    result = await geocoding.lookup_address(LATITUDE, LONGITUDE, db_session)

    # rua do Nominatim; bairro da base local; CEP do Nominatim descartado
    assert result == EnderecoSugerido(
        logradouro="Rua Basílio Pinto",
        bairro="Herval",
        cep=None,
        cidade="Quixadá",
        estado="Ceará",
    )


@pytest.mark.asyncio
async def test_lookup_address_faixa_intermediaria_sem_endereco_no_provedor(
    monkeypatch, db_session
):
    await inserir_referencia(db_session, [referencia(1, DLAT_300M, bairro="Herval")])
    mock_async_client(monkeypatch, json_handler({"error": "Unable to geocode"}))

    result = await geocoding.lookup_address(LATITUDE, LONGITUDE, db_session)

    assert result.logradouro is None
    assert result.bairro == "Herval"


@pytest.mark.asyncio
async def test_lookup_address_faixa_intermediaria_com_provedor_fora(
    monkeypatch, db_session
):
    await inserir_referencia(db_session, [referencia(1, DLAT_300M, bairro="Herval")])
    mock_async_client(monkeypatch, raising_handler(httpx.ConnectError("sem rede")))

    result = await geocoding.lookup_address(LATITUDE, LONGITUDE, db_session)

    assert result == EnderecoSugerido(bairro="Herval", cidade="Quixadá", estado="Ceará")


# ---------------------------------------------------------------------------
# Limites oficiais (bairros e distritos do IBGE)
# ---------------------------------------------------------------------------


def quadrado(lng_min, lat_min, lng_max, lat_max):
    return json.dumps(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [lng_min, lat_min],
                    [lng_max, lat_min],
                    [lng_max, lat_max],
                    [lng_min, lat_max],
                    [lng_min, lat_min],
                ]
            ],
        }
    )


def divisao(codigo, tipo, nome, geojson, sede=False):
    return {
        "codigo": codigo,
        "tipo": tipo,
        "nome": nome,
        "codigo_municipio": "2311306",
        "sede": sede,
        "geojson": geojson,
    }


# Sede a oeste de LONGITUDE+0.01 e Juatama a leste; bairro oficial "Centro"
# num quadrado de ~110 m ao redor do ponto de teste.
DIVISOES = [
    divisao(
        "231130605",
        "distrito",
        "Quixadá",
        quadrado(-39.1, -5.1, LONGITUDE + 0.01, -4.8),
        sede=True,
    ),
    divisao(
        "231130650",
        "distrito",
        "Juatama",
        quadrado(LONGITUDE + 0.01, -5.1, -38.9, -4.8),
    ),
    divisao(
        "2311306008",
        "bairro",
        "Centro",
        quadrado(
            LONGITUDE - 0.0005, LATITUDE - 0.0005, LONGITUDE + 0.0005, LATITUDE + 0.0005
        ),
    ),
]


async def inserir_divisoes_teste(db_session):
    conn = await db_session.connection()
    await inserir_divisoes(conn, DIVISOES)
    await db_session.commit()


@pytest.mark.asyncio
async def test_bairro_oficial_prevalece_sobre_os_vizinhos(monkeypatch, db_session):
    await inserir_divisoes_teste(db_session)
    # vizinhos registrados com outro bairro (ex.: perto da divisa)
    await inserir_referencia(
        db_session, [referencia(i, 0.0001 * i, bairro="Combate") for i in (1, 2, 3)]
    )
    nominatim_nao_pode_ser_chamado(monkeypatch)

    result = await geocoding.lookup_address(LATITUDE, LONGITUDE, db_session)

    assert result.bairro == "Centro"
    assert result.logradouro == "Rua Rui Barbosa"
    assert result.cep == "63900-207"


@pytest.mark.asyncio
async def test_sede_fora_dos_bairros_usa_bairro_dos_vizinhos(monkeypatch, db_session):
    await inserir_divisoes_teste(db_session)
    lat = LATITUDE + 0.005  # fora do "Centro", ainda na sede
    await inserir_referencia(
        db_session,
        [{**referencia(i, 0.005 + 0.0001 * i, bairro="Cedro")} for i in (1, 2)],
    )
    nominatim_nao_pode_ser_chamado(monkeypatch)

    result = await geocoding.lookup_address(lat, LONGITUDE, db_session)

    assert result.bairro == "Cedro"


@pytest.mark.asyncio
async def test_distrito_rural_sem_endereco_proximo(monkeypatch, db_session):
    await inserir_divisoes_teste(db_session)
    payload = {
        "address": {
            "road": "Estrada Vicinal",
            "village": "Palpite do OSM",
            "town": "Quixadá",
            "postcode": "63900-209",
        }
    }
    mock_async_client(monkeypatch, json_handler(payload))

    result = await geocoding.lookup_address(LATITUDE, LONGITUDE + 0.05, db_session)

    # bairro = distrito oficial; rua do Nominatim; CEP do Nominatim descartado
    assert result == EnderecoSugerido(
        logradouro="Estrada Vicinal",
        bairro="Juatama",
        cep=None,
        cidade="Quixadá",
        estado="Ceará",
    )


@pytest.mark.asyncio
async def test_distrito_rural_com_provedor_fora_ainda_sugere_distrito(
    monkeypatch, db_session
):
    await inserir_divisoes_teste(db_session)
    mock_async_client(monkeypatch, raising_handler(httpx.ConnectError("sem rede")))

    result = await geocoding.lookup_address(LATITUDE, LONGITUDE + 0.05, db_session)

    assert result == EnderecoSugerido(
        bairro="Juatama", cidade="Quixadá", estado="Ceará"
    )
