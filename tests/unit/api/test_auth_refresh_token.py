from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from src.api.routes.auth import login, logout, refresh_tokens, reset_password
from src.application.schemas.auth_schema import (
    RefreshTokenRequest,
    ResetPasswordRequest,
)
from src.core.security import generate_refresh_token_string, hash_token
from src.domain.enums.role import Role
from src.domain.models.refresh_token import RefreshToken
from src.domain.models.user import User

PATCH_GET_USER = "src.api.routes.auth.get_user_by_email_case_insensitive"
PATCH_VERIFY_PWD = "src.api.routes.auth.verify_password"
PATCH_ACCESS_TOKEN = "src.api.routes.auth.create_access_token"
PATCH_REFRESH_STR = "src.api.routes.auth.generate_refresh_token_string"


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ==============================================================================
# 1. Testes Unitários de Segurança
# ==============================================================================


def test_generate_refresh_token_string_uniqueness_and_format():
    token_1 = generate_refresh_token_string()
    token_2 = generate_refresh_token_string()

    assert isinstance(token_1, str)
    assert len(token_1) >= 64
    assert token_1 != token_2


def test_hash_token_consistency():
    token = "test_token_secure_value_123"
    hash_1 = hash_token(token)
    hash_2 = hash_token(token)

    assert hash_1 == hash_2
    assert len(hash_1) == 64
    assert hash_token("different_token") != hash_1


# ==============================================================================
# 2. Testes Unitários: POST /auth/login
# ==============================================================================


@pytest.mark.asyncio
async def test_unit_login_success():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    form_data = OAuth2PasswordRequestForm(
        grant_type="password",
        username="agente@teste.com",
        password="SenhaForte123",
        scope="",
        client_id=None,
        client_secret=None,
    )
    mock_user = User(
        id=1,
        nome="Agente Teste",
        email="agente@teste.com",
        password_hash="mocked_hash",
        role=Role.AGENTE,
        is_active=True,
    )

    with (
        patch(PATCH_GET_USER, new_callable=AsyncMock) as mock_get_user,
        patch(PATCH_VERIFY_PWD, return_value=True),
        patch(PATCH_ACCESS_TOKEN, return_value="mocked_access_token"),
        patch(PATCH_REFRESH_STR, return_value="raw_refresh_token_123"),
    ):
        mock_get_user.return_value = mock_user

        response = await login(form_data=form_data, db=mock_db)

        assert response.access_token == "mocked_access_token"
        assert response.refresh_token == "raw_refresh_token_123"
        assert response.token_type == "bearer"

        mock_db.exec.assert_awaited_once()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

        added_token = mock_db.add.call_args[0][0]
        assert isinstance(added_token, RefreshToken)
        assert added_token.token_hash == hash_token("raw_refresh_token_123")
        assert added_token.user_id == 1
        assert added_token.revoked is False


@pytest.mark.asyncio
async def test_unit_login_user_not_found():
    mock_db = AsyncMock()
    form_data = OAuth2PasswordRequestForm(
        grant_type="password",
        username="inexistente@teste.com",
        password="qualquer_senha",
        scope="",
        client_id=None,
        client_secret=None,
    )

    with patch(PATCH_GET_USER, new_callable=AsyncMock) as mock_get_user:
        mock_get_user.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await login(form_data=form_data, db=mock_db)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "E-mail ou senha incorretos."


@pytest.mark.asyncio
async def test_unit_login_user_inactive():
    mock_db = AsyncMock()
    form_data = OAuth2PasswordRequestForm(
        grant_type="password",
        username="inativo@teste.com",
        password="qualquer_senha",
        scope="",
        client_id=None,
        client_secret=None,
    )
    mock_user = User(
        id=2,
        nome="Agente Inativo",
        email="inativo@teste.com",
        password_hash="mocked_hash",
        role=Role.AGENTE,
        is_active=False,
    )

    with patch(PATCH_GET_USER, new_callable=AsyncMock) as mock_get_user:
        mock_get_user.return_value = mock_user

        with pytest.raises(HTTPException) as exc_info:
            await login(form_data=form_data, db=mock_db)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "E-mail ou senha incorretos."


@pytest.mark.asyncio
async def test_unit_login_wrong_password():
    mock_db = AsyncMock()
    form_data = OAuth2PasswordRequestForm(
        grant_type="password",
        username="agente@teste.com",
        password="SenhaErrada",
        scope="",
        client_id=None,
        client_secret=None,
    )
    mock_user = User(
        id=1,
        nome="Agente Teste",
        email="agente@teste.com",
        password_hash="mocked_hash",
        role=Role.AGENTE,
        is_active=True,
    )

    with (
        patch(PATCH_GET_USER, new_callable=AsyncMock) as mock_get_user,
        patch(PATCH_VERIFY_PWD, return_value=False),
    ):
        mock_get_user.return_value = mock_user

        with pytest.raises(HTTPException) as exc_info:
            await login(form_data=form_data, db=mock_db)

        assert exc_info.value.status_code == 401


