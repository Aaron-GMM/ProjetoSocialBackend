from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Column
from sqlmodel import Field, SQLModel


class DivisaoTerritorial(SQLModel, table=True):
    """
    Limite oficial de bairro ou distrito (malhas do IBGE, Censo 2022).

    Atributos:
        codigo (str): Código IBGE do bairro ou distrito.
        tipo (str): ``bairro`` ou ``distrito``.
        nome (str): Nome oficial.
        codigo_municipio (str): Código IBGE do município.
        sede (bool): Se o distrito é a sede do município.
        geom (Any): MultiPolígono (SRID 4326) com índice espacial GiST.
    """

    __tablename__ = "divisoes_territoriais"

    model_config = {"arbitrary_types_allowed": True}

    codigo: str = Field(primary_key=True, description="Código IBGE")
    tipo: str = Field(nullable=False, description="bairro ou distrito")
    nome: str = Field(nullable=False, description="Nome oficial")
    codigo_municipio: str = Field(
        index=True, nullable=False, description="Código IBGE do município"
    )
    sede: bool = Field(
        default=False, nullable=False, description="Distrito-sede do município"
    )
    geom: Any = Field(
        sa_column=Column(Geometry("MULTIPOLYGON", srid=4326), nullable=False),
    )
