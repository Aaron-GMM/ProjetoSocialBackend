import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.domain.enums.role import Role
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions.user import create_user
from src.main import app


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
async def admin_user(db_session):
    user = User(
        nome="Admin Silva",
        email="admin@test.com",
        password_hash="hashedpass",
        role=Role.ADMINISTRADOR,
    )
    return await create_user(db_session, user)


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
def admin_token(admin_user):
    from src.core.security import create_access_token

    return create_access_token({"sub": str(admin_user.id)})


@pytest.fixture
def agent_token(agent_user):
    from src.core.security import create_access_token

    return create_access_token({"sub": str(agent_user.id)})


@pytest.mark.asyncio
async def test_list_users_as_admin(client: AsyncClient, admin_token: str, agent_user):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/users/", headers=headers)
    assert response.status_code == 200, response.json()
    data = response.json()
    assert len(data) >= 2  # Admin and Agent
    assert "password_hash" not in data[0]


@pytest.mark.asyncio
async def test_list_users_as_agent_forbidden(client: AsyncClient, agent_token: str):
    headers = {"Authorization": f"Bearer {agent_token}"}
    response = await client.get("/users/", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_user_as_admin(client: AsyncClient, admin_token: str, agent_user):
    headers = {"Authorization": f"Bearer {admin_token}"}
    update_data = {"is_active": False, "nome": "Agente Desativado"}
    response = await client.patch(
        f"/users/{agent_user.id}", json=update_data, headers=headers
    )
    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["is_active"] is False
    assert data["nome"] == "Agente Desativado"


@pytest.mark.asyncio
async def test_update_user_not_found(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    update_data = {"is_active": False}
    response = await client.patch("/users/9999", json=update_data, headers=headers)
    assert response.status_code == 404