# ==============================================================================
# 3. Testes Unitários: POST /auth/refresh
# ==============================================================================


@pytest.mark.asyncio
async def test_unit_refresh_success():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    raw_token = "valid_raw_token"
    mock_token_record = RefreshToken(
        id=10,
        token_hash=hash_token(raw_token),
        user_id=1,
        expires_at=get_utc_now() + timedelta(days=7),
        revoked=False,
    )
    mock_user = User(
        id=1,
        nome="Agente Ativo",
        email="agente@teste.com",
        password_hash="mocked_hash",
        role=Role.AGENTE,
        is_active=True,
    )

    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = mock_token_record
    mock_db.exec.return_value = mock_exec_result
    mock_db.get.return_value = mock_user

    with (
        patch(PATCH_ACCESS_TOKEN, return_value="new_access_token_mock"),
        patch(PATCH_REFRESH_STR, return_value="new_raw_refresh_token"),
    ):
        request = RefreshTokenRequest(refresh_token=raw_token)
        response = await refresh_tokens(request=request, db=mock_db)

        assert response.access_token == "new_access_token_mock"
        assert response.refresh_token == "new_raw_refresh_token"
        assert response.token_type == "bearer"
        assert mock_token_record.revoked is True
        assert mock_db.add.call_count == 2
        assert mock_db.commit.await_count == 1
        assert mock_db.exec.await_count == 2


@pytest.mark.asyncio
async def test_unit_refresh_pessimistic_locking_and_purges_expired_tokens():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    raw_token = "valid_raw_token_concurrency"
    mock_token_record = RefreshToken(
        id=15,
        token_hash=hash_token(raw_token),
        user_id=1,
        expires_at=get_utc_now() + timedelta(days=7),
        revoked=False,
    )
    mock_user = User(
        id=1,
        nome="Agente Concorrencia",
        email="concorrencia@teste.com",
        password_hash="mocked_hash",
        role=Role.AGENTE,
        is_active=True,
    )

    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = mock_token_record
    mock_db.exec.return_value = mock_exec_result
    mock_db.get.return_value = mock_user

    with (
        patch(PATCH_ACCESS_TOKEN, return_value="access_token_mock"),
        patch(PATCH_REFRESH_STR, return_value="refresh_token_mock"),
    ):
        request = RefreshTokenRequest(refresh_token=raw_token)
        await refresh_tokens(request=request, db=mock_db)

        # 1. Verifica lock pessimista (with_for_update) no primeiro SELECT
        select_stmt = mock_db.exec.call_args_list[0][0][0]
        assert getattr(select_stmt, "_for_update_arg", None) is not None

        # 2. Verifica segundo exec realizando o DELETE de expurgo de tokens
        delete_stmt = mock_db.exec.call_args_list[1][0][0]
        assert delete_stmt.is_delete


