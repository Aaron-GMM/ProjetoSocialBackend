from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import String
from sqlmodel import Column, Field, Relationship, SQLModel

from src.domain.enums.placa_enums import (
    CodigoContran,
    TipoPelicula,
    TipoSubstrato,
    TipoSuporte,
)
from src.domain.models.endereco import Enderecos
from src.domain.models.eventos_placa import EventosPlaca


class Placa(SQLModel, table=True):
    """
    Modelo de representação de uma placa.

    Atributos:
        id (UUID): Identificador único da placa.
        codigo_contran (CodigoContran): Código Contran da placa (ex: R-1).
        afastamento (float, opcional): Distância do bordo em metros.
        tipo_pelicula (TipoPelicula, opcional): Tipo de película.
        tipo_substrato (TipoSubstrato, opcional): Tipo de substrato.
        tipo_suporte (TipoSuporte, opcional): Tipo de suporte.
        location (Any): Localização geográfica da placa (Point, SRID 4326).
        created_at (datetime): Data e hora de criação da placa.
        endereco (Enderecos, opcional): Endereço da placa (relação 1:1).
        eventos (list[EventosPlaca]): Histórico de eventos da placa (relação 1:N).
    """

    __tablename__ = "placas"

    model_config = {"arbitrary_types_allowed": True}

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Identificador único da placa",
    )
    codigo_contran: CodigoContran = Field(
        sa_column=Column(String, index=True, nullable=False),
        description="Código Contran (Ex: R-1, A-2a)",
    )
    afastamento: float | None = Field(
        default=None,
        nullable=True,
        description="Valor do afastamento em metros",
    )
    tipo_pelicula: TipoPelicula | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
        description="Tipo de película",
    )
    tipo_substrato: TipoSubstrato | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
        description="Tipo de substrato",
    )
    tipo_suporte: TipoSuporte | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
        description="Tipo de suporte",
    )
    location: Any = Field(
        sa_column=Column(Geometry("POINT", srid=4326)),
        description="Localização geográfica da placa",
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        nullable=False,
        description="Data e hora de criação da placa",
    )

    endereco: Enderecos | None = Relationship(
        back_populates="placa",
        sa_relationship_kwargs={
            "uselist": False,
            "cascade": "all, delete-orphan",
        },
    )
    eventos: list[EventosPlaca] = Relationship(
        back_populates="placa",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
