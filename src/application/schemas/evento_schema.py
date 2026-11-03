from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Form, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.domain.enums.placa_enums import EstadoConservacao, TipoEvento


class VistoriaCreate(BaseModel):
    """Schema de criação de um relatório de vistoria em uma placa existente."""

    estado_conservacao: EstadoConservacao
    estado_pelicula: EstadoConservacao | None = None
    estado_substrato: EstadoConservacao | None = None
    estado_suporte: EstadoConservacao | None = None
    observacao: str | None = None

    @classmethod
    def as_form(
        cls,
        estado_conservacao: Annotated[
            EstadoConservacao, Form(description="Estado geral de conservação")
        ],
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
            str | None, Form(description="Observação do agente")
        ] = None,
    ) -> "VistoriaCreate":
        """Constrói o schema VistoriaCreate a partir de campos multipart/form-data."""
        return cls(
            estado_conservacao=estado_conservacao,
            estado_pelicula=estado_pelicula,
            estado_substrato=estado_substrato,
            estado_suporte=estado_suporte,
            observacao=observacao.strip()
            if observacao and observacao.strip()
            else None,
        )


EventoPlacaCreate = VistoriaCreate


class EventoPlacaUpdate(BaseModel):
    """Schema para edição in-place de um evento/relatório da placa (HU-B4)."""

    estado_conservacao: EstadoConservacao | None = Field(
        None, description="Estado geral de conservação retificado"
    )
    estado_pelicula: EstadoConservacao | None = Field(
        None, description="Estado de conservação da película retificado"
    )
    estado_substrato: EstadoConservacao | None = Field(
        None, description="Estado de conservação do substrato retificado"
    )
    estado_suporte: EstadoConservacao | None = Field(
        None, description="Estado de conservação do suporte retificado"
    )
    observacao: str | None = Field(
        None, description="Nova observação retificada pelo agente ou administrador"
    )

    @classmethod
    async def as_form(
        cls,
        request: Request,
        estado_conservacao: Annotated[
            EstadoConservacao | None,
            Form(description="Estado geral de conservação retificado"),
        ] = None,
        estado_pelicula: Annotated[
            EstadoConservacao | None,
            Form(description="Estado de conservação da película retificado"),
        ] = None,
        estado_substrato: Annotated[
            EstadoConservacao | None,
            Form(description="Estado de conservação do substrato retificado"),
        ] = None,
        estado_suporte: Annotated[
            EstadoConservacao | None,
            Form(description="Estado de conservação do suporte retificado"),
        ] = None,
        observacao: Annotated[
            str | None, Form(description="Nova observação retificada")
        ] = None,
    ) -> "EventoPlacaUpdate":
        """Constrói o schema a partir de multipart/form-data ou application/json."""
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                body = await request.json()
                if not isinstance(body, dict):
                    raise RequestValidationError(
                        [
                            {
                                "loc": ("body",),
                                "msg": "JSON inválido",
                                "type": "value_error",
                            }
                        ]
                    )
                if isinstance(body.get("observacao"), str):
                    body["observacao"] = body["observacao"].strip() or None
                return cls.model_validate(body)
            except ValidationError as exc:
                raise RequestValidationError(exc.errors()) from exc

        return cls(
            estado_conservacao=estado_conservacao,
            estado_pelicula=estado_pelicula,
            estado_substrato=estado_substrato,
            estado_suporte=estado_suporte,
            observacao=observacao.strip()
            if observacao and observacao.strip()
            else None,
        )


class EventoPlacaResponse(BaseModel):
    """Schema de resposta de um evento/relatório da placa."""

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


class EventoQueryParams(BaseModel):
    """Parâmetros de paginação para listagem da timeline de eventos."""

    page: int = Field(default=1, ge=1, description="Número da página")
    page_size: int = Field(default=20, ge=1, le=100, description="Itens por página")


class EventoPlacaListResponse(BaseModel):
    """Schema de resposta paginada da listagem de eventos de uma placa."""

    total: int
    page: int
    page_size: int
    items: list[EventoPlacaResponse]

    model_config = ConfigDict(from_attributes=True)


EventoTimelineResponse = EventoPlacaListResponse
