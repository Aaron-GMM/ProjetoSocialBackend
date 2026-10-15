import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import settings

TEST_DATABASE_URL = settings.DATABASE_URL

# Garante que use o asyncpg
if TEST_DATABASE_URL.startswith("postgresql://"):
    TEST_DATABASE_URL = TEST_DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://"
    )


@pytest_asyncio.fixture(scope="function")
async def engine():
    """
    Cria o engine assíncrono e cria todas as tabelas antes dos testes.
    Depois, remove todas as tabelas após os testes.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # Habilita a extensão postgis no banco de testes (caso ainda não tenha)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine):
    """
    Fornece uma sessão assíncrona limpa.
    O isolamento é garantido pela recriação do banco a cada teste
    (engine scope=function).
    """
    async with AsyncSession(engine) as session:
        yield session
