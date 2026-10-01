from uuid import UUID

from sqlmodel import Session

# from src.domain.models.user import User


def get_user_by_email(db: Session, email: str):
    """Busca um usuário no banco pelo email."""
    pass  # TODO Equipe: Fazer o select(User).where(...) e retornar .first()


def get_user_by_id(db: Session, user_id: UUID):
    """Busca um usuário pelo UUID."""
    pass  # TODO Equipe: Implementar


def create_user(db: Session, user_data):
    """Insere um novo usuário no banco."""
    pass  # TODO Equipe: Montar o fluxo de db.add() e db.commit()
