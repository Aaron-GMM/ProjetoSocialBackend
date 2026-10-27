from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Form
from pydantic import BaseModel, ConfigDict, Field

from src.domain.enums.placa_enums import (
    CodigoContran,
    EstadoConservacao,
    TipoEvento,
    TipoPelicula,
    TipoSubstrato,
    TipoSuporte,
)


class EnderecoCreate(BaseModel):
    """Schema do endereço enviado no cadastro de placa."""

    logradouro: str | None = Field(
        None, description="Logradouro", examples=["Rua Basílio Pinto"]
    )
    bairro: str | None = Field(None, description="Bairro", examples=["Centro"])
    cep: str | None = Field(None, description="CEP", examples=["63900-000"])
    referencia: str | None = Field(
        None, description="Ponto de referência", examples=["Em frente à praça"]
    )


class PlacaCreate(BaseModel):
    """Schema de criação de placa (Placa + Endereço opcional + Evento inicial)."""

    codigo_contran: CodigoContran = Field(
        ..., description="Código Contran da placa", examples=["R-1"]
    )
    afastamento: float | None = Field(
        None, ge=0, description="Distância do bordo em metros", examples=[1.5]
    )
    tipo_pelicula: TipoPelicula | None = Field(
        None, description="Tipo de película", examples=["TIPO_I"]
    )
    tipo_substrato: TipoSubstrato | None = Field(
        None, description="Tipo de substrato", examples=["ACO"]
    )
    tipo_suporte: TipoSuporte | None = Field(
        None, description="Tipo de suporte", examples=["POSTE_ACO"]
    )
    latitude: float = Field(
        ..., ge=-90, le=90, description="Latitude (WGS 84)", examples=[-4.9714]
    )
    longitude: float = Field(
        ..., ge=-180, le=180, description="Longitude (WGS 84)", examples=[-39.0154]
    )
    endereco: EnderecoCreate | None = Field(
        None, description="Endereço da placa (opcional)"
    )
    estado_conservacao: EstadoConservacao = Field(
        ..., description="Estado geral de conservação", examples=["BOM"]
    )
    estado_pelicula: EstadoConservacao | None = Field(
        None, description="Estado de conservação da película", examples=["BOM"]
    )
    estado_substrato: EstadoConservacao | None = Field(
        None, description="Estado de conservação do substrato", examples=["REGULAR"]
    )
    estado_suporte: EstadoConservacao | None = Field(
        None, description="Estado de conservação do suporte", examples=["RUIM"]
    )
    observacao: str | None = Field(
        None, description="Observação sobre a placa", examples=["Placa inclinada"]
    )

    @classmethod
    def as_form(
        cls,
        codigo_contran: Annotated[
            CodigoContran, Form(description="Código Contran da placa")
        ],
        latitude: Annotated[
            float, Form(ge=-90, le=90, description="Latitude (WGS 84)")
        ],
        longitude: Annotated[
            float, Form(ge=-180, le=180, description="Longitude (WGS 84)")
        ],
        estado_conservacao: Annotated[
            EstadoConservacao, Form(description="Estado geral de conservação")
        ],
        logradouro: Annotated[str | None, Form(description="Logradouro")] = None,
        bairro: Annotated[str | None, Form(description="Bairro")] = None,
        cep: Annotated[str | None, Form(description="CEP")] = None,
        referencia: Annotated[
            str | None, Form(description="Ponto de referência")
        ] = None,
        afastamento: Annotated[
            float | None, Form(ge=0, description="Distância do bordo em metros")
        ] = None,
        tipo_pelicula: Annotated[
            TipoPelicula | None, Form(description="Tipo de película")
        ] = None,
        tipo_substrato: Annotated[
            TipoSubstrato | None, Form(description="Tipo de substrato")
        ] = None,
        tipo_suporte: Annotated[
            TipoSuporte | None, Form(description="Tipo de suporte")
        ] = None,
        estado_pelicula: Annotated[
            EstadoConservacao | None,
            Form(description="Estado de conservação da película"),
        ] = None,
        estado_substrato: Annotated[
            EstadoConservacao | None,
            Form(description="Estado de conservação do substrato"),
        ] = None,
        estado_suporte: Annotated[
            EstadoConservacao | None,
            Form(description="Estado de conservação do suporte"),
        ] = None,
        observacao: Annotated[
            str | None, Form(description="Observação sobre a placa")
        ] = None,
    ) -> "PlacaCreate":
        """Constrói o schema PlacaCreate a partir de campos multipart/form-data."""
        has_endereco = any(
            v is not None and v.strip() != ""
            for v in (logradouro, bairro, cep, referencia)
        )

        def clean_str(val: str | None) -> str | None:
            return val.strip() if val and val.strip() else None

        endereco_obj = (
            EnderecoCreate(
                logradouro=clean_str(logradouro),
                bairro=clean_str(bairro),
                cep=clean_str(cep),
                referencia=clean_str(referencia),
            )
            if has_endereco
            else None
        )
        return cls(
            codigo_contran=codigo_contran,
            afastamento=afastamento,
            tipo_pelicula=tipo_pelicula,
            tipo_substrato=tipo_substrato,
            tipo_suporte=tipo_suporte,
            latitude=latitude,
            longitude=longitude,
            endereco=endereco_obj,
            estado_conservacao=estado_conservacao,
            estado_pelicula=estado_pelicula,
            estado_substrato=estado_substrato,
            estado_suporte=estado_suporte,
            observacao=observacao,
        )


