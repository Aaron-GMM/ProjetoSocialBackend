from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from src.api.routes import placas as placas_route
from src.core.security import create_access_token
from src.domain.enums.placa_enums import EstadoConservacao, TipoEvento
from src.domain.enums.role import Role
from src.domain.models.eventos_placa import EventosPlaca
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions import placa as placa_functions
from src.infrastructure.database.functions.user import create_user
from src.main import app

FORM_DATA = {
    "codigo_contran": "R-1",
    "afastamento": "1.5",
    "tipo_suporte": "POSTE_ACO",
    "latitude": "-4.9714",
    "longitude": "-39.0154",
    "logradouro": "Rua Basílio Pinto",
    "bairro": "Centro",
    "cep": "63900-000",
    "estado_conservacao": "BOM",
}

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


@pytest.fixture(autouse=True)
def mock_minio(monkeypatch):
    mock_service = MagicMock()
    mock_service.ensure_bucket_exists_async = AsyncMock(return_value=None)
    mock_service.upload_file_async = AsyncMock(
        return_value="placas/2026/10/20/placas_123.jpg"
    )
    mock_service.get_public_url = MagicMock(
        side_effect=lambda name: f"http://localhost:9000/cacaplaca-images/{name}"
    )
    mock_service.delete_file_async = AsyncMock(return_value=None)
    monkeypatch.setattr(placas_route, "minio_service", mock_service)
    return mock_service


@pytest_asyncio.fixture
async def agent_user(db_session):
    user = User(
        nome="Agente Santos",
        email="agente_delete@test.com",
        password_hash="hashedpass",
        role=Role.AGENTE,
    )
    return await create_user(db_session, user)


