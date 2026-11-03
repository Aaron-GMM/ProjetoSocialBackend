from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domain.models.eventos_placa import EventosPlaca


async def create_evento(db: AsyncSession, evento: EventosPlaca) -> EventosPlaca:
    """Insere um novo evento (Append-Only) na linha do tempo da placa."""
    try:
        db.add(evento)
        await db.commit()
        await db.refresh(evento)
        return evento
    except Exception:
        await db.rollback()
        raise


async def get_evento_by_id(
    db: AsyncSession, evento_id: UUID, placa_id: UUID | None = None
) -> EventosPlaca | None:
    """Busca um evento específico pelo ID e valida o vínculo com a placa."""
    stmt = select(EventosPlaca).where(EventosPlaca.id == evento_id)
    if placa_id is not None:
        stmt = stmt.where(EventosPlaca.placa_id == placa_id)
    result = await db.exec(stmt)
    return result.first()


async def list_eventos_placa(
    db: AsyncSession, placa_id: UUID, params: Any
) -> tuple[int, list[EventosPlaca]]:
    """Lista eventos de uma placa específica paginados por timestamp DESC."""
    stmt = (
        select(EventosPlaca)
        .where(EventosPlaca.placa_id == placa_id)
        .order_by(EventosPlaca.timestamp.desc())
    )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.exec(count_stmt)).one()

    offset = (params.page - 1) * params.page_size
    paginated_stmt = stmt.offset(offset).limit(params.page_size)

    result = await db.exec(paginated_stmt)
    return total, list(result.all())


list_eventos_by_placa = list_eventos_placa


async def update_evento(db: AsyncSession, evento: EventosPlaca) -> EventosPlaca:
    """Persiste a edição in-place de um evento/relatório da placa (HU-B4)."""
    try:
        db.add(evento)
        await db.commit()
        await db.refresh(evento)
        return evento
    except Exception:
        await db.rollback()
        raise
