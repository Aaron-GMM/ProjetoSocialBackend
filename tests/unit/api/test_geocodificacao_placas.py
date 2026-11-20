from unittest.mock import ANY, AsyncMock, MagicMock

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from src.api.routes import placas as placas_route
from src.application.schemas.placa_schema import EnderecoSugerido
from src.core.security import create_access_token
from src.domain.enums.role import Role
from src.domain.models.endereco import Enderecos
from src.domain.models.placa import Placa
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions.endereco_referencia import (
    inserir_divisoes,
    inserir_enderecos,
)
from src.infrastructure.database.functions.user import create_user
from src.infrastructure.services import geocoding
from src.infrastructure.services.geocoding import GeocodingUnavailableError
from src.main import app

ENDPOINT = "/placas/endereco-por-coordenadas"
LATITUDE = -4.9714
LONGITUDE = -39.0154

FORM_DATA_SEM_ENDERECO = {
    "codigo_contran": "R-1",
    "latitude": str(LATITUDE),
    "longitude": str(LONGITUDE),
    "estado_conservacao": "BOM",
}

ENDERECO_SUGERIDO = EnderecoSugerido(
    logradouro="Rua Basílio Pinto",
    bairro="Centro",
    cep="63900-000",
    cidade="Quixadá",
    estado="Ceará",
)

FAKE_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
)


def make_photo_files():
    return {"foto": ("placa.jpg", FAKE_JPEG_BYTES, "image/jpeg")}


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def mock_minio(monkeypatch):
    mock_service = MagicMock()
    mock_service.ensure_bucket_exists_async = AsyncMock(return_value=None)
    mock_service.upload_file_async = AsyncMock(
        return_value="placas/2026/11/10/placas_123_abcd1234.jpg"
    )
    mock_service.get_public_url = MagicMock(
        return_value="http://localhost:9000/cacaplaca-images/placas/x.jpg"
    )
    mock_service.delete_file_async = AsyncMock(return_value=None)
    monkeypatch.setattr(placas_route, "minio_service", mock_service)
    return mock_service


@pytest_asyncio.fixture
async def agent_user(db_session):
    user = User(
        nome="Agente Geo",
        email="agente.geo@test.com",
        password_hash="hashedpass",
        role=Role.AGENTE,
    )
    return await create_user(db_session, user)


