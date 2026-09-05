from sqlmodel import Session, create_engine

from src.core.config import settings

# Em produção, echo deve ser False
engine = create_engine(settings.DATABASE_URL, echo=True)


def get_session():
    """Dependência do FastAPI para injeção da sessão do banco."""
    with Session(engine) as session:
        yield session
