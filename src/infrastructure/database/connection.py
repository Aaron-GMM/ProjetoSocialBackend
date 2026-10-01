from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import settings

# Ajusta a URL de postgresql:// para postgresql+asyncpg://
url = str(settings.DATABASE_URL)
if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(url, echo=True)


async def get_session() -> AsyncSession:
    """Dependência do FastAPI para injeção da sessão assíncrona do banco."""
    async with AsyncSession(engine) as session:
        yield session
