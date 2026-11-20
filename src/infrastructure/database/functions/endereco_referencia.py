from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlmodel.ext.asyncio.session import AsyncSession

from src.infrastructure.services.cnefe import DivisoesDoPonto, EnderecoVizinho

# A subconsulta ordena por `<->` (KNN pelo índice GiST) e limita a k
# candidatos; só então calcula a distância real em metros (geography) e aplica
# o raio. Filtrar por ST_DWithin(geography) direto impediria o uso do índice.
_VIZINHOS_SQL = text("""
    SELECT logradouro, bairro, cep, cidade, estado, distancia_m
    FROM (
        SELECT
            logradouro, bairro, cep, cidade, estado,
            ST_Distance(
                location::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
            ) AS distancia_m
        FROM enderecos_referencia
        ORDER BY location <-> ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
        LIMIT :limite
    ) AS candidatos
    WHERE distancia_m <= :raio_m
    ORDER BY distancia_m
""")

_DIVISOES_SQL = text("""
    SELECT tipo, nome, sede, codigo_municipio
    FROM divisoes_territoriais
    WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))
""")

_INSERT_DIVISAO_SQL = text("""
    INSERT INTO divisoes_territoriais (
        codigo, tipo, nome, codigo_municipio, sede, geom
    )
    VALUES (
        :codigo, :tipo, :nome, :codigo_municipio, :sede,
        ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326))
    )
    ON CONFLICT (codigo) DO UPDATE SET
        tipo = EXCLUDED.tipo,
        nome = EXCLUDED.nome,
        codigo_municipio = EXCLUDED.codigo_municipio,
        sede = EXCLUDED.sede,
        geom = EXCLUDED.geom
    WHERE (
        divisoes_territoriais.tipo, divisoes_territoriais.nome,
        divisoes_territoriais.codigo_municipio, divisoes_territoriais.sede,
        divisoes_territoriais.geom
    ) IS DISTINCT FROM (
        EXCLUDED.tipo, EXCLUDED.nome, EXCLUDED.codigo_municipio, EXCLUDED.sede,
        EXCLUDED.geom
    )
""")

# `bairro` não é atualizado no conflito: ele é derivado e mantido por
# `resolver_bairros`, o que evita regravar a tabela a cada execução do seed.
_INSERT_ENDERECO_SQL = text("""
    INSERT INTO enderecos_referencia (
        cod_unico_endereco, codigo_municipio, codigo_distrito, logradouro,
        localidade, bairro_correios, bairro, cep, cidade, estado, location
    )
    VALUES (
        :cod_unico_endereco, :codigo_municipio, :codigo_distrito, :logradouro,
        :localidade, :bairro_correios, :bairro, :cep, :cidade, :estado,
        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
    )
    ON CONFLICT (cod_unico_endereco) DO UPDATE SET
        codigo_municipio = EXCLUDED.codigo_municipio,
        codigo_distrito = EXCLUDED.codigo_distrito,
        logradouro = EXCLUDED.logradouro,
        localidade = EXCLUDED.localidade,
        bairro_correios = EXCLUDED.bairro_correios,
        cep = EXCLUDED.cep,
        cidade = EXCLUDED.cidade,
        estado = EXCLUDED.estado,
        location = EXCLUDED.location
    -- Só regrava linhas que mudaram (ex.: ajuste de formatação), evitando
    -- reescrever a tabela inteira a cada subida da API.
    WHERE (
        enderecos_referencia.codigo_municipio, enderecos_referencia.codigo_distrito,
        enderecos_referencia.logradouro, enderecos_referencia.localidade,
        enderecos_referencia.bairro_correios, enderecos_referencia.cep,
        enderecos_referencia.cidade, enderecos_referencia.estado,
        enderecos_referencia.location
    ) IS DISTINCT FROM (
        EXCLUDED.codigo_municipio, EXCLUDED.codigo_distrito, EXCLUDED.logradouro,
        EXCLUDED.localidade, EXCLUDED.bairro_correios, EXCLUDED.cep,
        EXCLUDED.cidade, EXCLUDED.estado, EXCLUDED.location
    )
""")

# Bairro oficial de cada endereço de referência:
# 1. dentro de um bairro oficial (limite do IBGE): esse bairro;
# 2. na sede, fora dos bairros: bairro dos Correios já validado (ex.: Cedro);
# 3. em outro distrito: o nome do distrito.
_RESOLVER_BAIRROS_SQL = text("""
    UPDATE enderecos_referencia AS e
    SET bairro = r.bairro
    FROM (
        SELECT
            er.cod_unico_endereco,
            COALESCE(
                (
                    SELECT b.nome FROM divisoes_territoriais b
                    WHERE b.tipo = 'bairro' AND ST_Contains(b.geom, er.location)
                    LIMIT 1
                ),
                CASE WHEN d.sede THEN er.bairro_correios ELSE d.nome END
            ) AS bairro
        FROM enderecos_referencia er
        LEFT JOIN divisoes_territoriais d
            ON d.tipo = 'distrito' AND d.codigo = er.codigo_distrito
    ) AS r
    WHERE e.cod_unico_endereco = r.cod_unico_endereco
      AND e.bairro IS DISTINCT FROM r.bairro
""")


async def buscar_vizinhos(
    db: AsyncSession, lat: float, lng: float, limite: int, raio_m: float
) -> list[EnderecoVizinho]:
    """Retorna até ``limite`` endereços de referência a no máximo ``raio_m``."""
    result = await db.execute(
        _VIZINHOS_SQL, {"lat": lat, "lng": lng, "limite": limite, "raio_m": raio_m}
    )
    return [
        EnderecoVizinho(
            logradouro=row.logradouro,
            bairro=row.bairro,
            cep=row.cep,
            cidade=row.cidade,
            estado=row.estado,
            distancia_m=row.distancia_m,
        )
        for row in result
    ]


async def buscar_divisoes(db: AsyncSession, lat: float, lng: float) -> DivisoesDoPonto:
    """Retorna o bairro e o distrito oficiais que contêm o ponto."""
    result = await db.execute(_DIVISOES_SQL, {"lat": lat, "lng": lng})
    bairro = distrito = codigo_municipio = None
    sede = False
    for row in result:
        codigo_municipio = row.codigo_municipio
        if row.tipo == "bairro":
            bairro = row.nome
        elif row.tipo == "distrito":
            distrito, sede = row.nome, row.sede
    return DivisoesDoPonto(
        bairro=bairro,
        distrito=distrito,
        distrito_sede=sede,
        codigo_municipio=codigo_municipio,
    )


async def inserir_divisoes(conn: AsyncConnection, divisoes: Iterable[dict]) -> None:
    """Insere/atualiza limites de bairros e distritos (idempotente)."""
    lote = list(divisoes)
    if lote:
        await conn.execute(_INSERT_DIVISAO_SQL, lote)


async def inserir_enderecos(conn: AsyncConnection, linhas: Iterable[dict]) -> None:
    """Insere/atualiza endereços de referência em lote (idempotente)."""
    padrao = {"localidade": None, "bairro_correios": None, "bairro": None}
    lote = [{**padrao, **linha} for linha in linhas]
    if lote:
        await conn.execute(_INSERT_ENDERECO_SQL, lote)


async def resolver_bairros(conn: AsyncConnection) -> int:
    """Recalcula o bairro oficial dos endereços; retorna quantos mudaram."""
    result = await conn.execute(_RESOLVER_BAIRROS_SQL)
    return result.rowcount
