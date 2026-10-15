from typing import TYPE_CHECKING, List

from sqlmodel import Field, Relationship, SQLModel

from ..enums.role import Role

if TYPE_CHECKING:
    from src.domain.models.eventos_placa import EventosPlaca


class User(SQLModel, table=True):
    """
    Model de usuário do sistema

    Attributes:
        id: ID do usuário
        nome: Nome do usuário
        email: Email do usuário
        password_hash: Hash da senha do usuário
        role: Função do usuário
        is_active: Status de atividade do usuário
        eventos_criados: Eventos criados pelo usuário
    """

    __tablename__ = "users"

    id: int = Field(
        default=None, primary_key=True, nullable=False, description="ID do usuário"
    )
    nome: str = Field(nullable=False, description="Nome do usuário")
    email: str = Field(
        nullable=False, unique=True, index=True, description="Email do usuário"
    )
    password_hash: str = Field(nullable=False, description="Hash da senha do usuário")
    role: Role = Field(
        nullable=False, default=Role.AGENTE, description="Função do usuário"
    )
    is_active: bool = Field(
        default=True, nullable=False, description="Status de atividade do usuário"
    )

    eventos_criados: List["EventosPlaca"] = Relationship(
        back_populates="created_by_user"
    )
