from typing import Any

from sqlalchemy import func, true
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.application.schemas.placa_schema import PlacaQueryParams
from src.domain.models.endereco import Enderecos
from src.domain.models.eventos_placa import EventosPlaca
from src.domain.models.municipio import Municipio
from src.domain.models.placa import Placa


async def get_municipio_by_codigo_ibge(
    db: AsyncSession, codigo_ibge: str
) -> Municipio | None:
    """Busca um município pelo código IBGE."""
    statement = select(Municipio).where(Municipio.codigo_ibge == codigo_ibge)
    result = await db.exec(statement)
    return result.first()


async def create_placa(
    db: AsyncSession, placa: Placa, endereco: Enderecos, evento: EventosPlaca
) -> Placa:
    """Insere a placa, seu endereço e o evento inicial em uma única transação."""
    try:
        placa.endereco = endereco
        placa.eventos = [evento]
        db.add(placa)
        await db.commit()

        for instance in (placa, endereco, evento):
            await db.refresh(instance)

        return placa
    except Exception:
        await db.rollback()
        raise


async def list_placas(
    db: AsyncSession, params: PlacaQueryParams
) -> tuple[int, list[Any]]:
    """Lista placas de forma paginada com Join Lateral do último evento e filtros."""
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
    total = (await db.exec(count_stmt)).one()

    offset = (params.page - 1) * params.page_size
    stmt = (
        stmt.order_by(Placa.created_at.desc()).offset(offset).limit(params.page_size)
    )

    result = await db.exec(stmt)
    return total, list(result.all())
