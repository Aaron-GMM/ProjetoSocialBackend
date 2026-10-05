from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.deps import get_current_user, require_admin
from src.application.schemas.user_schema import (
    UserCreate,
    UserResponse,
    UserUpdate,
    UserUpdateMe,
)
from src.core.security import generate_random_password, get_password_hash
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions import user as user_functions
from src.infrastructure.services.email import send_email

router = APIRouter(prefix="/users", tags=["Usuários"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Obtém o perfil do usuário logado",
    description=(
        "Retorna as informações do usuário atual com base no token JWT fornecido "
        "no header `Authorization`.\n\n"
        "**Uso no Frontend:**\n"
        "- Ideal para carregar os dados iniciais do usuário e exibir na barra de "
        "navegação ou perfil."
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
        "- Por questões de segurança, um usuário normal **não pode** alterar sua "
        "própria `role` ou o status `is_active` por aqui.\n"
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


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra um novo usuário com senha gerada (Apenas ADMIN)",
    description=(
        "Cria a conta de um novo Agente a partir de nome e e-mail.\n\n"
        "**Regras de Negócio:**\n"
        "- Requer nível de acesso `ADMINISTRADOR`.\n"
        "- A senha **não** vem no request: o backend gera uma senha forte "
        "aleatória, persiste apenas o seu hash e a envia por e-mail ao novo "
        "usuário (envio simulado no console).\n"
        "- A resposta **nunca** retorna a senha em texto plano."
    ),
    response_description="Dados do usuário criado (sem senha).",
)
async def create_user(
    user_create: UserCreate,
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_admin)],
):
    existing_user = await user_functions.get_user_by_email_case_insensitive(
        db, user_create.email
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um usuário cadastrado com este e-mail.",
        )

    raw_password = generate_random_password()
    new_user = User(
        nome=user_create.nome,
        email=user_create.email,
        password_hash=get_password_hash(raw_password),
    )
    created_user = await user_functions.create_user(db, new_user)

    send_email(
        recipient=created_user.email,
        subject="Sua conta no Caça Placa foi criada",
        body=(
            f"Olá, {created_user.nome}!\n\n"
            f"Sua senha temporária é: {raw_password}\n"
            "Altere-a no seu primeiro acesso."
        ),
    )

    return created_user


@router.get(
    "/",
    response_model=list[UserResponse],
    summary="Lista todos os usuários (Paginação)",
    description=(
        "Retorna uma lista paginada de todos os usuários cadastrados no sistema.\n\n"
        "**Controle de Acesso:**\n"
        "- Requer nível de acesso `ADMINISTRADOR`.\n\n"
        "**Uso no Frontend:**\n"
        "- Utilize os parâmetros `skip` e `limit` para construir tabelas com "
        "paginação (ex: páginas de 20 em 20 itens)."
    ),
    response_description="Lista de usuários cadastrados.",
)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_admin)],
    skip: int = Query(0, ge=0, description="Número de registros para pular (Offset)"),
    limit: int = Query(
        100, ge=1, le=1000, description="Quantidade máxima de registros por página"
    ),
):
    return await user_functions.get_all_users_paginated(db, skip=skip, limit=limit)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Atualiza dados de um usuário específico (Apenas ADMIN)",
    description=(
        "Permite que um Administrador atualize os dados de qualquer usuário do "
        "sistema, incluindo suas permissões.\n\n"
        "**Controle de Acesso:**\n"
        "- Requer nível de acesso `ADMINISTRADOR`.\n\n"
        "**Ações Comuns:**\n"
        "- **Desativação:** Para desativar a conta de um usuário "
        '(soft-delete lógico), envie `{"is_active": false}`.\n'
        "- **Promoção:** Para promover um agente a admin, envie "
        '`{"role": "ADMINISTRADOR"}`.'
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
    ],
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
