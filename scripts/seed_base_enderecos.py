"""Carrega a base de endereços oficiais de Quixadá no banco.

1. Limites dos 21 bairros e 13 distritos oficiais (malhas do IBGE).
2. Endereços do CNEFE/IBGE, com o bairro dos Correios por CEP e as grafias
   da mesma rua unificadas.
3. Resolve o bairro oficial de cada endereço (ver ``resolver_bairros``).

Idempotente: pode rodar a cada subida da API. Linhas já existentes só são
regravadas se o conteúdo mudou.
"""

import asyncio
import sys
import time
from itertools import islice
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.infrastructure.database.connection import url  # noqa: E402
from src.infrastructure.database.functions.endereco_referencia import (  # noqa: E402
    inserir_divisoes,
    inserir_enderecos,
    resolver_bairros,
)
from src.infrastructure.services.cnefe import (  # noqa: E402
    canonizar_logradouros,
    ler_bairros_correios,
    ler_base_cnefe,
    ler_divisoes,
)

DATA = Path(__file__).resolve().parent / "data"
DIVISOES = DATA / "divisoes_2311306_quixada.geojson"
CNEFE = DATA / "cnefe_2311306_quixada.csv.gz"
CORREIOS = DATA / "correios_bairros_2311306_quixada.csv"
TAMANHO_LOTE = 2000


async def seed_base_enderecos(
    database_url: str = url,
    divisoes_path: Path = DIVISOES,
    cnefe_path: Path = CNEFE,
    correios_path: Path = CORREIOS,
) -> dict[str, int]:
    print("Iniciando seed da base de endereços oficiais (IBGE/Correios)...")
    inicio = time.monotonic()
    # echo=False: o engine da aplicação loga cada SQL, o que poluiria a subida.
    engine = create_async_engine(database_url, echo=False)
    try:
        divisoes = ler_divisoes(divisoes_path)
        bairros_oficiais = [d["nome"] for d in divisoes if d["tipo"] == "bairro"]
        # Unifica grafias da mesma rua (ex.: "Benjamim"/"Benjamin Barroso").
        linhas = iter(
            canonizar_logradouros(
                list(
                    ler_base_cnefe(
                        cnefe_path,
                        ler_bairros_correios(correios_path),
                        bairros_oficiais,
                    )
                )
            )
        )
        total = 0
        async with engine.begin() as conn:
            await inserir_divisoes(conn, divisoes)
            while lote := list(islice(linhas, TAMANHO_LOTE)):
                await inserir_enderecos(conn, lote)
                total += len(lote)
            alterados = await resolver_bairros(conn)
    finally:
        await engine.dispose()
    print(
        f"Seed finalizado em {time.monotonic() - inicio:.1f}s: "
        f"{len(divisoes)} divisões, {total} endereços, "
        f"{alterados} bairros (re)calculados."
    )
    return {"divisoes": len(divisoes), "enderecos": total, "bairros": alterados}


if __name__ == "__main__":
    asyncio.run(seed_base_enderecos())