@pytest.fixture
def agent_headers(agent_user):
    token = create_access_token({"sub": str(agent_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def created_placa(client, agent_headers):
    response = await client.post(
        "/placas/",
        data=FORM_DATA,
        files=make_photo_files(),
        headers=agent_headers,
    )
    assert response.status_code == 201, response.json()
    return response.json()


# ============================================================================
# Testes [HU-B5]: DELETE /placas/{placa_id}
# ============================================================================


@pytest.mark.asyncio
async def test_delete_placa_success(
    client: AsyncClient, db_session, agent_headers, created_placa
):
    placa_id = created_placa["id"]

    response = await client.delete(f"/placas/{placa_id}", headers=agent_headers)
    assert response.status_code == 204

    # 1. Verifica no banco que o evento DELECAO foi registrado (Append-Only)
    stmt = (
        select(EventosPlaca)
        .where(EventosPlaca.placa_id == UUID(placa_id))
        .order_by(EventosPlaca.timestamp.desc())
    )
    eventos = list((await db_session.exec(stmt)).all())
    assert len(eventos) == 2
    assert eventos[0].tipo_evento == TipoEvento.DELECAO
    assert eventos[0].is_active is True

    # 2. Verifica que a placa não aparece mais na listagem geral
    list_res = await client.get("/placas/", headers=agent_headers)
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 0
    assert list_res.json()["items"] == []

    # 3. Verifica que buscar ou deletar novamente retorna 404
    second_del = await client.delete(f"/placas/{placa_id}", headers=agent_headers)
    assert second_del.status_code == 404


@pytest.mark.asyncio
async def test_delete_placa_not_found(client: AsyncClient, agent_headers):
    response = await client.delete(f"/placas/{uuid4()}", headers=agent_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Placa não encontrada."


@pytest.mark.asyncio
async def test_delete_placa_unauthenticated(client: AsyncClient, created_placa):
    response = await client.delete(f"/placas/{created_placa['id']}")
    assert response.status_code == 401


# ============================================================================
# Testes [HU-B6]: DELETE /placas/{placa_id}/eventos/{evento_id}
# ============================================================================


@pytest.mark.asyncio
async def test_delete_evento_vistoria_success_retorna_ao_evento_anterior(
    client: AsyncClient, db_session, agent_user, agent_headers, created_placa
):
    agent_id = (await db_session.exec(select(User.id))).one()
    placa_id = created_placa["id"]
    criacao_evento_id = created_placa["ultimo_evento"]["id"]

    vistoria_uuid = uuid4()
    vistoria = EventosPlaca(
        id=vistoria_uuid,
        placa_id=UUID(placa_id),
        created_by=agent_id,
        tipo_evento=TipoEvento.VISTORIA,
        estado_conservacao=EstadoConservacao.RUIM,
        foto_url="placas/vistoria.jpg",
        observacao="Vistoria lançada por engano",
        timestamp=datetime.now(UTC) + timedelta(minutes=5),
    )
    db_session.add(vistoria)
    await db_session.commit()
    vistoria_id = str(vistoria_uuid)

    # Exclui logicamente a vistoria
    del_res = await client.delete(
        f"/placas/{placa_id}/eventos/{vistoria_id}",
        headers=agent_headers,
    )
    assert del_res.status_code == 204

    # 1. Verifica que o registro continua no banco, mas com is_active = False
    stmt = select(EventosPlaca).where(EventosPlaca.id == vistoria_uuid)
    vistoria_db = (await db_session.exec(stmt)).one()
    assert vistoria_db.is_active is False

    # 2. Verifica que o LATERAL JOIN da placa voltou a apontar para CRIACAO
    list_res = await client.get("/placas/", headers=agent_headers)
    assert list_res.status_code == 200
    placa_item = list_res.json()["items"][0]
    assert placa_item["ultimo_evento"]["id"] == criacao_evento_id
    assert placa_item["ultimo_evento"]["tipo_evento"] == "CRIACAO"
    assert placa_item["ultimo_evento"]["estado_conservacao"] == "BOM"

    # 3. Verifica que a listagem de eventos da placa exibe apenas o evento ativo
    ev_list_res = await client.get(
        f"/placas/{placa_id}/historico",
        headers=agent_headers,
    )
    assert ev_list_res.status_code == 200
    assert ev_list_res.json()["total"] == 1
    assert ev_list_res.json()["items"][0]["id"] == criacao_evento_id


@pytest.mark.asyncio
async def test_delete_evento_criacao_unico_retorna_400(
    client: AsyncClient, agent_headers, created_placa
):
    placa_id = created_placa["id"]
    criacao_evento_id = created_placa["ultimo_evento"]["id"]

    response = await client.delete(
        f"/placas/{placa_id}/eventos/{criacao_evento_id}",
        headers=agent_headers,
    )
    assert response.status_code == 400
    assert "Não é permitido excluir o evento inicial" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_evento_criacao_permitido_quando_ha_outros_eventos(
    client: AsyncClient, db_session, agent_user, agent_headers, created_placa
):
    agent_id = (await db_session.exec(select(User.id))).one()
    placa_id = created_placa["id"]
    criacao_evento_id = created_placa["ultimo_evento"]["id"]

    vistoria = EventosPlaca(
        placa_id=UUID(placa_id),
        created_by=agent_id,
        tipo_evento=TipoEvento.VISTORIA,
        estado_conservacao=EstadoConservacao.REGULAR,
        timestamp=datetime.now(UTC) + timedelta(minutes=5),
    )
    db_session.add(vistoria)
    await db_session.commit()

    response = await client.delete(
        f"/placas/{placa_id}/eventos/{criacao_evento_id}",
        headers=agent_headers,
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_evento_not_found(
    client: AsyncClient, agent_headers, created_placa
):
    placa_id = created_placa["id"]
    response = await client.delete(
        f"/placas/{placa_id}/eventos/{uuid4()}",
        headers=agent_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Evento não encontrado para esta placa."


@pytest.mark.asyncio
async def test_delete_evento_placa_not_found(client: AsyncClient, agent_headers):
    response = await client.delete(
        f"/placas/{uuid4()}/eventos/{uuid4()}",
        headers=agent_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Placa não encontrada."


@pytest.mark.asyncio
async def test_delete_evento_unauthenticated(client: AsyncClient, created_placa):
    placa_id = created_placa["id"]
    evento_id = created_placa["ultimo_evento"]["id"]
    response = await client.delete(f"/placas/{placa_id}/eventos/{evento_id}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_soft_delete_evento_rollback_on_commit_error():
    mock_db = MagicMock()
    mock_db.commit = AsyncMock(side_effect=RuntimeError("Falha ao desativar evento"))
    mock_db.rollback = AsyncMock()

    evento = EventosPlaca(
        placa_id=uuid4(),
        created_by=1,
        tipo_evento=TipoEvento.VISTORIA,
        estado_conservacao=EstadoConservacao.BOM,
    )

    with pytest.raises(RuntimeError, match="Falha ao desativar evento"):
        await placa_functions.soft_delete_evento(mock_db, evento)

    mock_db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_evento_by_other_agent_forbidden_403(
    client: AsyncClient, db_session, created_placa
):
    other_agent = await create_user(
        db_session,
        User(
            nome="Outro Agente",
            email="outro.delete@test.com",
            password_hash="hashedpass",
            role=Role.AGENTE,
        ),
    )
    other_headers = {
        "Authorization": f"Bearer {create_access_token({'sub': str(other_agent.id)})}"
    }

    placa_id = created_placa["id"]
    evento_id = created_placa["ultimo_evento"]["id"]

    response = await client.delete(
        f"/placas/{placa_id}/eventos/{evento_id}",
        headers=other_headers,
    )
    assert response.status_code == 403
    assert "permissão" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_evento_by_admin_success(
    client: AsyncClient, db_session, created_placa
):
    agent_id = created_placa["ultimo_evento"]["created_by"]
    admin_user = await create_user(
        db_session,
        User(
            nome="Admin Exclusao",
            email="admin.delete@test.com",
            password_hash="hashedpass",
            role=Role.ADMINISTRADOR,
        ),
    )
    admin_headers = {
        "Authorization": f"Bearer {create_access_token({'sub': str(admin_user.id)})}"
    }

    placa_id = created_placa["id"]
    vistoria_uuid = uuid4()
    vistoria = EventosPlaca(
        id=vistoria_uuid,
        placa_id=UUID(placa_id),
        created_by=agent_id,
        tipo_evento=TipoEvento.VISTORIA,
        estado_conservacao=EstadoConservacao.RUIM,
        timestamp=datetime.now(UTC) + timedelta(minutes=5),
    )
    db_session.add(vistoria)
    await db_session.commit()

    response = await client.delete(
        f"/placas/{placa_id}/eventos/{vistoria_uuid}",
        headers=admin_headers,
    )
    assert response.status_code == 204
