from datetime import datetime
from typing import TYPE_CHECKING, List
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlmodel import Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from src.domain.models.endereco import Enderecos
    from src.domain.models.eventos_placa import EventosPlaca


class Placa(SQLModel, table=True):
    """
    Modelo de representação de uma placa.

    Atributos:
        id (UUID): Identificador único da placa.
        codigo_contran (str): Código Contran.
        afastamento (float, opcional): Valor do afastamento.
        tipo_pelicula (str, opcional): Tipo de película.
        tipo_substrato (str, opcional): Tipo de substrato.
        tipo_suporte (str, opcional): Tipo de suporte.
        location (Geometry): Localização geográfica da placa.
        created_at (datetime): Data e hora de criação da placa.
        endereco (Enderecos): Endereço da placa.
        eventos (List[EventosPlaca]): Eventos da placa.
    """

    __tablename__ = "placas"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Identificador único da placa",
    )
    codigo_contran: str = Field(index=True, unique=True, description="Código Contran")
    afastamento: float = Field(nullable=True, description="Valor do afastamento")
    tipo_pelicula: str = Field(nullable=True, description="Tipo de película")
    tipo_substrato: str = Field(nullable=True, description="Tipo de substrato")
    tipo_suporte: str = Field(nullable=True, description="Tipo de suporte")
    location: Geometry = Field(
        sa_column=Column(Geometry("POINT", srid=4326)),
        description="Localização geográfica da placa",
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        nullable=False,
        description="Data e hora de criação da placa",
    )

    endereco: "Enderecos" = Relationship(back_populates="placa")
    eventos: List["EventosPlaca"] = Relationship(back_populates="placa")
