from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, func
from sqlmodel import Column, Field, Relationship, SQLModel

from src.domain.enums.placa_enums import EstadoConservacao, TipoEvento

if TYPE_CHECKING:
    from src.domain.models.placa import Placa
    from src.domain.models.user import User


class EventosPlaca(SQLModel, table=True):
    """
    Modelo de representação de um evento de placa (Histórico/Vistoria).

    Atributos:
        id (UUID): Identificador único do evento.
        placa_id (UUID): Identificador da placa.
        created_by (int): Identificador do usuário que criou o evento.
        tipo_evento (TipoEvento): Tipo do evento (CRIACAO, VISTORIA, DELECAO).
        estado_conservacao (EstadoConservacao): Estado geral de conservação da placa.
        estado_pelicula (EstadoConservacao, opcional): Estado da película.
        estado_substrato (EstadoConservacao, opcional): Estado do substrato.
        estado_suporte (EstadoConservacao, opcional): Estado do suporte.
        foto_url (str, opcional): URL/Caminho da foto do evento no MinIO.
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
        foreign_key="placas.id",
        nullable=False,
        ondelete="CASCADE",
        description="Identificador da placa",
    )
    created_by: int = Field(
        foreign_key="users.id",
        nullable=False,
        description="Identificador do usuário que criou o evento",
    )
    tipo_evento: TipoEvento = Field(description="Tipo do evento")
    estado_conservacao: EstadoConservacao = Field(
        description="Estado geral de conservação da placa"
    )
    estado_pelicula: EstadoConservacao | None = Field(
        default=None,
        nullable=True,
        description="Estado de conservação da película",
    )
    estado_substrato: EstadoConservacao | None = Field(
        default=None,
        nullable=True,
        description="Estado de conservação do substrato",
    )
    estado_suporte: EstadoConservacao | None = Field(
        default=None,
        nullable=True,
        description="Estado de conservação do suporte",
    )
    foto_url: str | None = Field(
        default=None,
        nullable=True,
        description="URL da foto do evento",
    )
    observacao: str | None = Field(
        default=None,
        nullable=True,
        description="Observação sobre o evento",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        description="Data e hora do evento",
    )

    placa: Placa = Relationship(back_populates="eventos")
    created_by_user: User = Relationship(back_populates="eventos_criados")
