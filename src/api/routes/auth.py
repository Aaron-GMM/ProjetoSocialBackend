from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from src.application.schemas.auth_schema import TokenResponse
from src.core.security import create_access_token, verify_password
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions.user import (
    get_user_by_email_case_insensitive,
)

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Realiza login e emite token JWT",
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_session),
) -> TokenResponse:
    """
    Recebe email/senha e retorna o JWT.
    Fluxo:
    1. Chama functions.user.get_user_by_email
    2. Usa core.security.verify_password
    3. Retorna core.security.create_access_token
    """
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
        "role": str(user.role),
    }
    access_token = create_access_token(data=token_payload)

    return TokenResponse(access_token=access_token, token_type="bearer")
