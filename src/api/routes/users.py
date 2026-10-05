from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.deps import get_current_user, require_admin
from src.application.schemas.user_schema import UserResponse, UserUpdate, UserUpdateMe
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions import user as user_functions

router = APIRouter(prefix="/users", tags=["Usuários"])


@router.get("/me", response_model=UserResponse)
async def get_users_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Retorna os dados do próprio usuário logado.
    """
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_users_me(
    user_update: UserUpdateMe,
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Atualiza os próprios dados do usuário logado (ex: nome, email).
    """
    updated_user = await user_functions.update_user_partial(
        db, current_user.id, user_update.model_dump(exclude_unset=True)
    )
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Erro ao atualizar usuário."
        )

    return updated_user


@router.get("/", response_model=list[UserResponse])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_admin)],
    skip: int = Query(0, ge=0, description="Número de registros para pular"),
    limit: int = Query(100, ge=1, le=1000, description="Número máximo de registros"),
):
    """
    Retorna a lista de usuários paginada. (Apenas ADMs)
    """
    return await user_functions.get_all_users_paginated(db, skip=skip, limit=limit)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """
    Atualiza dados específicos de um usuário ou desativa a conta.
    """
    db_user = await user_functions.get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado."
        )

    updated_user = await user_functions.update_user_partial(
        db, user_id, user_update.model_dump(exclude_unset=True)
    )
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Erro ao atualizar usuário."
        )

    return updated_user