class EnderecoResponse(BaseModel):
    """Schema de resposta do endereço da placa."""

    id: UUID
    logradouro: str | None = None
    bairro: str | None = None
    cep: str | None = None
    referencia: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EventoPlacaResponse(BaseModel):
    """Schema de resposta de um evento da placa."""

    id: UUID
    created_by: int
    tipo_evento: TipoEvento
    estado_conservacao: EstadoConservacao
    estado_pelicula: EstadoConservacao | None
    estado_substrato: EstadoConservacao | None
    estado_suporte: EstadoConservacao | None
    foto_url: str | None
    observacao: str | None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class PlacaResponse(BaseModel):
    """Schema de resposta da placa com endereço e evento mais recente."""

    id: UUID
    codigo_contran: CodigoContran
    descricao_contran: str | None = Field(
        None,
        description="Descrição oficial CONTRAN da placa",
        examples=["Parada Obrigatória (PARE)"],
    )
    afastamento: float | None
    tipo_pelicula: TipoPelicula | None
    tipo_substrato: TipoSubstrato | None
    tipo_suporte: TipoSuporte | None
    latitude: float
    longitude: float
    created_at: datetime
    endereco: EnderecoResponse | None = None
    ultimo_evento: EventoPlacaResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class PlacaTipoItem(BaseModel):
    """Item descritivo do catálogo de tipos/códigos de placas CONTRAN."""

    codigo: str = Field(..., description="Código oficial CONTRAN", examples=["R-1"])
    descricao: str = Field(
        ...,
        description="Significado oficial da placa",
        examples=["Parada Obrigatória (PARE)"],
    )


class PlacaQueryParams(BaseModel):
    """Parâmetros de consulta e filtros de negócio para listagem de placas."""

    page: int = Field(default=1, ge=1, description="Número da página")
    page_size: int = Field(default=20, ge=1, le=100, description="Itens por página")

    codigo_contran: str | None = Field(
        None,
        description="Filtro por código ou tipo da placa (ex: 'R-1', 'R1', 'PARE')",
        examples=["R-1", "PARE"],
    )
    bairro: str | None = Field(None, description="Filtro parcial por bairro")
    logradouro: str | None = Field(None, description="Filtro parcial por logradouro")
    estado_conservacao: EstadoConservacao | None = Field(
        None, description="Filtro pelo estado de conservação atual"
    )


class PlacaListResponse(BaseModel):
    """Schema de resposta paginada da listagem de placas."""

    total: int
    page: int
    page_size: int
    items: list[PlacaResponse]

    model_config = ConfigDict(from_attributes=True)
