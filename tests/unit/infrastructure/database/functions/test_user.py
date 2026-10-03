import pytest

from src.domain.enums.role import Role
from src.domain.models.user import User
from src.infrastructure.database.functions.user import (
    create_user,
    delete_user,
    get_all_users,
    get_all_users_paginated,
    get_user_by_email_case_insensitive,
    get_user_by_id,
    update_user,
)


@pytest.mark.asyncio
async def test_get_all_users(db_session):
    # Arrange
    user = User(
        nome="John Doe",
        email="john.doe@example.com",
        password_hash="password_hashed",
    )
    user = await create_user(db_session, user)

    # Act
    response = await get_all_users(db_session)

    # Assert
    assert len(response) == 1
    assert response[0].nome == "John Doe"
    assert response[0].email == "john.doe@example.com"
    assert response[0].role == Role.AGENTE
    assert response[0].id == user.id


@pytest.mark.asyncio
async def test_get_all_users_paginated(db_session):
    # Arrange
    user = User(
        nome="John Doe",
        email="john.doe@example.com",
        password_hash="password_hashed",
    )
    user = await create_user(db_session, user)

    # Act
    response = await get_all_users_paginated(db_session, 0, 10)

    # Assert
    assert len(response) == 1
    assert response[0].nome == "John Doe"
    assert response[0].email == "john.doe@example.com"
    assert response[0].role == Role.AGENTE
    assert response[0].id == user.id


@pytest.mark.asyncio
async def test_create_user(db_session):
    # Arrange
    user = User(
        nome="John Doe",
        email="john.doe@example.com",
        password_hash="password_hashed",
    )

    # Act
    response = await create_user(db_session, user)

    # Assert
    assert response.nome == "John Doe"
    assert response.email == "john.doe@example.com"
    assert response.role == Role.AGENTE
    assert response.id is not None


@pytest.mark.asyncio
async def test_get_user_by_email(db_session):
    # Arrange
    user = User(
        nome="John Doe",
        email="john.doe@example.com",
        password_hash="password_hashed",
    )
    user = await create_user(db_session, user)

    # Act
    response = await get_user_by_email_case_insensitive(
        db_session, "john.doe@example.com"
    )

    # Assert
    assert response.nome == "John Doe"
    assert response.email == "john.doe@example.com"
    assert response.role == Role.AGENTE
    assert response.id == user.id


@pytest.mark.asyncio
async def test_get_user_by_id(db_session):
    # Arrange
    user = User(
        nome="John Doe",
        email="john.doe@example.com",
        password_hash="password_hashed",
    )
    user = await create_user(db_session, user)

    # Act
    response = await get_user_by_id(db_session, user.id)

    # Assert
    assert response.nome == "John Doe"
    assert response.email == "john.doe@example.com"
    assert response.role == Role.AGENTE
    assert response.id == user.id


@pytest.mark.asyncio
async def test_update_user(db_session):
    # Arrange
    user = User(
        nome="John Doe",
        email="john.doe@example.com",
        password_hash="password_hashed",
    )
    user = await create_user(db_session, user)

    # Act
    user.nome = "Jane Doe"
    user.email = "jane.doe@example.com"
    user = await update_user(db_session, user.id, user)

    # Assert
    assert user.nome == "Jane Doe"
    assert user.email == "jane.doe@example.com"
    assert user.role == Role.AGENTE
    assert user.id == user.id


@pytest.mark.asyncio
async def test_delete_user(db_session):
    # Arrange
    user = User(
        nome="John Doe",
        email="john.doe@example.com",
        password_hash="password_hashed",
    )
    user = await create_user(db_session, user)

    # Act
    response = await delete_user(db_session, user.id)
    response2 = await delete_user(db_session, user.id)

    # Assert
    assert response is True
    assert response2 is False
