from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlmodel import func, select

from src.api.routes import eventos as eventos_route
from src.api.routes import placas as placas_route
from src.core.security import create_access_token
from src.domain.enums.role import Role
from src.domain.models.eventos_placa import EventosPlaca
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions import evento as evento_functions
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

OLD_OBJECT = "placas/2026/11/01/evento_old.jpg"
NEW_OBJECT = "placas/2026/11/03/evento_retificado.jpg"

FAKE_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
)


def make_photo_files(content: bytes = FAKE_JPEG_BYTES, content_type="image/jpeg"):
    return {"foto": ("evento.jpg", content, content_type)}


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
    monkeypatch.setattr(eventos_route, "minio_service", mock_service)
    return mock_service


@pytest_asyncio.fixture
async def agent_user(db_session):
    user = User(
        nome="Agente Criador",
        email="criador@test.com",
        password_hash="hashedpass",
        role=Role.AGENTE,
    )
    return await create_user(db_session, user)


@pytest.fixture
def agent_headers(agent_user):
    token = create_access_token({"sub": str(agent_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def other_agent_headers(db_session):
    other = User(
        nome="Outro Agente",
        email="outro.agente@test.com",
        password_hash="hashedpass",
        role=Role.AGENTE,
    )
    created = await create_user(db_session, other)
    token = create_access_token({"sub": str(created.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_headers(db_session):
    admin = User(
        nome="Admin Sistema",
        email="admin.eventos@test.com",
        password_hash="hashedpass",
        role=Role.ADMINISTRADOR,
    )
    created = await create_user(db_session, admin)
    token = create_access_token({"sub": str(created.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def placa_and_evento(client, agent_headers, mock_minio):
    response = await client.post(
        "/placas/", data=FORM_DATA, files=make_photo_files(), headers=agent_headers
    )
    assert response.status_code == 201, response.json()
    mock_minio.upload_file_async.reset_mock()
    mock_minio.delete_file_async.reset_mock()
    body = response.json()
    return body["id"], body["ultimo_evento"]["id"]


async def count_rows(db_session, model) -> int:
    result = await db_session.exec(select(func.count()).select_from(model))
    return result.one()


@pytest.mark.asyncio
async def test_update_evento_by_owner_multipart_with_photo_success(
    client: AsyncClient,
    db_session,
    agent_headers,
    mock_minio,
    placa_and_evento,
):
    """Agente criador edita seu evento via multipart/form-data com nova foto."""
    placa_id, evento_id = placa_and_evento

    response = await client.patch(
        f"/placas/{placa_id}/eventos/{evento_id}",
        data={
            "estado_conservacao": "RUIM",
            "estado_pelicula": "REGULAR",
            "estado_substrato": "BOM",
            "estado_suporte": "RUIM",
            "observacao": "  Observação retificada após conferência  ",
        },
        files=make_photo_files(),
        headers=agent_headers,
    )

    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["id"] == evento_id
    assert data["tipo_evento"] == "CRIACAO"
    assert data["estado_conservacao"] == "RUIM"
    assert data["estado_pelicula"] == "REGULAR"
    assert data["estado_substrato"] == "BOM"
    assert data["estado_suporte"] == "RUIM"
    assert data["observacao"] == "Observação retificada após conferência"
    assert data["foto_url"].endswith(NEW_OBJECT)

    # Garante que foi Update in-place (sem criar nova vistoria)
    assert await count_rows(db_session, EventosPlaca) == 1
    mock_minio.upload_file_async.assert_awaited_once()
    mock_minio.delete_file_async.assert_awaited_once_with(OLD_OBJECT)


@pytest.mark.asyncio
async def test_update_evento_by_owner_json_without_photo_success(
    client: AsyncClient,
    db_session,
    agent_headers,
    mock_minio,
    placa_and_evento,
):
    """Agente criador edita o evento via JSON mantendo a foto original."""
    placa_id, evento_id = placa_and_evento

    response = await client.patch(
        f"/placas/{placa_id}/eventos/{evento_id}",
        json={
            "estado_conservacao": "REGULAR",
            "observacao": "Correção rápida de texto via JSON",
        },
        headers=agent_headers,
    )

    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["id"] == evento_id
    assert data["estado_conservacao"] == "REGULAR"
    assert data["observacao"] == "Correção rápida de texto via JSON"
    assert data["foto_url"].endswith(OLD_OBJECT)
    assert await count_rows(db_session, EventosPlaca) == 1
    mock_minio.upload_file_async.assert_not_awaited()
    mock_minio.delete_file_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_evento_by_admin_success(
    client: AsyncClient,
    db_session,
    admin_headers,
    mock_minio,
    placa_and_evento,
):
    """Administrador pode editar evento criado por qualquer agente."""
    placa_id, evento_id = placa_and_evento

    response = await client.patch(
        f"/placas/{placa_id}/eventos/{evento_id}",
        data={
            "estado_conservacao": "RUIM",
            "observacao": "Retificado pela auditoria do administrador",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["id"] == evento_id
    assert data["estado_conservacao"] == "RUIM"
    assert data["observacao"] == "Retificado pela auditoria do administrador"
    assert await count_rows(db_session, EventosPlaca) == 1


@pytest.mark.asyncio
async def test_update_evento_by_other_agent_forbidden_403(
    client: AsyncClient,
    other_agent_headers,
    mock_minio,
    placa_and_evento,
):
    """Agente comum não pode editar evento criado por outro agente (HTTP 403)."""
    placa_id, evento_id = placa_and_evento

    response = await client.patch(
        f"/placas/{placa_id}/eventos/{evento_id}",
        data={"observacao": "Tentativa indevida"},
        headers=other_agent_headers,
    )

    assert response.status_code == 403
    assert "permissão" in response.json()["detail"].lower()
    mock_minio.upload_file_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_evento_unauthenticated_401(client: AsyncClient, placa_and_evento):
    """Requisição sem token deve retornar HTTP 401."""
    placa_id, evento_id = placa_and_evento
    response = await client.patch(
        f"/placas/{placa_id}/eventos/{evento_id}",
        data={"observacao": "Sem token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_evento_placa_not_found_404(
    client: AsyncClient, agent_headers, placa_and_evento
):
    """Se placa_id não existir, retorna HTTP 404."""
    _, evento_id = placa_and_evento
    response = await client.patch(
        f"/placas/{uuid4()}/eventos/{evento_id}",
        data={"observacao": "Placa inexistente"},
        headers=agent_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Placa não encontrada."


@pytest.mark.asyncio
async def test_update_evento_not_found_404(
    client: AsyncClient, agent_headers, placa_and_evento
):
    """Se evento_id não existir para a placa informada, retorna HTTP 404."""
    placa_id, _ = placa_and_evento
    response = await client.patch(
        f"/placas/{placa_id}/eventos/{uuid4()}",
        data={"observacao": "Evento inexistente"},
        headers=agent_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Evento não encontrado para esta placa."


@pytest.mark.asyncio
async def test_update_evento_invalid_payload_422(
    client: AsyncClient, agent_headers, placa_and_evento
):
    """Valida retorno 422 para enum inválido via form-data e via JSON."""
    placa_id, evento_id = placa_and_evento

    res_form = await client.patch(
        f"/placas/{placa_id}/eventos/{evento_id}",
        data={"estado_conservacao": "DESTRUIDO"},
        headers=agent_headers,
    )
    assert res_form.status_code == 422

    res_json = await client.patch(
        f"/placas/{placa_id}/eventos/{evento_id}",
        json={"estado_conservacao": "DESTRUIDO"},
        headers=agent_headers,
    )
    assert res_json.status_code == 422

    res_json_list = await client.patch(
        f"/placas/{placa_id}/eventos/{evento_id}",
        json=["invalido"],
        headers=agent_headers,
    )
    assert res_json_list.status_code == 422


@pytest.mark.asyncio
async def test_update_evento_invalid_and_empty_image_400(
    client: AsyncClient, agent_headers, mock_minio, placa_and_evento
):
    """Valida retorno 400 para imagem com formato inválido ou arquivo vazio."""
    placa_id, evento_id = placa_and_evento

    res_pdf = await client.patch(
        f"/placas/{placa_id}/eventos/{evento_id}",
        files=make_photo_files(content=b"%PDF-1.4", content_type="application/pdf"),
        headers=agent_headers,
    )
    assert res_pdf.status_code == 400

    res_empty = await client.patch(
        f"/placas/{placa_id}/eventos/{evento_id}",
        files=make_photo_files(content=b"", content_type="image/jpeg"),
        headers=agent_headers,
    )
    assert res_empty.status_code == 400
    mock_minio.upload_file_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_evento_minio_unavailable_503(
    client: AsyncClient, agent_headers, mock_minio, placa_and_evento
):
    """Se o MinIO falhar durante o upload da nova foto, retorna HTTP 503."""
    placa_id, evento_id = placa_and_evento
    mock_minio.upload_file_async.side_effect = StorageError("MinIO indisponível")

    response = await client.patch(
        f"/placas/{placa_id}/eventos/{evento_id}",
        files=make_photo_files(),
        headers=agent_headers,
    )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_update_evento_db_failure_cleans_up_new_photo(
    client: AsyncClient, agent_headers, mock_minio, placa_and_evento, monkeypatch
):
    """Se o banco falhar após o upload da nova foto, remove a nova foto do MinIO."""
    placa_id, evento_id = placa_and_evento
    mock_update = AsyncMock(
        side_effect=RuntimeError("Falha no banco ao atualizar evento")
    )
    monkeypatch.setattr(evento_functions, "update_evento", mock_update)
    monkeypatch.setattr(placa_functions, "update_evento", mock_update)

    with pytest.raises(RuntimeError, match="Falha no banco ao atualizar evento"):
        await client.patch(
            f"/placas/{placa_id}/eventos/{evento_id}",
            data={"observacao": "Teste rollback MinIO"},
            files=make_photo_files(),
            headers=agent_headers,
        )

    mock_minio.delete_file_async.assert_awaited_once_with(NEW_OBJECT)
