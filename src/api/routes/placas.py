from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2 import WKTElement
from sqlalchemy import func, select, true
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.deps import get_current_user
from src.application.schemas.placa_schema import (
    EnderecoResponse,
    EventoPlacaResponse,
    PlacaCreate,
    PlacaListResponse,
    PlacaQueryParams,
    PlacaResponse,
)
from src.domain.enums.placa_enums import TipoEvento
from src.domain.models.endereco import Enderecos
from src.domain.models.eventos_placa import EventosPlaca
from src.domain.models.placa import Placa
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions import placa as placa_functions
from src.infrastructure.database.functions.geo_validator import is_point_in_municipio

QUIXADA_CODIGO_IBGE = "2311306"

router = APIRouter(prefix="/placas", tags=["Placas"])


@router.post(
    "/",
    response_model=PlacaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra uma nova placa",
    description=(
        "Cadastra uma placa a partir de um payload JSON com os dados da placa, "
        "do endereço e do estado de conservação inicial.\n\n"
        "**Regras de Negócio:**\n"
        "- Requer usuário autenticado (Agente ou Administrador).\n"
        "- As coordenadas devem estar dentro do polígono de Quixadá.\n"
        "- A Placa, o Endereço e o evento `CRIACAO` são inseridos em uma única "
        "transação atômica (Append-Only).\n"
        "- O envio de foto ainda não é suportado: `foto_url` fica `null`."
    ),
    response_description="Placa criada com endereço e evento inicial.",
)
async def create_placa(
    placa_create: PlacaCreate,
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    municipio = await placa_functions.get_municipio_by_codigo_ibge(
        db, QUIXADA_CODIGO_IBGE
    )
    if not municipio:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Município de Quixadá não cadastrado.",
        )

    is_inside = await is_point_in_municipio(
        db, placa_create.latitude, placa_create.longitude, municipio.id
    )
    if not is_inside:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="As coordenadas da placa estão fora de Quixadá!",
        )

    placa = Placa(
        codigo_contran=placa_create.codigo_contran,
        afastamento=placa_create.afastamento,
        tipo_pelicula=placa_create.tipo_pelicula,
        tipo_substrato=placa_create.tipo_substrato,
        tipo_suporte=placa_create.tipo_suporte,
        location=WKTElement(
            f"POINT({placa_create.longitude} {placa_create.latitude})", srid=4326
        ),
    )
    endereco = Enderecos(placa_id=placa.id, **placa_create.endereco.model_dump())
    evento = EventosPlaca(
        placa_id=placa.id,
        created_by=current_user.id,
        tipo_evento=TipoEvento.CRIACAO,
        estado_conservacao=placa_create.estado_conservacao,
        estado_pelicula=placa_create.estado_pelicula,
        estado_substrato=placa_create.estado_substrato,
        estado_suporte=placa_create.estado_suporte,
        observacao=placa_create.observacao,
    )
    created_placa = await placa_functions.create_placa(db, placa, endereco, evento)

    return PlacaResponse(
        id=created_placa.id,
        codigo_contran=created_placa.codigo_contran,
        afastamento=created_placa.afastamento,
        tipo_pelicula=created_placa.tipo_pelicula,
        tipo_substrato=created_placa.tipo_substrato,
        tipo_suporte=created_placa.tipo_suporte,
        latitude=placa_create.latitude,
        longitude=placa_create.longitude,
        created_at=created_placa.created_at,
        endereco=EnderecoResponse.model_validate(endereco),
        ultimo_evento=EventoPlacaResponse.model_validate(evento),
    )