@pytest.fixture
def agent_headers(agent_user):
    token = create_access_token({"sub": str(agent_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_reverse_geocode(monkeypatch):
    mock = AsyncMock(return_value=ENDERECO_SUGERIDO)
    monkeypatch.setattr(placas_route, "reverse_geocode", mock)
    return mock


@pytest.fixture
def mock_lookup_address(monkeypatch):
    mock = AsyncMock(return_value=ENDERECO_SUGERIDO)
    monkeypatch.setattr(placas_route, "lookup_address", mock)
    return mock


async def get_endereco_salvo(db_session) -> Enderecos | None:
    return (await db_session.exec(select(Enderecos))).one_or_none()


async def post_placa(client, headers, **form_overrides):
    data = {**FORM_DATA_SEM_ENDERECO, **form_overrides}
    return await client.post(
        "/placas/", data=data, files=make_photo_files(), headers=headers
    )


# ---------------------------------------------------------------------------
# GET /placas/endereco-por-coordenadas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_endereco_por_coordenadas_success(
    client, agent_headers, mock_lookup_address
):
    response = await client.get(
        ENDPOINT,
        params={"latitude": LATITUDE, "longitude": LONGITUDE},
        headers=agent_headers,
    )

    assert response.status_code == 200, response.json()
    assert response.json() == {
        "logradouro": "Rua Basílio Pinto",
        "bairro": "Centro",
        "cep": "63900-000",
        "cidade": "Quixadá",
        "estado": "Ceará",
    }
    mock_lookup_address.assert_awaited_once_with(LATITUDE, LONGITUDE, ANY)


@pytest.mark.asyncio
async def test_endereco_por_coordenadas_partial_returns_nulls(
    client, agent_headers, mock_lookup_address
):
    mock_lookup_address.return_value = EnderecoSugerido(
        bairro="Centro", cidade="Quixadá", estado="Ceará"
    )

    response = await client.get(
        ENDPOINT,
        params={"latitude": LATITUDE, "longitude": LONGITUDE},
        headers=agent_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["logradouro"] is None
    assert data["cep"] is None
    assert data["bairro"] == "Centro"


@pytest.mark.asyncio
async def test_endereco_por_coordenadas_not_found(
    client, agent_headers, mock_lookup_address
):
    mock_lookup_address.return_value = None

    response = await client.get(
        ENDPOINT, params={"latitude": 0, "longitude": 0}, headers=agent_headers
    )

    assert response.status_code == 404
    assert "Nenhum endereço encontrado" in response.json()["detail"]


@pytest.mark.asyncio
async def test_endereco_por_coordenadas_provider_unavailable(
    client, agent_headers, mock_lookup_address
):
    mock_lookup_address.side_effect = GeocodingUnavailableError("timeout")

    response = await client.get(
        ENDPOINT,
        params={"latitude": LATITUDE, "longitude": LONGITUDE},
        headers=agent_headers,
    )

    assert response.status_code == 503
    assert "indisponível" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"latitude": -90.1, "longitude": 0},
        {"latitude": 90.1, "longitude": 0},
        {"latitude": 0, "longitude": -180.1},
        {"latitude": 0, "longitude": 180.1},
        {"latitude": "abc", "longitude": 0},
        {"latitude": 0},
        {"longitude": 0},
    ],
)
async def test_endereco_por_coordenadas_invalid_params(
    client, agent_headers, mock_lookup_address, params
):
    response = await client.get(ENDPOINT, params=params, headers=agent_headers)

    assert response.status_code == 422
    mock_lookup_address.assert_not_awaited()


@pytest.mark.asyncio
async def test_endereco_por_coordenadas_unauthenticated(client, mock_lookup_address):
    response = await client.get(
        ENDPOINT, params={"latitude": LATITUDE, "longitude": LONGITUDE}
    )

    assert response.status_code == 401
    mock_lookup_address.assert_not_awaited()


# ---------------------------------------------------------------------------
# Auto-preenchimento no POST /placas/
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_placa_autofills_endereco_from_coordinates(
    client, db_session, agent_headers, mock_minio, mock_reverse_geocode
):
    response = await post_placa(client, agent_headers)

    assert response.status_code == 201, response.json()
    endereco = response.json()["endereco"]
    assert endereco["logradouro"] == "Rua Basílio Pinto"
    assert endereco["bairro"] == "Centro"
    assert endereco["cep"] == "63900-000"
    assert endereco["referencia"] is None
    mock_reverse_geocode.assert_awaited_once_with(LATITUDE, LONGITUDE, ANY)

    salvo = await get_endereco_salvo(db_session)
    assert salvo is not None
    assert (salvo.logradouro, salvo.bairro, salvo.cep) == (
        "Rua Basílio Pinto",
        "Centro",
        "63900-000",
    )


