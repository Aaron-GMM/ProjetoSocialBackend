from unittest.mock import AsyncMock, MagicMock

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
    mock_lookup_address.assert_awaited_once_with(LATITUDE, LONGITUDE)


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
    mock_reverse_geocode.assert_awaited_once_with(LATITUDE, LONGITUDE)

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