@pytest.mark.asyncio
async def test_unit_refresh_token_not_found():
    mock_db = AsyncMock()
    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = None
    mock_db.exec.return_value = mock_exec_result

    request = RefreshTokenRequest(refresh_token="non_existent_token")

    with pytest.raises(HTTPException) as exc_info:
        await refresh_tokens(request=request, db=mock_db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Refresh token inválido, expirado ou revogado."


@pytest.mark.asyncio
async def test_unit_refresh_token_already_revoked():
    mock_db = AsyncMock()
    mock_token_record = RefreshToken(
        id=11,
        token_hash=hash_token("revoked_token"),
        user_id=1,
        expires_at=get_utc_now() + timedelta(days=7),
        revoked=True,
    )
    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = mock_token_record
    mock_db.exec.return_value = mock_exec_result

    request = RefreshTokenRequest(refresh_token="revoked_token")

    with pytest.raises(HTTPException) as exc_info:
        await refresh_tokens(request=request, db=mock_db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Refresh token inválido, expirado ou revogado."
    assert mock_db.exec.await_count == 2
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_unit_refresh_token_theft_detection_revokes_all_sessions():
    mock_db = AsyncMock()
    compromised_token = RefreshToken(
        id=99,
        token_hash=hash_token("stolen_revoked_token"),
        user_id=42,
        expires_at=get_utc_now() + timedelta(days=7),
        revoked=True,
    )
    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = compromised_token
    mock_db.exec.return_value = mock_exec_result

    request = RefreshTokenRequest(refresh_token="stolen_revoked_token")

    with pytest.raises(HTTPException) as exc_info:
        await refresh_tokens(request=request, db=mock_db)

    assert exc_info.value.status_code == 401
    assert mock_db.exec.await_count == 2
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_unit_refresh_token_expired():
    mock_db = AsyncMock()
    mock_token_record = RefreshToken(
        id=12,
        token_hash=hash_token("expired_token"),
        user_id=1,
        expires_at=get_utc_now() - timedelta(seconds=10),
        revoked=False,
    )
    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = mock_token_record
    mock_db.exec.return_value = mock_exec_result

    request = RefreshTokenRequest(refresh_token="expired_token")

    with pytest.raises(HTTPException) as exc_info:
        await refresh_tokens(request=request, db=mock_db)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_unit_refresh_user_inactive():
    mock_db = AsyncMock()
    mock_token_record = RefreshToken(
        id=13,
        token_hash=hash_token("token_user_inactive"),
        user_id=5,
        expires_at=get_utc_now() + timedelta(days=7),
        revoked=False,
    )
    mock_user_inactive = User(
        id=5,
        nome="Usuario Desativado",
        email="inactive@teste.com",
        password_hash="mock",
        role=Role.AGENTE,
        is_active=False,
    )

    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = mock_token_record
    mock_db.exec.return_value = mock_exec_result
    mock_db.get.return_value = mock_user_inactive

    request = RefreshTokenRequest(refresh_token="token_user_inactive")

    with pytest.raises(HTTPException) as exc_info:
        await refresh_tokens(request=request, db=mock_db)

    assert exc_info.value.status_code == 401


# ==============================================================================
# 4. Testes Unitários: POST /auth/reset-password e Revogação de Sessões
# ==============================================================================


@pytest.mark.asyncio
async def test_unit_reset_password_revokes_all_active_refresh_tokens():
    mock_db = AsyncMock()
    mock_user = User(
        id=7,
        nome="Agente Reset",
        email="reset@teste.com",
        password_hash="old_hash",
        role=Role.AGENTE,
        is_active=True,
    )

    with patch(
        "src.api.routes.auth.change_user_password", new_callable=AsyncMock
    ) as mock_change_pwd:
        request = ResetPasswordRequest(new_password="NovaSenhaSegura123")
        response = await reset_password(
            request=request, current_user=mock_user, db=mock_db
        )

        assert response == {"message": "Senha redefinida com sucesso."}
        mock_change_pwd.assert_awaited_once_with(
            new_password="NovaSenhaSegura123",
            user=mock_user,
            db=mock_db,
        )
        mock_db.exec.assert_awaited_once()
        mock_db.commit.assert_awaited_once()


# ==============================================================================
# 5. Testes Unitários: POST /auth/logout
# ==============================================================================


@pytest.mark.asyncio
async def test_unit_logout_success():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    raw_token = "valid_logout_token"
    mock_token_record = RefreshToken(
        id=20,
        token_hash=hash_token(raw_token),
        user_id=1,
        expires_at=get_utc_now() + timedelta(days=7),
        revoked=False,
    )
    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = mock_token_record
    mock_db.exec.return_value = mock_exec_result

    request = RefreshTokenRequest(refresh_token=raw_token)
    response = await logout(request=request, db=mock_db)

    assert response == {"message": "Sessão encerrada com sucesso."}
    assert mock_token_record.revoked is True
    mock_db.add.assert_called_once_with(mock_token_record)
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_unit_logout_token_not_found():
    mock_db = AsyncMock()
    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = None
    mock_db.exec.return_value = mock_exec_result

    request = RefreshTokenRequest(refresh_token="inexistent_token")
    response = await logout(request=request, db=mock_db)

    assert response == {"message": "Sessão encerrada com sucesso."}
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_unit_logout_already_revoked():
    mock_db = AsyncMock()
    raw_token = "already_revoked_logout_token"
    mock_token_record = RefreshToken(
        id=21,
        token_hash=hash_token(raw_token),
        user_id=1,
        expires_at=get_utc_now() + timedelta(days=7),
        revoked=True,
    )
    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = mock_token_record
    mock_db.exec.return_value = mock_exec_result

    request = RefreshTokenRequest(refresh_token=raw_token)
    response = await logout(request=request, db=mock_db)

    assert response == {"message": "Sessão encerrada com sucesso."}
    mock_db.commit.assert_not_awaited()