@pytest.mark.asyncio
async def test_create_placa_with_full_endereco_skips_geocoding(
    client, db_session, agent_headers, mock_minio, mock_reverse_geocode
):
    response = await post_placa(
        client,
        agent_headers,
        logradouro="Av. Plácido Castelo",
        bairro="Planalto Universitário",
        cep="63902-580",
    )

    assert response.status_code == 201, response.json()
    endereco = response.json()["endereco"]
    assert endereco["logradouro"] == "Av. Plácido Castelo"
    assert endereco["bairro"] == "Planalto Universitário"
    assert endereco["cep"] == "63902-580"
    mock_reverse_geocode.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_placa_manual_fields_take_priority_over_geocoding(
    client, db_session, agent_headers, mock_minio, mock_reverse_geocode
):
    response = await post_placa(
        client,
        agent_headers,
        bairro="Bairro Informado",
        referencia="Em frente à praça",
    )

    assert response.status_code == 201, response.json()
    endereco = response.json()["endereco"]
    assert endereco["bairro"] == "Bairro Informado"
    assert endereco["logradouro"] == "Rua Basílio Pinto"
    assert endereco["cep"] == "63900-000"
    assert endereco["referencia"] == "Em frente à praça"
    mock_reverse_geocode.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_placa_partial_geocoding_fills_only_available_fields(
    client, db_session, agent_headers, mock_minio, mock_reverse_geocode
):
    mock_reverse_geocode.return_value = EnderecoSugerido(
        bairro="Centro", cidade="Quixadá"
    )

    response = await post_placa(client, agent_headers)

    assert response.status_code == 201, response.json()
    endereco = response.json()["endereco"]
    assert endereco["bairro"] == "Centro"
    assert endereco["logradouro"] == ""
    assert endereco["cep"] == ""


@pytest.mark.asyncio
async def test_create_placa_geocoding_failure_does_not_abort_creation(
    client, db_session, agent_headers, mock_minio, mock_reverse_geocode
):
    # reverse_geocode retorna None em qualquer falha do provedor
    mock_reverse_geocode.return_value = None

    response = await post_placa(client, agent_headers)

    assert response.status_code == 201, response.json()
    assert response.json()["endereco"] is None
    assert await get_endereco_salvo(db_session) is None
    assert len((await db_session.exec(select(Placa))).all()) == 1
    mock_minio.upload_file_async.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_placa_geocoding_failure_keeps_manual_fields(
    client, db_session, agent_headers, mock_minio, mock_reverse_geocode
):
    mock_reverse_geocode.return_value = None

    response = await post_placa(client, agent_headers, logradouro="Rua Informada")

    assert response.status_code == 201, response.json()
    endereco = response.json()["endereco"]
    assert endereco["logradouro"] == "Rua Informada"
    assert endereco["bairro"] == ""
    assert endereco["cep"] == ""


@pytest.mark.asyncio
async def test_create_placa_real_provider_timeout_does_not_abort_creation(
    client, db_session, agent_headers, mock_minio, monkeypatch
):
    """Integra rota + serviço real com o httpx simulando timeout do provedor."""
    real_async_client = httpx.AsyncClient

    def handler(request):
        raise httpx.ReadTimeout("timeout", request=request)

    def factory(*args, **kwargs):
        return real_async_client(
            *args, transport=httpx.MockTransport(handler), **kwargs
        )

    monkeypatch.setattr(geocoding.httpx, "AsyncClient", factory)
    monkeypatch.setattr(placas_route, "reverse_geocode", geocoding.reverse_geocode)

    response = await post_placa(client, agent_headers)

    assert response.status_code == 201, response.json()
    assert response.json()["endereco"] is None


# ---------------------------------------------------------------------------
# Integração com a base local (CNEFE/IBGE), sem mocks na geocodificação
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def base_local(db_session):
    """Endereços de referência ao redor da coordenada de teste."""
    linhas = [
        (1, 0.00005, "Rua Rui Barbosa", "Centro", "63900-207"),
        (2, 0.00010, "Rua Basílio Pinto", "Centro", "63900-211"),
        (3, 0.00015, "Rua Rui Barbosa", "Centro", "63900-205"),
        (4, 0.00020, "Rua Rui Barbosa", "Combate", "63900-205"),
    ]
    conn = await db_session.connection()
    await inserir_enderecos(
        conn,
        [
            {
                "cod_unico_endereco": cod,
                "codigo_municipio": "2311306",
                "codigo_distrito": "231130605",
                "logradouro": logradouro,
                "bairro": bairro,
                "cep": cep,
                "cidade": "Quixadá",
                "estado": "Ceará",
                "lat": LATITUDE + dlat,
                "lng": LONGITUDE,
            }
            for cod, dlat, logradouro, bairro, cep in linhas
        ],
    )
    await db_session.commit()


