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
    mock_service.get_public_url = MagicMock(
        return_value=(
            "http://localhost:9000/cacaplaca-images/placas/2026/10/20/"
            "placas_123_abcd1234.jpg"
        )
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
    codigo_contran: str = "R-1",
) -> dict:
    data = {
        **FORM_DATA,
        "codigo_contran": codigo_contran,
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


@pytest.mark.asyncio
async def test_get_placas_sem_endereco_retorna_corretamente(
    client: AsyncClient, quixada, agent_headers
):
    # Cadastra uma placa sem dados de endereço
    data_sem_end = {
        k: v
        for k, v in FORM_DATA.items()
        if k not in ("logradouro", "bairro", "cep", "referencia")
    }
    files = {"foto": ("placa.jpg", FAKE_JPEG_BYTES, "image/jpeg")}
    create_res = await client.post(
        "/placas/", data=data_sem_end, files=files, headers=agent_headers
    )
    assert create_res.status_code == 201
    created_id = create_res.json()["id"]

    # 1. Verifica no endpoint geral /placas/
    res_list = await client.get("/placas/")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total"] == 1
    assert list_data["items"][0]["id"] == created_id
    assert list_data["items"][0]["endereco"] is None


@pytest.mark.asyncio
async def test_get_placas_filtro_codigo_contran(
    client: AsyncClient, quixada, agent_headers
):
    p_r1 = await cadastrar_placa(client, agent_headers)
    files = {"foto": ("placa.jpg", FAKE_JPEG_BYTES, "image/jpeg")}
    res_a18 = await client.post(
        "/placas/",
        data={**FORM_DATA, "codigo_contran": "A-18", "latitude": "-4.9720"},
        files=files,
        headers=agent_headers,
    )
    assert res_a18.status_code == 201

    # 1. Busca exata por 'R-1'
    res_exact = await client.get("/placas/", params={"codigo_contran": "R-1"})
    assert res_exact.status_code == 200
    assert len(res_exact.json()["items"]) == 1
    assert res_exact.json()["items"][0]["id"] == p_r1["id"]
    assert (
        res_exact.json()["items"][0]["descricao_contran"] == "Parada Obrigatória (PARE)"
    )

    # 2. Busca por alias sem hífen 'R1'
    res_alias = await client.get("/placas/", params={"codigo_contran": "R1"})
    assert res_alias.status_code == 200
    assert len(res_alias.json()["items"]) == 1
    assert res_alias.json()["items"][0]["id"] == p_r1["id"]

    # 3. Busca por texto 'pare'
    res_desc = await client.get("/placas/", params={"codigo_contran": "pare"})
    assert res_desc.status_code == 200
    assert len(res_desc.json()["items"]) == 1
    assert res_desc.json()["items"][0]["id"] == p_r1["id"]

    # 4. Busca por 'lombada' -> A-18
    res_lombada = await client.get("/placas/", params={"codigo_contran": "lombada"})
    assert res_lombada.status_code == 200
    assert len(res_lombada.json()["items"]) == 1
    assert res_lombada.json()["items"][0]["codigo_contran"] == "A-18"


@pytest.mark.asyncio
async def test_get_placas_tipos_catalogo(client: AsyncClient):
    response = await client.get("/placas/tipos")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    codigos = {item["codigo"] for item in data}
    assert "R-1" in codigos
    assert "A-18" in codigos
    r1_item = next(item for item in data if item["codigo"] == "R-1")
    assert "PARE" in r1_item["descricao"]


@pytest.mark.asyncio
async def test_get_placas_filtro_busca_geral_search(
    client: AsyncClient, quixada, agent_headers
):
    files = {"foto": ("placa.jpg", FAKE_JPEG_BYTES, "image/jpeg")}

    # Placa 1: R-1 (Parada Obrigatória PARE), Centro, Rua Basílio Pinto
    p_r1 = await cadastrar_placa(
        client,
        agent_headers,
        codigo_contran="R-1",
        bairro="Centro",
        logradouro="Rua Basílio Pinto",
    )

    # Placa 2: A-18 (Saliência ou Lombada), Campo Novo, Avenida Plácido Castelo
    res_a18 = await client.post(
        "/placas/",
        data={
            **FORM_DATA,
            "codigo_contran": "A-18",
            "bairro": "Campo Novo",
            "logradouro": "Avenida Plácido Castelo",
            "latitude": "-4.9720",
        },
        files=files,
        headers=agent_headers,
    )
    assert res_a18.status_code == 201
    p_a18 = res_a18.json()

    # Placa 3: R-2 (Dê a Preferência), SEM ENDEREÇO
    form_sem_end = {
        k: v
        for k, v in FORM_DATA.items()
        if k not in ("logradouro", "bairro", "cep", "referencia")
    }
    form_sem_end["codigo_contran"] = "R-2"
    form_sem_end["latitude"] = "-4.9730"
    res_r2 = await client.post(
        "/placas/",
        data=form_sem_end,
        files=files,
        headers=agent_headers,
    )
    assert res_r2.status_code == 201
    p_r2 = res_r2.json()

    # 1. Busca por Rua (logradouro)
    res_rua = await client.get("/placas/", params={"search": "Basílio"})
    assert res_rua.status_code == 200
    ids_rua = [i["id"] for i in res_rua.json()["items"]]
    assert p_r1["id"] in ids_rua
    assert p_a18["id"] not in ids_rua

    # 2. Busca por Bairro
    res_bairro = await client.get("/placas/", params={"search": "Campo Novo"})
    assert res_bairro.status_code == 200
    ids_bairro = [i["id"] for i in res_bairro.json()["items"]]
    assert p_a18["id"] in ids_bairro
    assert p_r1["id"] not in ids_bairro

    # 3. Busca por Descrição CONTRAN ('pare')
    res_pare = await client.get("/placas/", params={"search": "pare"})
    assert res_pare.status_code == 200
    ids_pare = [i["id"] for i in res_pare.json()["items"]]
    assert p_r1["id"] in ids_pare
    assert p_a18["id"] not in ids_pare

    # 4. Busca por Descrição CONTRAN ('lombada')
    res_lombada = await client.get("/placas/", params={"search": "lombada"})
    assert res_lombada.status_code == 200
    ids_lombada = [i["id"] for i in res_lombada.json()["items"]]
    assert p_a18["id"] in ids_lombada
    assert p_r1["id"] not in ids_lombada

    # 5. Busca por Código com alias sem hífen ('R1')
    res_r1_alias = await client.get("/placas/", params={"search": "R1"})
    assert res_r1_alias.status_code == 200
    ids_r1 = [i["id"] for i in res_r1_alias.json()["items"]]
    assert p_r1["id"] in ids_r1

    # 6. Busca por Código exato ('A-18')
    res_code = await client.get("/placas/", params={"search": "A-18"})
    assert res_code.status_code == 200
    ids_code = [i["id"] for i in res_code.json()["items"]]
    assert p_a18["id"] in ids_code

    # 7. Busca com alias em português ('busca')
    res_busca = await client.get("/placas/", params={"busca": "Centro"})
    assert res_busca.status_code == 200
    ids_busca = [i["id"] for i in res_busca.json()["items"]]
    assert p_r1["id"] in ids_busca

    # 8. Busca em placa sem endereço via código CONTRAN
    res_sem_end = await client.get("/placas/", params={"search": "R-2"})
    assert res_sem_end.status_code == 200
    ids_sem_end = [i["id"] for i in res_sem_end.json()["items"]]
    assert p_r2["id"] in ids_sem_end

    # 9. Busca por termo inexistente
    res_inexistente = await client.get(
        "/placas/", params={"search": "InexistenteXYZ123"}
    )
    assert res_inexistente.status_code == 200
    assert len(res_inexistente.json()["items"]) == 0
