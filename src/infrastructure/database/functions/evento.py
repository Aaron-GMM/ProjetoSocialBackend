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
    """Busca um evento ativo específico pelo ID e valida o vínculo com a placa."""
    stmt = select(EventosPlaca).where(
        EventosPlaca.id == evento_id,
        EventosPlaca.is_active.is_(True),
    )
    if placa_id is not None:
        stmt = stmt.where(EventosPlaca.placa_id == placa_id)
    result = await db.exec(stmt)
    return result.first()


async def get_evento_placa_by_id(
    db: AsyncSession, placa_id: UUID, evento_id: UUID
) -> EventosPlaca | None:
    """Busca um evento ativo específico de uma placa."""
    return await get_evento_by_id(db, evento_id, placa_id)


async def list_eventos_placa(
    db: AsyncSession, placa_id: UUID, params: Any
) -> tuple[int, list[EventosPlaca]]:
    """Lista eventos ativos de uma placa específica paginados por timestamp DESC."""
    stmt = (
        select(EventosPlaca)
        .where(
            EventosPlaca.placa_id == placa_id,
            EventosPlaca.is_active.is_(True),
        )
        .order_by(EventosPlaca.timestamp.desc())
    )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.exec(count_stmt)).one()

    offset = (params.page - 1) * page_size if (page_size := params.page_size) else 0
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


async def count_active_eventos_placa(db: AsyncSession, placa_id: UUID) -> int:
    """Conta o total de eventos ativos de uma placa."""
    stmt = (
        select(func.count())
        .select_from(EventosPlaca)
        .where(
            EventosPlaca.placa_id == placa_id,
            EventosPlaca.is_active.is_(True),
        )
    )
    return (await db.exec(stmt)).one()


async def soft_delete_evento(db: AsyncSession, evento: EventosPlaca) -> EventosPlaca:
    """Marca um evento como inativo (exclusão lógica)."""
    try:
        evento.is_active = False
        db.add(evento)
        await db.commit()
        await db.refresh(evento)
        return evento
    except Exception:
        await db.rollback()
        raise
