from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import settings

# Ajusta a URL de postgresql:// para postgresql+asyncpg://
url = str(settings.DATABASE_URL)
if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(url, echo=True)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """Dependência do FastAPI para injeção da sessão assíncrona do banco."""
    async with async_session() as session:
        yield session
