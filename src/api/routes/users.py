from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.deps import get_current_user, require_admin
from src.application.schemas.user_schema import UserResponse, UserUpdate, UserUpdateMe
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions import user as user_functions

router = APIRouter(prefix="/users", tags=["Usuários"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Obtém o perfil do usuário logado",
    description=(
        "Retorna as informações do usuário atual com base no token JWT fornecido no header `Authorization`.\n\n"  # noqa: E501
        "**Uso no Frontend:**\n"
        "- Ideal para carregar os dados iniciais do usuário e exibir na barra de navegação ou perfil."  # noqa: E501
    ),
    response_description="Dados completos do usuário logado (exceto senha).",
)
async def get_users_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Atualiza o perfil do usuário logado",
    description=(
        "Permite que o usuário logado atualize seus próprios dados cadastrais.\n\n"
        "**Regras:**\n"
        "- Apenas os campos enviados no corpo da requisição serão atualizados.\n"
        "- Por questões de segurança, um usuário normal **não pode** alterar sua própria `role` ou o status `is_active` por aqui.\n"  # noqa: E501
    ),
    response_description="Dados do usuário logado após a atualização.",
)
async def update_users_me(
    user_update: UserUpdateMe,
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    updated_user = await user_functions.update_user_partial(
        db, current_user.id, user_update.model_dump(exclude_unset=True)
    )
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Erro ao atualizar usuário."
        )

    return updated_user


@router.get(
    "/",
    response_model=list[UserResponse],
    summary="Lista todos os usuários (Paginação)",
    description=(
        "Retorna uma lista paginada de todos os usuários cadastrados no sistema.\n\n"
        "**Controle de Acesso:**\n"
        "- Requer nível de acesso `ADMINISTRADOR`.\n\n"
        "**Uso no Frontend:**\n"
        "- Utilize os parâmetros `skip` e `limit` para construir tabelas com paginação (ex: páginas de 20 em 20 itens)."  # noqa: E501
    ),
    response_description="Lista de usuários cadastrados.",
)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_admin)],
    skip: int = Query(0, ge=0, description="Número de registros para pular (Offset)"),
    limit: int = Query(
        100, ge=1, le=1000, description="Quantidade máxima de registros por página"
    ),  # noqa: E501
):
    return await user_functions.get_all_users_paginated(db, skip=skip, limit=limit)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Atualiza dados de um usuário específico (Apenas ADMIN)",
    description=(
        "Permite que um Administrador atualize os dados de qualquer usuário do sistema, incluindo suas permissões.\n\n"  
        "**Controle de Acesso:**\n"
        "-  Requer nível de acesso `ADMINISTRADOR`.\n\n"
        "**Ações Comuns:**\n"
        '-  **Desativação:** Para desativar a conta de um usuário (soft-delete lógico), envie `{"is_active": false}`.\n'  
        '-  **Promoção:** Para promover um agente a admin, envie `{"role": "ADMINISTRADOR"}`.'
    ),
    response_description="Usuário com os dados atualizados.",
)
async def update_user(
    user_id: Annotated[
        int,
        Path(
            title="ID do Usuário",
            description="O ID numérico do usuário a ser atualizado.",
        ),
    ],  # noqa: E501
    user_update: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_admin)],
):
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
