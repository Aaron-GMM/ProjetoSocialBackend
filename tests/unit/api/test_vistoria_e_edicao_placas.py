from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlmodel import func, select

from src.api.routes import placas as placas_route
from src.core.security import create_access_token
from src.domain.enums.placa_enums import EstadoConservacao, TipoEvento
from src.domain.enums.role import Role
from src.domain.models.endereco import Enderecos
from src.domain.models.eventos_placa import EventosPlaca
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions import placa as placa_functions
from src.infrastructure.database.functions.user import create_user
from src.infrastructure.storage.minio_client import StorageError
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

OLD_OBJECT = "placas/2026/10/20/placas_old.jpg"
NEW_OBJECT = "placas/2026/10/31/placas_new.jpg"

FAKE_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
)


def make_photo_files(content: bytes = FAKE_JPEG_BYTES, content_type="image/jpeg"):
    return {"foto": ("placa.jpg", content, content_type)}


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
    mock_service.upload_file_async = AsyncMock(side_effect=[OLD_OBJECT, NEW_OBJECT])
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
        email="agente@test.com",
        password_hash="hashedpass",
        role=Role.AGENTE,
    )
    return await create_user(db_session, user)


@pytest.fixture
def agent_headers(agent_user):
    token = create_access_token({"sub": str(agent_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def placa_id(client, agent_headers, mock_minio):
    response = await client.post(
        "/placas/", data=FORM_DATA, files=make_photo_files(), headers=agent_headers
    )
    assert response.status_code == 201, response.json()
    mock_minio.upload_file_async.reset_mock()
    mock_minio.delete_file_async.reset_mock()
    return response.json()["id"]


async def count_rows(db_session, model) -> int:
    result = await db_session.exec(select(func.count()).select_from(model))
    return result.one()


VISTORIA_DATA = {
    "estado_conservacao": "RUIM",
    "estado_pelicula": "REGULAR",
    "estado_suporte": "RUIM",
    "observacao": "Placa pichada",
}


@pytest.mark.asyncio
async def test_create_vistoria_success(
    client: AsyncClient, db_session, agent_headers, mock_minio, placa_id
):
    agent_id = (await db_session.exec(select(User.id))).one()
    response = await client.post(
        f"/placas/{placa_id}/vistoria",
        data=VISTORIA_DATA,
        files=make_photo_files(),
        headers=agent_headers,
    )

    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["tipo_evento"] == "VISTORIA"
    assert data["estado_conservacao"] == "RUIM"
    assert data["estado_pelicula"] == "REGULAR"
    assert data["estado_substrato"] is None
    assert data["observacao"] == "Placa pichada"
    assert data["created_by"] == agent_id
    assert data["foto_url"].endswith(NEW_OBJECT)
    assert await count_rows(db_session, EventosPlaca) == 2

    list_response = await client.get("/placas/")
    ultimo_evento = list_response.json()["items"][0]["ultimo_evento"]
    assert ultimo_evento["id"] == data["id"]
    assert ultimo_evento["tipo_evento"] == "VISTORIA"


@pytest.mark.asyncio
async def test_create_vistoria_placa_not_found(
    client: AsyncClient, agent_headers, mock_minio
):
    response = await client.post(
        f"/placas/{uuid4()}/vistoria",
        data=VISTORIA_DATA,
        files=make_photo_files(),
        headers=agent_headers,
    )

    assert response.status_code == 404
    mock_minio.upload_file_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_vistoria_unauthenticated(client: AsyncClient, placa_id):
    response = await client.post(
        f"/placas/{placa_id}/vistoria", data=VISTORIA_DATA, files=make_photo_files()
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_vistoria_invalid_payload(
    client: AsyncClient, agent_headers, placa_id
):
    response = await client.post(
        f"/placas/{placa_id}/vistoria",
        data={"estado_conservacao": "PESSIMO"},
        files=make_photo_files(),
        headers=agent_headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_vistoria_invalid_image(
    client: AsyncClient, db_session, agent_headers, mock_minio, placa_id
):
    response = await client.post(
        f"/placas/{placa_id}/vistoria",
        data=VISTORIA_DATA,
        files=make_photo_files(content=b"%PDF-1.4", content_type="application/pdf"),
        headers=agent_headers,
    )

    assert response.status_code == 400
    mock_minio.upload_file_async.assert_not_awaited()
    assert await count_rows(db_session, EventosPlaca) == 1


@pytest.mark.asyncio
async def test_create_vistoria_minio_unavailable(
    client: AsyncClient, db_session, agent_headers, mock_minio, placa_id
):
    mock_minio.upload_file_async.side_effect = StorageError("MinIO offline")

    response = await client.post(
        f"/placas/{placa_id}/vistoria",
        data=VISTORIA_DATA,
        files=make_photo_files(),
        headers=agent_headers,
    )

    assert response.status_code == 503
    assert await count_rows(db_session, EventosPlaca) == 1


@pytest.mark.asyncio
async def test_create_vistoria_db_failure_cleans_up_minio_file(
    client: AsyncClient, agent_headers, mock_minio, placa_id, monkeypatch
):
    monkeypatch.setattr(
        placa_functions,
        "create_evento",
        AsyncMock(side_effect=RuntimeError("Erro no banco")),
    )

    with pytest.raises(RuntimeError, match="Erro no banco"):
        await client.post(
            f"/placas/{placa_id}/vistoria",
            data=VISTORIA_DATA,
            files=make_photo_files(),
            headers=agent_headers,
        )

    mock_minio.delete_file_async.assert_awaited_once_with(NEW_OBJECT)


@pytest.mark.asyncio
async def test_update_placa_fields_and_endereco(
    client: AsyncClient, db_session, agent_headers, mock_minio, placa_id
):
    response = await client.patch(
        f"/placas/{placa_id}",
        data={"codigo_contran": "A-18", "afastamento": "2.0", "bairro": "Alto"},
        headers=agent_headers,
    )

    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["codigo_contran"] == "A-18"
    assert data["afastamento"] == 2.0
    assert data["tipo_suporte"] == "POSTE_ACO"
    assert data["endereco"]["bairro"] == "Alto"
    assert data["endereco"]["logradouro"] == "Rua Basílio Pinto"
    assert data["ultimo_evento"]["foto_url"].endswith(OLD_OBJECT)
    assert await count_rows(db_session, EventosPlaca) == 1
    mock_minio.upload_file_async.assert_not_awaited()
    mock_minio.delete_file_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_placa_creates_endereco_when_missing(
    client: AsyncClient, db_session, agent_headers, mock_minio
):
    form = {
        k: v for k, v in FORM_DATA.items() if k not in ("logradouro", "bairro", "cep")
    }
    created = await client.post(
        "/placas/", data=form, files=make_photo_files(), headers=agent_headers
    )
    placa_id = created.json()["id"]

    response = await client.patch(
        f"/placas/{placa_id}", data={"bairro": "Centro"}, headers=agent_headers
    )

    assert response.status_code == 200, response.json()
    assert response.json()["endereco"]["bairro"] == "Centro"
    assert await count_rows(db_session, Enderecos) == 1


@pytest.mark.asyncio
async def test_update_placa_replaces_photo(
    client: AsyncClient, db_session, agent_headers, mock_minio, placa_id
):
    response = await client.patch(
        f"/placas/{placa_id}", files=make_photo_files(), headers=agent_headers
    )

    assert response.status_code == 200, response.json()
    assert response.json()["ultimo_evento"]["foto_url"].endswith(NEW_OBJECT)
    mock_minio.delete_file_async.assert_awaited_once_with(OLD_OBJECT)

    evento = (await db_session.exec(select(EventosPlaca))).one()
    assert evento.foto_url == NEW_OBJECT
    assert evento.tipo_evento == TipoEvento.CRIACAO
    assert evento.estado_conservacao == EstadoConservacao.BOM


@pytest.mark.asyncio
async def test_update_placa_db_failure_cleans_up_new_photo(
    client: AsyncClient, agent_headers, mock_minio, placa_id, monkeypatch
):
    monkeypatch.setattr(
        placa_functions,
        "save_placa_changes",
        AsyncMock(side_effect=RuntimeError("Erro no banco")),
    )

    with pytest.raises(RuntimeError, match="Erro no banco"):
        await client.patch(
            f"/placas/{placa_id}", files=make_photo_files(), headers=agent_headers
        )

    mock_minio.delete_file_async.assert_awaited_once_with(NEW_OBJECT)


@pytest.mark.asyncio
async def test_update_placa_not_found(client: AsyncClient, agent_headers):
    response = await client.patch(
        f"/placas/{uuid4()}", data={"afastamento": "1"}, headers=agent_headers
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_placa_unauthenticated(client: AsyncClient, placa_id):
    response = await client.patch(f"/placas/{placa_id}", data={"afastamento": "1"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_placa_invalid_payload(
    client: AsyncClient, agent_headers, placa_id
):
    response = await client.patch(
        f"/placas/{placa_id}",
        data={"codigo_contran": "XYZ", "afastamento": "-1"},
        headers=agent_headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_save_placa_changes_rollback_on_commit_error():
    mock_db = MagicMock()
    mock_db.commit = AsyncMock(side_effect=RuntimeError("Falha ao persistir"))
    mock_db.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="Falha ao persistir"):
        await placa_functions.save_placa_changes(mock_db, [])

    mock_db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_evento_rollback_on_commit_error():
    mock_db = MagicMock()
    mock_db.commit = AsyncMock(side_effect=RuntimeError("Falha ao persistir"))
    mock_db.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="Falha ao persistir"):
        await placa_functions.create_evento(mock_db, MagicMock())

    mock_db.rollback.assert_awaited_once()
