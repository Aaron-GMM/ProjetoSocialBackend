from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Column
from sqlmodel import Field, SQLModel


class EnderecoReferencia(SQLModel, table=True):
    """
    Endereço oficial de referência (CNEFE/IBGE, Censo 2022) usado na
    geocodificação reversa local.

    Atributos:
        cod_unico_endereco (int): Código único do endereço no CNEFE.
        codigo_municipio (str): Código IBGE do município.
        codigo_distrito (str): Código IBGE do distrito.
        logradouro (str, opcional): Logradouro formatado para exibição.
        localidade (str, opcional): Localidade registrada pelo recenseador
            (pode ser loteamento, residencial ou fazenda).
        bairro_correios (str, opcional): Bairro dos Correios para o CEP, já
            validado contra a lista de bairros oficiais.
        bairro (str, opcional): Bairro oficial resolvido pelo seed (limite do
            IBGE, Correios ou distrito, ver ``resolver_bairros``).
        cep (str, opcional): CEP no formato 00000-000.
        cidade (str): Nome do município.
        estado (str): Nome do estado.
        location (Any): Ponto do endereço (SRID 4326) com índice espacial GiST.
    """

    __tablename__ = "enderecos_referencia"

    model_config = {"arbitrary_types_allowed": True}

    cod_unico_endereco: int = Field(
        sa_column=Column(BigInteger, primary_key=True, autoincrement=False),
        description="Código único do endereço no CNEFE",
    )
    codigo_municipio: str = Field(
        index=True, nullable=False, description="Código IBGE do município"
    )
    codigo_distrito: str = Field(
        index=True, nullable=False, description="Código IBGE do distrito"
    )
    logradouro: str | None = Field(default=None, description="Logradouro")
    localidade: str | None = Field(default=None, description="Localidade (CNEFE)")
    bairro_correios: str | None = Field(
        default=None, description="Bairro oficial segundo os Correios"
    )
    bairro: str | None = Field(default=None, description="Bairro oficial")
    cep: str | None = Field(default=None, description="CEP (00000-000)")
    cidade: str = Field(nullable=False, description="Município")
    estado: str = Field(nullable=False, description="Estado")
    location: Any = Field(
        sa_column=Column(Geometry("POINT", srid=4326), nullable=False),
    )
