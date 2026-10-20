from datetime import datetime
from uuid import UUID

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

    logradouro: str = Field(
        ..., min_length=1, description="Logradouro", examples=["Rua Basílio Pinto"]
    )
    bairro: str = Field(..., min_length=1, description="Bairro", examples=["Centro"])
    cep: str = Field(..., min_length=1, description="CEP", examples=["63900-000"])
    referencia: str | None = Field(
        None, description="Ponto de referência", examples=["Em frente à praça"]
    )


class PlacaCreate(BaseModel):
    """Schema de criação de placa (Placa + Endereço + Evento inicial)."""

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
    endereco: EnderecoCreate
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


class EnderecoResponse(BaseModel):
    """Schema de resposta do endereço da placa."""

    id: UUID
    logradouro: str
    bairro: str
    cep: str
    referencia: str | None

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
    afastamento: float | None
    tipo_pelicula: TipoPelicula | None
    tipo_substrato: TipoSubstrato | None
    tipo_suporte: TipoSuporte | None
    latitude: float
    longitude: float
    created_at: datetime
    endereco: EnderecoResponse
    ultimo_evento: EventoPlacaResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class PlacaQueryParams(BaseModel):
    """Parâmetros de consulta e filtros para listagem de placas."""

    page: int = Field(default=1, ge=1, description="Número da página")
    page_size: int = Field(default=20, ge=1, le=100, description="Itens por página")

    min_lng: float | None = Field(None, ge=-180, le=180, description="Longitude mínima")
    min_lat: float | None = Field(None, ge=-90, le=90, description="Latitude mínima")
    max_lng: float | None = Field(None, ge=-180, le=180, description="Longitude máxima")
    max_lat: float | None = Field(None, ge=-90, le=90, description="Latitude máxima")

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