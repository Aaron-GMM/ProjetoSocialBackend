from typing import Any
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import Column
from sqlmodel import Field, SQLModel


class Municipio(SQLModel, table=True):
    __tablename__ = "municipios"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    nome: str = Field(index=True, unique=True)
    codigo_ibge: str = Field(index=True, unique=True)

    # Campo geoespacial. SRID 4326 é o padrão para GPS (Latitude/Longitude).
    # O tipo GEOMETRY aceita Polígonos ou MultiPolígonos.
    poligono: Any = Field(
        sa_column=Column(Geometry("GEOMETRY", srid=4326, spatial_index=False))
    )
