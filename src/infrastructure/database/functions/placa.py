from typing import Any

from sqlalchemy import func, true
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.application.schemas.placa_schema import PlacaQueryParams
from src.domain.enums.placa_enums import resolve_codigo_contran_filter
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
    db: AsyncSession,
    placa: Placa,
    endereco: Enderecos | None,
    evento: EventosPlaca,
) -> Placa:
    """Insere a placa, endereço (opcional) e evento inicial atomicamente."""
    try:
        if endereco is not None:
            placa.endereco = endereco
        placa.eventos = [evento]
        db.add(placa)
        await db.commit()

        to_refresh: list[Any] = [placa, evento]
        if endereco is not None:
            to_refresh.append(endereco)

        for instance in to_refresh:
            await db.refresh(instance)

        return placa
    except Exception:
        await db.rollback()
        raise


def _build_base_placa_query():
    """Constrói a query base de placas com Endereço e Join Lateral do último evento."""
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
        .outerjoin(Enderecos, Placa.id == Enderecos.placa_id)
        .outerjoin(ultimo_evento_sub, true())
    )
    return stmt, ultimo_evento_sub


async def _paginate_placa_query(
    db: AsyncSession, stmt: Any, page: int, page_size: int
) -> tuple[int, list[Any]]:
    """Executa a contagem total e retorna os registros paginados."""
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.exec(count_stmt)).one()

    offset = (page - 1) * page_size
    paginated_stmt = (
        stmt.order_by(Placa.created_at.desc()).offset(offset).limit(page_size)
    )

    result = await db.exec(paginated_stmt)
    return total, list(result.all())


async def list_placas(
    db: AsyncSession, params: PlacaQueryParams
) -> tuple[int, list[Any]]:
    """Lista placas paginadas com filtros de código, endereço e estado."""
    stmt, ultimo_evento_sub = _build_base_placa_query()

    if params.codigo_contran:
        matched = resolve_codigo_contran_filter(params.codigo_contran)
        if len(matched) == 1:
            stmt = stmt.where(
                (Placa.codigo_contran == matched[0])
                | (Placa.codigo_contran.ilike(f"%{params.codigo_contran}%"))
            )
        elif matched:
            stmt = stmt.where(
                (Placa.codigo_contran.in_(matched))
                | (Placa.codigo_contran.ilike(f"%{params.codigo_contran}%"))
            )

    if params.bairro:
        stmt = stmt.where(Enderecos.bairro.ilike(f"%{params.bairro}%"))
    if params.logradouro:
        stmt = stmt.where(Enderecos.logradouro.ilike(f"%{params.logradouro}%"))
    if params.estado_conservacao:
        stmt = stmt.where(
            ultimo_evento_sub.c.ev_estado_conservacao == params.estado_conservacao
        )

    return await _paginate_placa_query(db, stmt, params.page, params.page_size)
