from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from src.api.routes.auth import router
from src.core.security import ALGORITHM, SECRET_KEY, get_password_hash

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_login_sucesso():
    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.role = "admin"
    fake_user.password_hash = get_password_hash("senha_valida")

    with patch(
        "src.api.routes.auth.get_user_by_email_case_insensitive",
        new_callable=AsyncMock,
        return_value=fake_user,
    ):
        response = client.post(
            "/auth/login",
            data={"username": "usuario@teste.com", "password": "senha_valida"},
        )

        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

        payload = jwt.decode(body["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "1"
        assert payload["role"] == "admin"


def test_login_usuario_nao_encontrado_retorna_401():
    with patch(
        "src.api.routes.auth.get_user_by_email_case_insensitive",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.post(
            "/auth/login",
            data={"username": "inexistente@teste.com", "password": "qualquer_senha"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "E-mail ou senha incorretos."


def test_login_senha_incorreta_retorna_401():
    fake_user = MagicMock()
    fake_user.id = 2
    fake_user.role = "user"
    fake_user.password_hash = get_password_hash("senha_real")

    with patch(
        "src.api.routes.auth.get_user_by_email_case_insensitive",
        new_callable=AsyncMock,
        return_value=fake_user,
    ):
        response = client.post(
            "/auth/login",
            data={"username": "usuario@teste.com", "password": "senha_errada"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "E-mail ou senha incorretos."


def test_login_usuario_sem_hash_retorna_401():
    fake_user = MagicMock()
    fake_user.id = 3
    fake_user.role = "user"
    fake_user.password_hash = None
    fake_user.hashed_password = None

    with patch(
        "src.api.routes.auth.get_user_by_email_case_insensitive",
        new_callable=AsyncMock,
        return_value=fake_user,
    ):
        response = client.post(
            "/auth/login",
            data={"username": "usuario@teste.com", "password": "qualquer_senha"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "E-mail ou senha incorretos."
