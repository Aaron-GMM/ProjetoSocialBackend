from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from src.api.routes.auth import router
from src.core.security import ALGORITHM, SECRET_KEY, get_password_hash
from src.domain.enums.role import Role

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_login_sucesso():
    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.role = Role.ADMINISTRADOR
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
        assert payload["role"] == "ADMINISTRADOR"


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
    fake_user.role = Role.AGENTE
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
    fake_user.role = Role.AGENTE
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


GENERIC_MESSAGE = (
    "Se o e-mail estiver cadastrado, você receberá em instantes um link "
    "para redefinir sua senha."
)


def test_forgot_password_usuario_existente_envia_email_com_token():
    fake_user = MagicMock()
    fake_user.id = 7
    fake_user.email = "usuario@teste.com"
    fake_user.nome = "Usuário Teste"

    with (
        patch(
            "src.api.routes.auth.get_user_by_email_case_insensitive",
            new_callable=AsyncMock,
            return_value=fake_user,
        ),
        patch("src.api.routes.auth.create_reset_token", return_value="token-falso"),
        patch("src.api.routes.auth.send_email") as mock_send_email,
    ):
        response = client.post(
            "/auth/forgot-password", json={"email": "usuario@teste.com"}
        )

    assert response.status_code == 200
    assert response.json() == {"message": GENERIC_MESSAGE}

    mock_send_email.assert_called_once()
    _, kwargs = mock_send_email.call_args
    assert kwargs["recipient"] == "usuario@teste.com"
    assert "token-falso" in kwargs["body"]


def test_forgot_password_usuario_inexistente_nao_envia_email():
    with (
        patch(
            "src.api.routes.auth.get_user_by_email_case_insensitive",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("src.api.routes.auth.create_reset_token") as mock_create_token,
        patch("src.api.routes.auth.send_email") as mock_send_email,
    ):
        response = client.post(
            "/auth/forgot-password", json={"email": "fantasma@teste.com"}
        )

    assert response.status_code == 200
    assert response.json() == {"message": GENERIC_MESSAGE}
    mock_create_token.assert_not_called()
    mock_send_email.assert_not_called()


def test_forgot_password_mensagem_generica_previnem_user_enumeration():
    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "existe@teste.com"
    fake_user.nome = "Existe"

    with patch(
        "src.api.routes.auth.get_user_by_email_case_insensitive",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response_inexistente = client.post(
            "/auth/forgot-password", json={"email": "naoexiste@teste.com"}
        )

    with (
        patch(
            "src.api.routes.auth.get_user_by_email_case_insensitive",
            new_callable=AsyncMock,
            return_value=fake_user,
        ),
        patch("src.api.routes.auth.create_reset_token", return_value="token-falso"),
        patch("src.api.routes.auth.send_email"),
    ):
        response_existente = client.post(
            "/auth/forgot-password", json={"email": "existe@teste.com"}
        )

    assert response_inexistente.status_code == response_existente.status_code == 200
    assert response_inexistente.json() == response_existente.json()


def test_forgot_password_email_invalido_retorna_422():
    response = client.post("/auth/forgot-password", json={"email": "email-invalido"})

    assert response.status_code == 422
