from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.deps import get_current_user_from_reset_token
from src.application.schemas.auth_schema import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    TokenResponse,
)
from src.core.config import settings
from src.core.security import create_access_token, create_reset_token, verify_password
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
    summary="Realiza login e emite token JWT",
    description=(
        "Endpoint padrão do OAuth2 para autenticação de usuários.\n\n"
        "**Regras de Negócio:**\n"
        "- O frontend deve enviar `username` (email) e `password` no formato "
        "`application/x-www-form-urlencoded`.\n"
        "- Se as credenciais forem válidas, a API emite um `access_token` JWT.\n"
        "- O token contém a `role` e o `sub` (ID do usuário) e deve ser usado nas "
        "requisições subsequentes via cabeçalho `Authorization: Bearer <token>`."
    ),
    response_description="Objeto contendo o Token JWT de Acesso e seu tipo.",
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
    if not user:
        raise unauthorized_exception

    password_hash = getattr(user, "password_hash", None) or getattr(
        user, "hashed_password", None
    )
    if not password_hash or not verify_password(form_data.password, password_hash):
        raise unauthorized_exception

    token_payload = {
        "sub": str(user.id),
        "role": user.role.value,
    }
    access_token = create_access_token(data=token_payload)

    return TokenResponse(access_token=access_token, token_type="bearer")


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Solicita redefinição de senha",
    description=(
        "Inicia o fluxo de recuperação de senha.\n\n"
        "**Regras de Negócio:**\n"
        "- Se o e-mail estiver cadastrado, o backend gera um token JWT de vida "
        "curta (claim `reset_token`) e envia o link de redefinição por e-mail "
        "(envio simulado no console).\n"
        "- A resposta é sempre `200 OK` com uma mensagem genérica, mesmo para "
        "e-mails inexistentes, prevenindo a enumeração de usuários."
    ),
    response_description="Mensagem genérica de confirmação.",
)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ForgotPasswordResponse:
    user = await get_user_by_email_case_insensitive(db=db, email=request.email)
    if user:
        reset_token = create_reset_token(user_id=user.id)
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        send_email(
            recipient=user.email,
            subject="Redefinição de senha - Caça Placa",
            body=(
                f"Olá, {user.nome}!\n\n"
                "Recebemos uma solicitação de redefinição de senha.\n"
                f"Use o link abaixo para definir uma nova senha "
                f"(válido por {settings.RESET_TOKEN_EXPIRE_MINUTES} minutos):\n"
                f"{reset_link}"
            ),
        )

    return ForgotPasswordResponse(
        message=(
            "Se o e-mail estiver cadastrado, você receberá em instantes um link "
            "para redefinir sua senha."
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
