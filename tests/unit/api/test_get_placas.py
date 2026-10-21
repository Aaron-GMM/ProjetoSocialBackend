from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.api.routes import placas as placas_route
from src.core.security import create_access_token
from src.domain.enums.placa_enums import EstadoConservacao, TipoEvento
from src.domain.enums.role import Role
from src.domain.models.eventos_placa import EventosPlaca
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions.user import create_user
from src.main import app

QUIXADA_POLIGONO = (
    "POLYGON((-39.15 -5.05, -38.90 -5.05, -38.90 -4.85, -39.15 -4.85, -39.15 -5.05))"
)

FORM_DATA = {
    "codigo_contran": "R-1",
    "afastamento": "1.5",
    "tipo_pelicula": "TIPO_I",
    "tipo_substrato": "ACO",
    "tipo_suporte": "POSTE_ACO",
    "latitude": "-4.9714",
    "longitude": "-39.0154",
    "logradouro": "Rua Basílio Pinto",
    "bairro": "Centro",
    "cep": "63900-000",
    "referencia": "Em frente à praça",
    "estado_conservacao": "BOM",
    "estado_pelicula": "REGULAR",
    "observacao": "Placa nova",
}

FAKE_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
)


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


@pytest.fixture(autouse=True)
def mock_minio(monkeypatch):
    mock_service = MagicMock()
    mock_service.ensure_bucket_exists_async = AsyncMock(return_value=None)
    mock_service.upload_file_async = AsyncMock(
        return_value="placas/2026/10/20/placas_123_abcd1234.jpg"
    )
    mock_service.get_presigned_url_async = AsyncMock(
        return_value=(
            "http://localhost:9000/cacaplaca-images/placas/2026/10/20/"
            "placas_123_abcd1234.jpg?X-Amz-Signature=123"
        )
    )
    mock_service.delete_file_async = AsyncMock(return_value=None)
    monkeypatch.setattr(placas_route, "minio_service", mock_service)
    return mock_service


@pytest_asyncio.fixture
async def quixada(db_session):
    await db_session.execute(
        text(
            "INSERT INTO municipios (id, nome, codigo_ibge, poligono) VALUES "
            "(gen_random_uuid(), 'Quixadá', '2311306', "
            "ST_GeomFromText(:poligono, 4326))"
        ),
        {"poligono": QUIXADA_POLIGONO},
    )
    await db_session.commit()


@pytest_asyncio.fixture
async def agent_user(db_session):
    user = User(
        nome="Agente Santos",
        email="agente@test.com",
        password_hash="hashedpass",
        role=Role.AGENTE,
    )
    return await create_user(db_session, user)


@pytest.fixture
def agent_headers(agent_user):
    token = create_access_token({"sub": str(agent_user.id)})
    return {"Authorization": f"Bearer {token}"}


async def cadastrar_placa(
    client: AsyncClient,
    headers: dict,
    latitude: float = -4.9714,
    longitude: float = -39.0154,
    bairro: str = "Centro",
    logradouro: str = "Rua Basílio Pinto",
    estado_conservacao: str = "BOM",
) -> dict:
    data = {
        **FORM_DATA,
        "latitude": str(latitude),
        "longitude": str(longitude),
        "bairro": bairro,
        "logradouro": logradouro,
        "estado_conservacao": estado_conservacao,
    }
    files = {"foto": ("placa.jpg", FAKE_JPEG_BYTES, "image/jpeg")}
    response = await client.post("/placas/", data=data, files=files, headers=headers)
    assert response.status_code == 201, response.json()
    return response.json()


