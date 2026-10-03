from sqlmodel import Field, SQLModel

from ..enums.role import Role


class User(SQLModel, table=True):
    """
    Model de usuário do sistema

    Attributes:
        id: ID do usuário
        nome: Nome do usuário
        email: Email do usuário
        password_hash: Hash da senha do usuário
        role: Função do usuário
    """
    __tablename__ = "users"
    
    id: int = Field(
        default=None,
        primary_key=True,
        nullable=False,
        description="ID do usuário"
    )
    nome: str = Field(nullable=False, description="Nome do usuário")
    email: str = Field(
        nullable=False,
        unique=True,
        index=True,
        description="Email do usuário"
    )
    password_hash: str = Field(nullable=False, description="Hash da senha do usuário")
    role: Role = Field(
        nullable=False,
        default=Role.AGENTE,
        description="Função do usuário"
    )