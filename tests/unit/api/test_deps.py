from unittest.mock import AsyncMock, MagicMock

from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient
from jose import jwt

from src.api.deps import get_current_user, require_admin
from src.core.security import ALGORITHM, SECRET_KEY, create_access_token
from src.domain.enums.role import Role
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session

app = FastAPI()


@app.get("/test/protected")
async def protected_route(user: User = Depends(get_current_user)):
    return {"message": "ok", "user_id": user.id}


@app.get("/test/admin-only")
async def admin_route(user: User = Depends(require_admin)):
    return {"message": "admin ok", "role": user.role.value}


client = TestClient(app)


def test_get_current_user_token_invalido():
    response = client.get(
        "/test/protected",
        headers={"Authorization": "Bearer token_malformado"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Credenciais inválidas ou token expirado."


def test_get_current_user_sem_sub_no_payload():
    token = jwt.encode({"dados": "sem_sub"}, SECRET_KEY, algorithm=ALGORITHM)
    response = client.get(
        "/test/protected",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_usuario_nao_encontrado_no_banco():
    token = create_access_token(data={"sub": "999", "role": Role.ADMINISTRADOR.value})

    mock_db = AsyncMock()
    mock_db.get.return_value = None

    app.dependency_overrides[get_session] = lambda: mock_db

    try:
        response = client.get(
            "/test/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    finally:
        app.dependency_overrides.clear()


def test_get_current_user_sucesso():
    token = create_access_token(data={"sub": "1", "role": Role.ADMINISTRADOR.value})
    fake_user = MagicMock(spec=User)
    fake_user.id = 1
    fake_user.role = Role.ADMINISTRADOR

    mock_db = AsyncMock()
    mock_db.get.return_value = fake_user

    app.dependency_overrides[get_session] = lambda: mock_db

    try:
        response = client.get(
            "/test/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["user_id"] == 1
    finally:
        app.dependency_overrides.clear()


def test_require_admin_bloqueia_agente():
    fake_agent = MagicMock(spec=User)
    fake_agent.id = 2
    fake_agent.role = Role.AGENTE

    app.dependency_overrides[get_current_user] = lambda: fake_agent

    try:
        response = client.get("/test/admin-only")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert (
            response.json()["detail"]
            == "Acesso negado: requer privilégios de administrador."
        )
    finally:
        app.dependency_overrides.clear()


def test_require_admin_permite_administrador():
    fake_admin = MagicMock(spec=User)
    fake_admin.id = 1
    fake_admin.role = Role.ADMINISTRADOR

    app.dependency_overrides[get_current_user] = lambda: fake_admin

    try:
        response = client.get("/test/admin-only")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["role"] == Role.ADMINISTRADOR.value
    finally:
        app.dependency_overrides.clear()