def provedor_externo_fora_do_ar(monkeypatch):
    real_async_client = httpx.AsyncClient

    def handler(request):
        raise httpx.ConnectError("sem rede", request=request)

    def factory(*args, **kwargs):
        return real_async_client(
            *args, transport=httpx.MockTransport(handler), **kwargs
        )

    monkeypatch.setattr(geocoding.httpx, "AsyncClient", factory)


@pytest.mark.asyncio
async def test_endereco_por_coordenadas_usa_base_local(
    client, agent_headers, base_local
):
    response = await client.get(
        ENDPOINT,
        params={"latitude": LATITUDE, "longitude": LONGITUDE},
        headers=agent_headers,
    )

    assert response.status_code == 200, response.json()
    assert response.json() == {
        "logradouro": "Rua Rui Barbosa",
        "bairro": "Centro",
        "cep": "63900-207",
        "cidade": "Quixadá",
        "estado": "Ceará",
    }


@pytest.mark.asyncio
async def test_endereco_por_coordenadas_base_local_independe_do_provedor(
    client, agent_headers, base_local, monkeypatch
):
    provedor_externo_fora_do_ar(monkeypatch)

    response = await client.get(
        ENDPOINT,
        params={"latitude": LATITUDE, "longitude": LONGITUDE},
        headers=agent_headers,
    )

    assert response.status_code == 200
    assert response.json()["bairro"] == "Centro"


@pytest.mark.asyncio
async def test_endereco_por_coordenadas_fora_da_base_e_provedor_fora_retorna_503(
    client, agent_headers, monkeypatch
):
    provedor_externo_fora_do_ar(monkeypatch)

    response = await client.get(
        ENDPOINT,
        params={"latitude": LATITUDE, "longitude": LONGITUDE},
        headers=agent_headers,
    )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_endereco_por_coordenadas_fora_da_base_sem_endereco_retorna_404(
    client, agent_headers
):
    # sem base local e o provedor (bloqueado no conftest) não encontra endereço
    response = await client.get(
        ENDPOINT,
        params={"latitude": LATITUDE, "longitude": LONGITUDE},
        headers=agent_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_placa_preenche_endereco_pela_base_local(
    client, db_session, agent_headers, mock_minio, base_local, monkeypatch
):
    provedor_externo_fora_do_ar(monkeypatch)

    response = await post_placa(client, agent_headers, referencia="Perto da praça")

    assert response.status_code == 201, response.json()
    endereco = response.json()["endereco"]
    assert endereco["logradouro"] == "Rua Rui Barbosa"
    assert endereco["bairro"] == "Centro"
    assert endereco["cep"] == "63900-207"
    assert endereco["referencia"] == "Perto da praça"
    salvo = await get_endereco_salvo(db_session)
    assert (salvo.logradouro, salvo.bairro, salvo.cep) == (
        "Rua Rui Barbosa",
        "Centro",
        "63900-207",
    )


@pytest.mark.asyncio
async def test_create_placa_base_local_respeita_campos_do_agente(
    client, agent_headers, mock_minio, base_local
):
    response = await post_placa(client, agent_headers, bairro="Bairro Digitado")

    assert response.status_code == 201, response.json()
    endereco = response.json()["endereco"]
    assert endereco["bairro"] == "Bairro Digitado"
    assert endereco["logradouro"] == "Rua Rui Barbosa"
    assert endereco["cep"] == "63900-207"


@pytest.mark.asyncio
async def test_endereco_por_coordenadas_faixa_intermediaria_descarta_bairro_do_osm(
    client, agent_headers, db_session, monkeypatch
):
    # endereço de referência a ~300 m; Nominatim devolve um bairro "chutado"
    conn = await db_session.connection()
    await inserir_enderecos(
        conn,
        [
            {
                "cod_unico_endereco": 99,
                "codigo_municipio": "2311306",
                "codigo_distrito": "231130605",
                "logradouro": "Rua Distante",
                "bairro": "Centro",
                "cep": "63900-207",
                "cidade": "Quixadá",
                "estado": "Ceará",
                "lat": LATITUDE + 0.0027,
                "lng": LONGITUDE,
            }
        ],
    )
    await db_session.commit()
    real_async_client = httpx.AsyncClient
    payload = {
        "address": {
            "road": "Rua Rui Barbosa",
            "suburb": "Sitiá Oeste",
            "town": "Quixadá",
            "postcode": "63900-209",
        }
    }

    def factory(*args, **kwargs):
        return real_async_client(
            *args,
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)),
            **kwargs,
        )

    monkeypatch.setattr(geocoding.httpx, "AsyncClient", factory)

    response = await client.get(
        ENDPOINT,
        params={"latitude": LATITUDE, "longitude": LONGITUDE},
        headers=agent_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "logradouro": "Rua Rui Barbosa",
        "bairro": "Centro",
        "cep": None,
        "cidade": "Quixadá",
        "estado": "Ceará",
    }