@router.get(
    "/",
    response_model=PlacaListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lista placas com filtros e estado atual",
    description=(
        "Recupera uma lista paginada de placas unificando Endereço "
        "e o último EventoPlaca.\n\n"
        "**Recursos e Filtros:**\n"
        "- Bounding Box espacial via `ST_MakeEnvelope` e `ST_Within`.\n"
        "- Lateral Join para evitar o problema de N+1 queries.\n"
        "- Filtros parciais por bairro e logradouro (case-insensitive).\n"
        "- Filtro por estado de conservação atual da placa."
    ),
    response_description="Lista paginada de placas com endereço e último evento.",
)
async def list_placas(
    params: Annotated[PlacaQueryParams, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    ultimo_evento_sub = (
        select(
            EventosPlaca.id.label("ev_id"),
            EventosPlaca.created_by.label("ev_created_by"),
            EventosPlaca.tipo_evento.label("ev_tipo_evento"),
            EventosPlaca.estado_conservacao.label("ev_estado_conservacao"),
            EventosPlaca.estado_pelicula.label("ev_estado_pelicula"),
            EventosPlaca.estado_substrato.label("ev_estado_substrato"),
            EventosPlaca.estado_suporte.label("ev_estado_suporte"),
            EventosPlaca.foto_url.label("ev_foto_url"),
            EventosPlaca.observacao.label("ev_observacao"),
            EventosPlaca.timestamp.label("ev_timestamp"),
        )
        .where(EventosPlaca.placa_id == Placa.id)
        .order_by(EventosPlaca.timestamp.desc())
        .limit(1)
        .correlate(Placa)
        .subquery()
        .lateral("ultimo_evento")
    )

    stmt = (
        select(
            Placa,
            Enderecos,
            func.ST_Y(Placa.location).label("latitude"),
            func.ST_X(Placa.location).label("longitude"),
            ultimo_evento_sub,
        )
        .join(Enderecos, Placa.id == Enderecos.placa_id)
        .outerjoin(ultimo_evento_sub, true())
    )

    if (
        params.min_lng is not None
        and params.min_lat is not None
        and params.max_lng is not None
        and params.max_lat is not None
    ):
        envelope = func.ST_MakeEnvelope(
            params.min_lng,
            params.min_lat,
            params.max_lng,
            params.max_lat,
            4326,
        )
        stmt = stmt.where(func.ST_Within(Placa.location, envelope))

    if params.bairro:
        stmt = stmt.where(Enderecos.bairro.ilike(f"%{params.bairro}%"))
    if params.logradouro:
        stmt = stmt.where(Enderecos.logradouro.ilike(f"%{params.logradouro}%"))
    if params.estado_conservacao:
        stmt = stmt.where(
            ultimo_evento_sub.c.ev_estado_conservacao == params.estado_conservacao
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    offset = (params.page - 1) * params.page_size
    stmt = stmt.order_by(Placa.created_at.desc()).offset(offset).limit(params.page_size)

    result = await session.execute(stmt)
    rows = result.all()

    items: list[PlacaResponse] = []
    for row in rows:
        placa = row[0]
        endereco = row[1]
        lat = row.latitude
        lng = row.longitude

        evento_response = None
        if row.ev_id is not None:
            evento_response = EventoPlacaResponse(
                id=row.ev_id,
                created_by=row.ev_created_by,
                tipo_evento=row.ev_tipo_evento,
                estado_conservacao=row.ev_estado_conservacao,
                estado_pelicula=row.ev_estado_pelicula,
                estado_substrato=row.ev_estado_substrato,
                estado_suporte=row.ev_estado_suporte,
                foto_url=row.ev_foto_url,
                observacao=row.ev_observacao,
                timestamp=row.ev_timestamp,
            )

        items.append(
            PlacaResponse(
                id=placa.id,
                codigo_contran=placa.codigo_contran,
                afastamento=placa.afastamento,
                tipo_pelicula=placa.tipo_pelicula,
                tipo_substrato=placa.tipo_substrato,
                tipo_suporte=placa.tipo_suporte,
                latitude=lat,
                longitude=lng,
                created_at=placa.created_at,
                endereco=EnderecoResponse.model_validate(endereco),
                ultimo_evento=evento_response,
            )
        )

    return PlacaListResponse(
        total=total,
        page=params.page,
        page_size=params.page_size,
        items=items,
    )
