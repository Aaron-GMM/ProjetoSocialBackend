from uuid import UUID

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession


async def is_point_in_municipio(
    db: AsyncSession, lat: float, lng: float, municipio_id: UUID
) -> bool:
    """
    Verifica no PostGIS se a coordenada (lat, lng) está contida no
    polígono do município informado. (Versão Assíncrona)
    """
    query = text("""
        SELECT ST_Contains(
            poligono, 
            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
        )
        FROM municipios
        WHERE id = :mun_id
    """)

    result = await db.execute(query, {"lng": lng, "lat": lat, "mun_id": municipio_id})
    # .scalar() em queries async precisa extrair do result
    is_inside = result.scalar()

    return bool(is_inside)
