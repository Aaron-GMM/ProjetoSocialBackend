import asyncio
import json

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from src.infrastructure.database.connection import engine


async def seed_municipio_quixada():
    print("Iniciando seed do município de Quixadá...")

    try:
        with open("scripts/quixada.geojson", "r") as f:
            data = json.load(f)
            # O IBGE retorna FeatureCollection. PostGIS precisa da Geometry.
            geom = data["features"][0]["geometry"]
            geojson_data = json.dumps(geom)
    except Exception as e:
        print(f"Erro ao ler geojson: {e}")
        return

    async with AsyncSession(engine) as session:
        query = text("""
            INSERT INTO municipios (id, nome, codigo_ibge, poligono)
            VALUES (gen_random_uuid(), 'Quixadá', '2311306', 
                    ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326))
            ON CONFLICT (codigo_ibge) DO NOTHING;
        """)

        await session.execute(query, {"geojson": geojson_data})
        await session.commit()
        print("Seed finalizado com sucesso! Quixadá está no banco de dados.")


if __name__ == "__main__":
    asyncio.run(seed_municipio_quixada())