@pytest.mark.asyncio
async def test_get_placas_success_e_ultimo_evento(
    client: AsyncClient, db_session, quixada, agent_user, agent_headers, mock_minio
):
    agent_id = agent_user.id
    placa = await cadastrar_placa(client, agent_headers)

    # Insere um evento mais recente (VISTORIA) com foto para validar o Join Lateral
    vistoria = EventosPlaca(
        placa_id=UUID(placa["id"]),
        created_by=agent_id,
        tipo_evento=TipoEvento.VISTORIA,
        estado_conservacao=EstadoConservacao.RUIM,
        foto_url="placas/2026/10/20/vistoria_999.jpg",
        observacao="Placa sofreu avaria",
        timestamp=datetime.now(UTC) + timedelta(minutes=5),
    )
    db_session.add(vistoria)
    await db_session.commit()

    response = await client.get("/placas/")

    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["id"] == placa["id"]
    assert item["ultimo_evento"]["tipo_evento"] == "VISTORIA"
    assert item["ultimo_evento"]["estado_conservacao"] == "RUIM"
    assert item["ultimo_evento"]["foto_url"].startswith(
        "http://localhost:9000/cacaplaca-images/"
    )
    assert item["latitude"] == pytest.approx(-4.9714, rel=1e-3)
    assert item["longitude"] == pytest.approx(-39.0154, rel=1e-3)


@pytest.mark.asyncio
async def test_get_placas_filtro_bounding_box(
    client: AsyncClient, quixada, agent_headers
):
    dentro = await cadastrar_placa(client, agent_headers)
    fora = await cadastrar_placa(
        client,
        agent_headers,
        latitude=-4.9900,
        longitude=-39.0500,
        bairro="Distrito",
        logradouro="Estrada Velha",
    )

    params = {
        "min_lng": -39.020,
        "min_lat": -4.980,
        "max_lng": -39.010,
        "max_lat": -4.960,
    }
    response = await client.get("/placas/", params=params)

    assert response.status_code == 200
    ids = [i["id"] for i in response.json()["items"]]
    assert dentro["id"] in ids
    assert fora["id"] not in ids


@pytest.mark.asyncio
async def test_get_placas_bounding_box_parcial_ignorada(
    client: AsyncClient, quixada, agent_headers
):
    await cadastrar_placa(client, agent_headers)

    # Só parte dos parâmetros da bbox não deve ativar o filtro espacial
    response = await client.get("/placas/", params={"min_lng": -39.0})

    assert response.status_code == 200
    assert response.json()["total"] == 1


@pytest.mark.asyncio
async def test_get_placas_filtros_textuais_ilike(
    client: AsyncClient, quixada, agent_headers
):
    placa = await cadastrar_placa(
        client,
        agent_headers,
        bairro="Campo Novo",
        logradouro="Avenida Plácido Castelo",
    )

    res_bairro = await client.get("/placas/", params={"bairro": "campo"})
    assert res_bairro.status_code == 200
    assert [i["id"] for i in res_bairro.json()["items"]] == [placa["id"]]

    res_logradouro = await client.get("/placas/", params={"logradouro": "plácido"})
    assert res_logradouro.status_code == 200
    assert [i["id"] for i in res_logradouro.json()["items"]] == [placa["id"]]


@pytest.mark.asyncio
async def test_get_placas_filtro_estado_conservacao(
    client: AsyncClient, quixada, agent_headers
):
    await cadastrar_placa(client, agent_headers, estado_conservacao="BOM")
    ruim = await cadastrar_placa(
        client,
        agent_headers,
        latitude=-4.9720,
        longitude=-39.0160,
        estado_conservacao="RUIM",
    )

    response = await client.get("/placas/", params={"estado_conservacao": "RUIM"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == ruim["id"]


@pytest.mark.asyncio
async def test_get_placas_paginacao(client: AsyncClient, quixada, agent_headers):
    await cadastrar_placa(client, agent_headers, logradouro="Rua 1")
    await cadastrar_placa(
        client,
        agent_headers,
        latitude=-4.9720,
        longitude=-39.0160,
        logradouro="Rua 2",
    )

    res_p1 = await client.get("/placas/", params={"page": 1, "page_size": 1})
    res_p2 = await client.get("/placas/", params={"page": 2, "page_size": 1})

    assert res_p1.status_code == 200
    assert res_p2.status_code == 200
    items_p1 = res_p1.json()["items"]
    items_p2 = res_p2.json()["items"]
    assert len(items_p1) == 1
    assert len(items_p2) == 1
    assert items_p1[0]["id"] != items_p2[0]["id"]
    assert res_p1.json()["total"] == 2


@pytest.mark.asyncio
async def test_get_placas_nenhum_resultado(client: AsyncClient):
    response = await client.get(
        "/placas/", params={"bairro": "Bairro Inexistente Jamais Visto"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
