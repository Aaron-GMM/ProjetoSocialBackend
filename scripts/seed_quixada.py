import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.infrastructure.database.connection import engine  # noqa: E402


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

    async with engine.begin() as conn:
        query = text("""
            INSERT INTO municipios (id, nome, codigo_ibge, poligono)
            VALUES (gen_random_uuid(), 'Quixadá', '2311306', 
                    ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326))
            ON CONFLICT (codigo_ibge) DO NOTHING;
        """)

        await conn.execute(query, {"geojson": geojson_data})
        print("Seed finalizado com sucesso! Quixadá está no banco de dados.")


if __name__ == "__main__":
    asyncio.run(seed_municipio_quixada())
