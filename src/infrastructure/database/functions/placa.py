from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

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
