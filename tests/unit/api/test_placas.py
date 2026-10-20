from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlmodel import func, select

from src.core.security import create_access_token
from src.domain.enums.placa_enums import CodigoContran, EstadoConservacao, TipoEvento
from src.domain.enums.role import Role
from src.domain.models.endereco import Enderecos
from src.domain.models.eventos_placa import EventosPlaca
from src.domain.models.placa import Placa
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions import placa as placa_functions
from src.infrastructure.database.functions.user import create_user
from src.main import app

QUIXADA_POLIGONO = (
    "POLYGON((-39.15 -5.05, -38.90 -5.05, -38.90 -4.85, -39.15 -4.85, -39.15 -5.05))"
)

PAYLOAD = {
    "codigo_contran": "R-1",
    "afastamento": 1.5,
    "tipo_pelicula": "TIPO_I",
    "tipo_substrato": "ACO",
    "tipo_suporte": "POSTE_ACO",
    "latitude": -4.9714,
    "longitude": -39.0154,
    "endereco": {
        "logradouro": "Rua Basílio Pinto",
        "bairro": "Centro",
        "cep": "63900-000",
        "referencia": "Em frente à praça",
    },
    "estado_conservacao": "BOM",
    "estado_pelicula": "REGULAR",
    "observacao": "Placa nova",
}


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


async def count_rows(db_session, model) -> int:
    result = await db_session.exec(select(func.count()).select_from(model))
    return result.one()


@pytest.mark.asyncio
async def test_create_placa_success(
    client: AsyncClient, db_session, quixada, agent_user, agent_headers
):
    agent_id = agent_user.id
    response = await client.post("/placas/", json=PAYLOAD, headers=agent_headers)

    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["codigo_contran"] == "R-1"
    assert data["latitude"] == PAYLOAD["latitude"]
    assert data["longitude"] == PAYLOAD["longitude"]
    assert data["endereco"]["bairro"] == "Centro"
    assert data["ultimo_evento"]["tipo_evento"] == "CRIACAO"
    assert data["ultimo_evento"]["estado_conservacao"] == "BOM"
    assert data["ultimo_evento"]["created_by"] == agent_id
    assert data["ultimo_evento"]["foto_url"] is None

    result = await db_session.execute(
        text("SELECT ST_X(location), ST_Y(location) FROM placas WHERE id = :id"),
        {"id": data["id"]},
    )
    assert result.one() == (PAYLOAD["longitude"], PAYLOAD["latitude"])
    assert await count_rows(db_session, Enderecos) == 1
    assert await count_rows(db_session, EventosPlaca) == 1


@pytest.mark.asyncio
async def test_create_placa_outside_quixada(
    client: AsyncClient, db_session, quixada, agent_headers
):
    payload = {**PAYLOAD, "latitude": -3.732, "longitude": -38.526}
    response = await client.post("/placas/", json=payload, headers=agent_headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "As coordenadas da placa estão fora de Quixadá!"
    assert await count_rows(db_session, Placa) == 0


@pytest.mark.asyncio
async def test_create_placa_without_municipio(
    client: AsyncClient, db_session, agent_headers
):
    response = await client.post("/placas/", json=PAYLOAD, headers=agent_headers)

    assert response.status_code == 500
    assert await count_rows(db_session, Placa) == 0


@pytest.mark.asyncio
async def test_create_placa_unauthenticated(client: AsyncClient, quixada):
    response = await client.post("/placas/", json=PAYLOAD)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_placa_invalid_payload(
    client: AsyncClient, quixada, agent_headers
):
    payload = {**PAYLOAD, "codigo_contran": "XYZ", "latitude": 200}
    response = await client.post("/placas/", json=payload, headers=agent_headers)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_placa_rollback_on_commit_error():
    mock_db = MagicMock()
    mock_db.commit = AsyncMock(side_effect=RuntimeError("Falha ao persistir"))
    mock_db.rollback = AsyncMock()

    placa = Placa(codigo_contran=CodigoContran.R_1, location="POINT(-39.01 -4.97)")
    endereco = Enderecos(
        placa_id=placa.id,
        logradouro="Rua Basílio Pinto",
        bairro="Centro",
        cep="63900-000",
    )
    evento = EventosPlaca(
        placa_id=placa.id,
        created_by=1,
        tipo_evento=TipoEvento.CRIACAO,
        estado_conservacao=EstadoConservacao.BOM,
    )

    with pytest.raises(RuntimeError, match="Falha ao persistir"):
        await placa_functions.create_placa(mock_db, placa, endereco, evento)

    mock_db.rollback.assert_awaited_once()
