from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlmodel import func, select

from src.api.routes import placas as placas_route
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
from src.infrastructure.storage.minio_client import StorageError
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


def make_photo_files(
    filename: str = "placa.jpg",
    content: bytes = FAKE_JPEG_BYTES,
    content_type: str = "image/jpeg",
):
    return {"foto": (filename, content, content_type)}


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


async def count_rows(db_session, model) -> int:
    result = await db_session.exec(select(func.count()).select_from(model))
    return result.one()


@pytest.mark.asyncio
async def test_create_placa_success(
    client: AsyncClient, db_session, quixada, agent_user, agent_headers, mock_minio
):
    agent_id = agent_user.id
    response = await client.post(
        "/placas/",
        data=FORM_DATA,
        files=make_photo_files(),
        headers=agent_headers,
    )

    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["codigo_contran"] == "R-1"
    assert data["latitude"] == float(FORM_DATA["latitude"])
    assert data["longitude"] == float(FORM_DATA["longitude"])
    assert data["endereco"]["bairro"] == "Centro"
    assert data["ultimo_evento"]["tipo_evento"] == "CRIACAO"
    assert data["ultimo_evento"]["estado_conservacao"] == "BOM"
    assert data["ultimo_evento"]["created_by"] == agent_id
    assert data["ultimo_evento"]["foto_url"].startswith(
        "http://localhost:9000/cacaplaca-images/placas/2026/10/20/"
    )

    mock_minio.ensure_bucket_exists_async.assert_awaited_once()
    mock_minio.upload_file_async.assert_awaited_once()
    mock_minio.get_presigned_url_async.assert_awaited_once()

    result = await db_session.execute(
        text("SELECT ST_X(location), ST_Y(location) FROM placas WHERE id = :id"),
        {"id": data["id"]},
    )
    assert result.one() == (float(FORM_DATA["longitude"]), float(FORM_DATA["latitude"]))

    evento_row = (await db_session.exec(select(EventosPlaca))).one()
    assert evento_row.foto_url == "placas/2026/10/20/placas_123_abcd1234.jpg"
    assert await count_rows(db_session, Enderecos) == 1
    assert await count_rows(db_session, EventosPlaca) == 1


@pytest.mark.asyncio
async def test_create_placa_outside_quixada(
    client: AsyncClient, db_session, quixada, agent_headers, mock_minio
):
    form_data = {**FORM_DATA, "latitude": "-3.732", "longitude": "-38.526"}
    response = await client.post(
        "/placas/",
        data=form_data,
        files=make_photo_files(),
        headers=agent_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "As coordenadas da placa estão fora de Quixadá!"
    mock_minio.upload_file_async.assert_not_awaited()
    assert await count_rows(db_session, Placa) == 0


@pytest.mark.asyncio
async def test_create_placa_without_municipio(
    client: AsyncClient, db_session, agent_headers, mock_minio
):
    response = await client.post(
        "/placas/",
        data=FORM_DATA,
        files=make_photo_files(),
        headers=agent_headers,
    )

    assert response.status_code == 500
    mock_minio.upload_file_async.assert_not_awaited()
    assert await count_rows(db_session, Placa) == 0


@pytest.mark.asyncio
async def test_create_placa_unauthenticated(client: AsyncClient, quixada):
    response = await client.post(
        "/placas/", data=FORM_DATA, files=make_photo_files()
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_placa_invalid_payload(
    client: AsyncClient, quixada, agent_headers
):
    form_data = {**FORM_DATA, "codigo_contran": "XYZ", "latitude": "200"}
    response = await client.post(
        "/placas/",
        data=form_data,
        files=make_photo_files(),
        headers=agent_headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_placa_invalid_image_type(
    client: AsyncClient, db_session, quixada, agent_headers, mock_minio
):
    response = await client.post(
        "/placas/",
        data=FORM_DATA,
        files=make_photo_files(
            filename="documento.pdf",
            content=b"%PDF-1.4",
            content_type="application/pdf",
        ),
        headers=agent_headers,
    )

    assert response.status_code == 400
    assert "Formato de imagem inválido" in response.json()["detail"]
    mock_minio.upload_file_async.assert_not_awaited()
    assert await count_rows(db_session, Placa) == 0


@pytest.mark.asyncio
async def test_create_placa_empty_image(
    client: AsyncClient, db_session, quixada, agent_headers, mock_minio
):
    response = await client.post(
        "/placas/",
        data=FORM_DATA,
        files=make_photo_files(content=b""),
        headers=agent_headers,
    )

    assert response.status_code == 400
    assert "vazio" in response.json()["detail"]
    mock_minio.upload_file_async.assert_not_awaited()
    assert await count_rows(db_session, Placa) == 0


@pytest.mark.asyncio
async def test_create_placa_minio_unavailable_returns_503(
    client: AsyncClient, db_session, quixada, agent_headers, mock_minio
):
    mock_minio.upload_file_async.side_effect = StorageError("MinIO offline")

    response = await client.post(
        "/placas/",
        data=FORM_DATA,
        files=make_photo_files(),
        headers=agent_headers,
    )

    assert response.status_code == 503
    assert "indisponível" in response.json()["detail"]
    assert await count_rows(db_session, Placa) == 0


@pytest.mark.asyncio
async def test_create_placa_db_failure_cleans_up_minio_file(
    client: AsyncClient, quixada, agent_headers, mock_minio, monkeypatch
):
    monkeypatch.setattr(
        placa_functions,
        "create_placa",
        AsyncMock(side_effect=RuntimeError("Erro no banco")),
    )

    with pytest.raises(RuntimeError, match="Erro no banco"):
        await client.post(
            "/placas/",
            data=FORM_DATA,
            files=make_photo_files(),
            headers=agent_headers,
        )

    mock_minio.delete_file_async.assert_awaited_once_with(
        "placas/2026/10/20/placas_123_abcd1234.jpg"
    )


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
