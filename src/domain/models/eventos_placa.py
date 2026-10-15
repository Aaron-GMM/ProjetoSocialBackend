from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from src.domain.models.placa import Placa
    from src.domain.models.user import User


class TipoEvento(str, Enum):
    CRIACAO = "CRIACAO"
    VISTORIA = "VISTORIA"
    DELECAO = "DELECAO"


class EstadoConservacao(str, Enum):
    BOM = "BOM"
    REGULAR = "REGULAR"
    RUIM = "RUIM"


class EventosPlaca(SQLModel, table=True):
    """
    Modelo de representação de um evento de placa.

    Atributos:
        id (UUID): Identificador único do evento.
        placa_id (UUID): Identificador da placa.
        created_by (UUID): Identificador do usuário que criou o evento.
        tipo_evento (TipoEvento): Tipo do evento.
        estado_conservacao (EstadoConservacao): Estado de conservação da placa.
        foto_url (str, opcional): URL da foto do evento.
        observacao (str, opcional): Observação sobre o evento.
        timestamp (datetime): Data e hora do evento.
        placa (Placa): Placa associada ao evento.
        created_by_user (User): Usuário que criou o evento.
    """

    __tablename__ = "eventos_placa"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Identificador único do evento",
    )
    placa_id: UUID = Field(
        foreign_key="placas.id", description="Identificador da placa"
    )
    created_by: int = Field(
        foreign_key="users.id",
        description="Identificador do usuário que criou o evento",
    )
    tipo_evento: TipoEvento = Field(description="Tipo do evento")
    estado_conservacao: EstadoConservacao = Field(
        description="Estado de conservação da placa"
    )
    foto_url: str = Field(default=None, description="URL da foto do evento")
    observacao: str = Field(default=None, description="Observação sobre o evento")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        nullable=False,
        description="Data e hora do evento",
    )

    placa: "Placa" = Relationship(back_populates="eventos")
    created_by_user: "User" = Relationship(back_populates="eventos_criados")
