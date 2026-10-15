from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.security import get_password_hash
from src.domain.models.user import User


async def get_user_by_email_case_insensitive(
    db: AsyncSession, email: str
) -> User | None:
    """Busca um usuário no banco pelo email."""
    statement = select(User).where(func.lower(User.email) == func.lower(email))
    result = await db.exec(statement)
    return result.first()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Busca um usuário pelo ID."""
    statement = select(User).where(User.id == user_id)
    result = await db.exec(statement)
    return result.first()


async def create_user(db: AsyncSession, user: User) -> User:
    """Insere um novo usuário no banco."""
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


async def get_all_users(db: AsyncSession) -> list[User]:
    """Retorna todos os usuários."""
    statement = select(User)
    result = await db.exec(statement)
    return result.all()


async def get_all_users_paginated(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> list[User]:
    """Retorna todos os usuários com paginação."""
    statement = select(User).offset(skip).limit(limit)
    result = await db.exec(statement)
    return result.all()


async def update_user(db: AsyncSession, user_id: int, user_data: User) -> User | None:
    """Atualiza um usuário no banco."""
    statement = select(User).where(User.id == user_id)
    result = await db.exec(statement)
    user = result.first()

    if user:
        for key, value in user_data.model_dump().items():
            setattr(user, key, value)
        await db.commit()
        await db.refresh(user)

    return user


async def update_user_partial(
    db: AsyncSession, user_id: int, user_data: dict
) -> User | None:
    """Atualiza parcialmente um usuário no banco."""
    statement = select(User).where(User.id == user_id)
    result = await db.exec(statement)
    user = result.first()

    if user:
        for key, value in user_data.items():
            setattr(user, key, value)
        await db.commit()
        await db.refresh(user)

    return user


async def delete_user(db: AsyncSession, user_id: int) -> bool:
    """Deleta um usuário do banco."""
    statement = select(User).where(User.id == user_id)
    result = await db.exec(statement)
    user = result.first()

    if user:
        await db.delete(user)
        await db.commit()
        return True

    return False


async def change_user_password(new_password: str, user: User, db: AsyncSession):
    """Atualiza a senha do usuário armazenando apenas o hash."""
    hashed_password = get_password_hash(new_password)
    user.password_hash = hashed_password

    db.add(user)
    await db.commit()
