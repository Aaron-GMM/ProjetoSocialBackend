from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from src.domain.models.placa import Placa


class Enderecos(SQLModel, table=True):
    """
    Modelo de representação de um endereço.

    Atributos:
        id (UUID): Identificador único do endereço.
        placa_id (UUID): Identificador da placa.
        logradouro (str): Logradouro do endereço.
        bairro (str): Bairro do endereço.
        cep (str): CEP do endereço.
        referencia (str, opcional): Complemento do endereço.
        placa (Placa): Placa associada ao endereço.
    """

    __tablename__ = "enderecos"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        nullable=False,
        description="ID do endereço",
    )
    placa_id: UUID = Field(
        foreign_key="placas.id",
        unique=True,
        nullable=False,
        ondelete="CASCADE",
        description="Identificador da placa",
    )
    logradouro: str = Field(
        nullable=False,
        description="Logradouro do endereço",
    )
    bairro: str = Field(
        nullable=False,
        description="Bairro do endereço",
    )
    cep: str = Field(
        nullable=False,
        description="CEP do endereço",
    )
    referencia: str | None = Field(
        default=None,
        nullable=True,
        description="Complemento do endereço",
    )

    placa: Placa = Relationship(back_populates="endereco")
