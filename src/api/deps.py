from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.security import (
    ALGORITHM,
    PASSWORD_RESET_TOKEN_TYPE,
    SECRET_KEY,
    hash_token,
    validate_access_token,
)
from src.domain.enums.role import Role
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou token expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = validate_access_token(token)
    if user_id is None:
        raise credentials_exception

    user = await db.get(User, user_id)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_from_reset_token(
    token: Annotated[str, Query(description="Token de redefinição de senha")],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Obtém o usuário associado a um token válido de redefinição de senha."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token de redefinição inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("token_type") != PASSWORD_RESET_TOKEN_TYPE:
            raise credentials_exception

        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        user = await db.get(User, int(user_id))
        if user is None:
            raise credentials_exception
    except (JWTError, TypeError, ValueError):
        raise credentials_exception

    # Verificação de usuário inativo tratada separadamente para retornar 403
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo.",
        )

    password_hash = getattr(user, "password_hash", None) or getattr(
        user, "hashed_password", None
    )
    token_fgp = payload.get("pwd_fgp")
    if token_fgp and password_hash:
        if token_fgp != hash_token(password_hash)[:16]:
            raise credentials_exception

    return user


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role != Role.ADMINISTRADOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: requer privilégios de administrador.",
        )
    return current_user
