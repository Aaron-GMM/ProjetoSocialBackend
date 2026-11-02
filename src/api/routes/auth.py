from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.deps import get_current_user_from_reset_token
from src.application.schemas.auth_schema import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from src.core.config import settings
from src.core.security import (
    create_access_token,
    create_reset_token,
    generate_refresh_token_string,
    hash_token,
    verify_password,
)
from src.domain.models.refresh_token import RefreshToken
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions.user import (
    change_user_password,
    get_user_by_email_case_insensitive,
)
from src.infrastructure.services.email import send_email

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Realiza login e emite access e refresh token",
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    unauthorized_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="E-mail ou senha incorretos.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = await get_user_by_email_case_insensitive(db=db, email=form_data.username)
    if not user or not user.is_active:
        raise unauthorized_exception

    password_hash = getattr(user, "password_hash", None) or getattr(
        user, "hashed_password", None
    )
    if not password_hash or not verify_password(form_data.password, password_hash):
        raise unauthorized_exception

    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )

    raw_refresh_token = generate_refresh_token_string()
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    db_refresh_token = RefreshToken(
        token_hash=hash_token(raw_refresh_token),
        user_id=user.id,
        expires_at=expires_at,
        revoked=False,
    )
    db.add(db_refresh_token)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        token_type="bearer",
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renova tokens via refresh token rotation",
)
async def refresh_tokens(
    request: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    unauthorized_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token inválido, expirado ou revogado.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_h = hash_token(request.refresh_token)

    statement = select(RefreshToken).where(RefreshToken.token_hash == token_h)
    result = await db.exec(statement)
    token_record = result.first()

    if not token_record:
        raise unauthorized_exception

    now = datetime.now(timezone.utc)

    token_expires = (
        token_record.expires_at.replace(tzinfo=timezone.utc)
        if token_record.expires_at.tzinfo is None
        else token_record.expires_at
    )

    if token_record.revoked or token_expires < now:
        raise unauthorized_exception

    user = await db.get(User, token_record.user_id)
    if not user or not user.is_active:
        raise unauthorized_exception

    token_record.revoked = True
    db.add(token_record)

    new_access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )
    new_raw_refresh = generate_refresh_token_string()
    new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    new_db_token = RefreshToken(
        token_hash=hash_token(new_raw_refresh),
        user_id=user.id,
        expires_at=new_expires_at,
        revoked=False,
    )
    db.add(new_db_token)
    await db.commit()

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_raw_refresh,
        token_type="bearer",
    )


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Solicita redefinição de senha",
    description=(
        "Inicia o fluxo de recuperação de senha.\n\n"
        "**Regras de Negócio:**\n"
        "- Se o e-mail estiver cadastrado, o backend gera um token JWT de vida "
        "curta (claim `token_type=password_reset`) e envia o link de redefinição "
        "por e-mail via SMTP.\n"
        "- A resposta de sucesso contém uma mensagem genérica, mesmo para "
        "e-mails inexistentes, prevenindo a enumeração de usuários.\n"
        "- Falhas na configuração ou no envio SMTP são propagadas como erro."
    ),
    response_description="Mensagem genérica de confirmação.",
)
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ForgotPasswordResponse:
    user = await get_user_by_email_case_insensitive(
        db=db,
        email=request.email,
    )

    if user:
        reset_token = create_reset_token(user_id=user.id)
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

        background_tasks.add_task(
            send_email,
            recipient=user.email,
            subject="Redefinição de senha - Caça Placa",
            body=(
                f"Olá, {user.nome}!\n\n"
                "Recebemos uma solicitação de redefinição de senha.\n"
                "Use o link abaixo para definir uma nova senha "
                f"(válido por {settings.RESET_TOKEN_EXPIRE_MINUTES} minutos):\n"
                f"{reset_link}"
            ),
        )

    return ForgotPasswordResponse(
        message=(
            "Se o e-mail estiver cadastrado, você receberá em instantes "
            "um link para redefinir sua senha."
        )
    )


@router.post(
    "/reset-password",
    summary="Redefine a senha do usuário com um token válido",
)
async def reset_password(
    request: ResetPasswordRequest,
    current_user: Annotated[User, Depends(get_current_user_from_reset_token)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    await change_user_password(
        new_password=request.new_password,
        user=current_user,
        db=db,
    )
    return {"message": "Senha redefinida com sucesso."}