# ---------------------------------------------------------------------------
# Padronização do que o agente digita (grafia oficial nos relatórios)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def base_padronizacao(db_session, base_local):
    """Bairro oficial "Centro" ao redor do ponto de teste."""
    conn = await db_session.connection()
    await inserir_divisoes(
        conn,
        [
            {
                "codigo": "2311306008",
                "tipo": "bairro",
                "nome": "Centro",
                "codigo_municipio": "2311306",
                "sede": False,
                "geojson": (
                    '{"type":"Polygon","coordinates":[[[-39.02,-4.972],'
                    "[-39.01,-4.972],[-39.01,-4.970],[-39.02,-4.970],"
                    "[-39.02,-4.972]]]}"
                ),
            }
        ],
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_create_placa_grava_rua_e_bairro_digitados_na_grafia_oficial(
    client, db_session, agent_headers, mock_minio, base_padronizacao
):
    response = await post_placa(
        client,
        agent_headers,
        logradouro="rua rui barbosa",
        bairro="CENTRO",
        cep="63900-000",
    )

    assert response.status_code == 201, response.json()
    endereco = response.json()["endereco"]
    assert endereco["logradouro"] == "Rua Rui Barbosa"
    assert endereco["bairro"] == "Centro"
    salvo = await get_endereco_salvo(db_session)
    assert (salvo.logradouro, salvo.bairro) == ("Rua Rui Barbosa", "Centro")


@pytest.mark.asyncio
async def test_create_placa_mantem_texto_sem_correspondencia_oficial(
    client, agent_headers, mock_minio, base_padronizacao
):
    response = await post_placa(
        client,
        agent_headers,
        logradouro="Rua Nova do Loteamento",
        bairro="Loteamento Recente",
        cep="63900-000",
    )

    assert response.status_code == 201, response.json()
    endereco = response.json()["endereco"]
    assert endereco["logradouro"] == "Rua Nova do Loteamento"
    assert endereco["bairro"] == "Loteamento Recente"


@pytest.mark.asyncio
async def test_update_placa_grava_rua_e_bairro_na_grafia_oficial(
    client, agent_headers, mock_minio, base_padronizacao
):
    created = await post_placa(client, agent_headers)
    placa_id = created.json()["id"]

    response = await client.patch(
        f"/placas/{placa_id}",
        data={"logradouro": "RUA RUI BARBOSA", "bairro": "centro"},
        headers=agent_headers,
    )

    assert response.status_code == 200, response.json()
    endereco = response.json()["endereco"]
    assert endereco["logradouro"] == "Rua Rui Barbosa"
    assert endereco["bairro"] == "Centro"
