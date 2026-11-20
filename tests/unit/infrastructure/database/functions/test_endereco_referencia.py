import csv
import gzip
import json

import pytest
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from scripts.seed_base_enderecos import seed_base_enderecos
from src.infrastructure.database.functions.endereco_referencia import (
    buscar_divisoes,
    buscar_vizinhos,
    inserir_divisoes,
    inserir_enderecos,
    resolver_bairros,
)
from src.infrastructure.services.cnefe import DivisoesDoPonto

# Ponto de origem (Rua Rui Barbosa, Centro de Quixadá). Em Quixadá,
# 0.0001° de latitude ~ 11 m.
LAT, LNG = -4.970198, -39.019579
SEDE = "231130605"
JUATAMA = "231130650"


def endereco(cod, dlat, bairro="Centro", logradouro="Rua A", cep="63900-001", **extra):
    return {
        "cod_unico_endereco": cod,
        "codigo_municipio": "2311306",
        "codigo_distrito": SEDE,
        "logradouro": logradouro,
        "bairro": bairro,
        "cep": cep,
        "cidade": "Quixadá",
        "estado": "Ceará",
        "lat": LAT + dlat,
        "lng": LNG,
        **extra,
    }


def quadrado(lng_min, lat_min, lng_max, lat_max) -> str:
    return json.dumps(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [lng_min, lat_min],
                    [lng_max, lat_min],
                    [lng_max, lat_max],
                    [lng_min, lat_max],
                    [lng_min, lat_min],
                ]
            ],
        }
    )


def divisao(codigo, tipo, nome, geojson, sede=False):
    return {
        "codigo": codigo,
        "tipo": tipo,
        "nome": nome,
        "codigo_municipio": "2311306",
        "sede": sede,
        "geojson": geojson,
    }


# Sede: faixa a oeste de LNG+0.01; Juatama: faixa a leste.
# Bairro "Centro": quadrado pequeno (~110 m) ao redor da origem.
DIVISOES = [
    divisao(SEDE, "distrito", "Quixadá", quadrado(-39.1, -5.1, LNG + 0.01, -4.8), True),
    divisao(JUATAMA, "distrito", "Juatama", quadrado(LNG + 0.01, -5.1, -38.9, -4.8)),
    divisao(
        "2311306008",
        "bairro",
        "Centro",
        quadrado(LNG - 0.0005, LAT - 0.0005, LNG + 0.0005, LAT + 0.0005),
    ),
]


async def inserir(db_session: AsyncSession, linhas=(), divisoes=()):
    conn = await db_session.connection()
    await inserir_divisoes(conn, divisoes)
    await inserir_enderecos(conn, linhas)
    await db_session.commit()


async def bairros_por_codigo(db_session) -> dict[int, str | None]:
    result = await db_session.execute(
        text("SELECT cod_unico_endereco, bairro FROM enderecos_referencia")
    )
    return dict(result.all())


# ---------------------------------------------------------------------------
# Busca de vizinhos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buscar_vizinhos_ordena_por_distancia(db_session):
    await inserir(
        db_session,
        [
            endereco(1, 0.0005, logradouro="Rua 55m"),
            endereco(2, 0.0001, logradouro="Rua 11m"),
            endereco(3, 0.0003, logradouro="Rua 33m"),
        ],
    )

    vizinhos = await buscar_vizinhos(db_session, LAT, LNG, limite=7, raio_m=150)

    assert [v.logradouro for v in vizinhos] == ["Rua 11m", "Rua 33m", "Rua 55m"]
    assert 10 < vizinhos[0].distancia_m < 12
    assert vizinhos[0].cidade == "Quixadá"


@pytest.mark.asyncio
async def test_buscar_vizinhos_respeita_raio(db_session):
    await inserir(db_session, [endereco(1, 0.0010), endereco(2, 0.0020)])  # 110/220m

    assert len(await buscar_vizinhos(db_session, LAT, LNG, limite=7, raio_m=150)) == 1
    assert await buscar_vizinhos(db_session, LAT, LNG, limite=7, raio_m=100) == []


@pytest.mark.asyncio
async def test_buscar_vizinhos_respeita_limite(db_session):
    await inserir(db_session, [endereco(i, 0.00001 * i) for i in range(1, 21)])

    vizinhos = await buscar_vizinhos(db_session, LAT, LNG, limite=7, raio_m=150)

    assert len(vizinhos) == 7


@pytest.mark.asyncio
async def test_buscar_vizinhos_tabela_vazia(db_session):
    assert await buscar_vizinhos(db_session, LAT, LNG, limite=7, raio_m=150) == []


# ---------------------------------------------------------------------------
# Divisões oficiais
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buscar_divisoes_dentro_de_bairro(db_session):
    await inserir(db_session, divisoes=DIVISOES)

    assert await buscar_divisoes(db_session, LAT, LNG) == DivisoesDoPonto(
        bairro="Centro",
        distrito="Quixadá",
        distrito_sede=True,
        codigo_municipio="2311306",
    )


@pytest.mark.asyncio
async def test_buscar_divisoes_sede_fora_dos_bairros(db_session):
    await inserir(db_session, divisoes=DIVISOES)

    divisoes = await buscar_divisoes(db_session, LAT + 0.005, LNG)

    assert (divisoes.bairro, divisoes.distrito, divisoes.distrito_sede) == (
        None,
        "Quixadá",
        True,
    )


@pytest.mark.asyncio
async def test_buscar_divisoes_outro_distrito(db_session):
    await inserir(db_session, divisoes=DIVISOES)

    divisoes = await buscar_divisoes(db_session, LAT, LNG + 0.05)

    assert (divisoes.bairro, divisoes.distrito, divisoes.distrito_sede) == (
        None,
        "Juatama",
        False,
    )


@pytest.mark.asyncio
async def test_buscar_divisoes_fora_do_municipio(db_session):
    await inserir(db_session, divisoes=DIVISOES)

    assert await buscar_divisoes(db_session, -3.73, -38.5) == DivisoesDoPonto(
        bairro=None, distrito=None, distrito_sede=False, codigo_municipio=None
    )


@pytest.mark.asyncio
async def test_inserir_divisoes_e_idempotente_e_atualiza_nome(db_session):
    await inserir(db_session, divisoes=DIVISOES)
    await inserir(db_session, divisoes=DIVISOES)
    renomeado = {**DIVISOES[2], "nome": "Centro Histórico"}
    await inserir(db_session, divisoes=[renomeado])

    result = await db_session.execute(
        text(
            "SELECT count(*), max(nome) FILTER (WHERE tipo = 'bairro') "
            "FROM divisoes_territoriais"
        )
    )
    assert result.one() == (3, "Centro Histórico")


# ---------------------------------------------------------------------------
# Resolução do bairro oficial de cada endereço
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolver_bairros_aplica_regra_oficial(db_session):
    await inserir(
        db_session,
        [
            # dentro do bairro oficial: limite prevalece sobre os Correios
            endereco(1, 0.0001, bairro=None, bairro_correios="Combate"),
            # sede, fora dos bairros: bairro dos Correios (ex.: Cedro)
            endereco(2, 0.005, bairro=None, bairro_correios="Cedro"),
            # sede, fora dos bairros, sem bairro oficial nos Correios
            endereco(3, 0.006, bairro=None, bairro_correios=None),
            # outro distrito: o nome do distrito
            {
                **endereco(4, 0.0, bairro=None),
                "codigo_distrito": JUATAMA,
                "lng": LNG + 0.05,
            },
        ],
        DIVISOES,
    )
    conn = await db_session.connection()

    alterados = await resolver_bairros(conn)
    await db_session.commit()

    assert alterados == 3  # o endereço 3 já estava sem bairro
    assert await bairros_por_codigo(db_session) == {
        1: "Centro",
        2: "Cedro",
        3: None,
        4: "Juatama",
    }

    conn = await db_session.connection()
    assert await resolver_bairros(conn) == 0  # idempotente


@pytest.mark.asyncio
async def test_inserir_enderecos_nao_sobrescreve_bairro_resolvido(db_session):
    await inserir(db_session, [endereco(1, 0.0001, bairro=None)], DIVISOES)
    conn = await db_session.connection()
    await resolver_bairros(conn)
    await db_session.commit()

    # nova carga (ex.: seed na próxima subida) com localidade alterada
    await inserir(db_session, [endereco(1, 0.0001, bairro=None, localidade="Nova")])

    result = await db_session.execute(
        text("SELECT bairro, localidade FROM enderecos_referencia")
    )
    assert result.one() == ("Centro", "Nova")


@pytest.mark.asyncio
async def test_inserir_enderecos_lote_vazio(db_session):
    conn = await db_session.connection()
    await inserir_enderecos(conn, [])
    await inserir_divisoes(conn, [])

    result = await db_session.execute(text("SELECT count(*) FROM enderecos_referencia"))
    assert result.scalar() == 0


# ---------------------------------------------------------------------------
# Seed completo (scripts/seed_base_enderecos.py)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_base_enderecos_carrega_resolve_e_e_idempotente(engine, tmp_path):
    divisoes_path = tmp_path / "divisoes.geojson"
    divisoes_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            k: d[k]
                            for k in (
                                "codigo",
                                "tipo",
                                "nome",
                                "codigo_municipio",
                                "sede",
                            )
                        },
                        "geometry": json.loads(d["geojson"]),
                    }
                    for d in DIVISOES
                ],
            }
        )
    )
    correios_path = tmp_path / "correios.csv"
    correios_path.write_text("CEP;BAIRRO_CORREIOS\n63902740;Cedro\n", encoding="utf-8")
    cnefe_path = tmp_path / "base.csv.gz"
    with gzip.open(cnefe_path, "wt", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(
            [
                "COD_UNICO_ENDERECO",
                "COD_MUNICIPIO",
                "COD_DISTRITO",
                "CEP",
                "DSC_LOCALIDADE",
                "NOM_TIPO_SEGLOGR",
                "NOM_TITULO_SEGLOGR",
                "NOM_SEGLOGR",
                "LATITUDE",
                "LONGITUDE",
            ]
        )
        for i in range(1, 2501):  # mais de um lote (TAMANHO_LOTE=2000)
            # metade dentro do Centro oficial, metade fora (região do Cedro)
            lat = LAT + (0.0001 if i % 2 else 0.005) + i * 1e-8
            writer.writerow(
                [
                    i,
                    "2311306",
                    SEDE,
                    "63902740",
                    "RESIDENCIAL RACHEL DE QUEIROZ",
                    "RUA",
                    "",
                    "RUI BARBOSA",
                    lat,
                    LNG,
                ]
            )
    database_url = engine.url.render_as_string(hide_password=False)
    caminhos = {
        "divisoes_path": divisoes_path,
        "cnefe_path": cnefe_path,
        "correios_path": correios_path,
    }

    primeira = await seed_base_enderecos(database_url, **caminhos)
    segunda = await seed_base_enderecos(database_url, **caminhos)

    assert primeira == {"divisoes": 3, "enderecos": 2500, "bairros": 2500}
    assert segunda == {"divisoes": 3, "enderecos": 2500, "bairros": 0}
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT bairro, count(*) FROM enderecos_referencia "
                "GROUP BY bairro ORDER BY bairro"
            )
        )
        assert result.all() == [("Cedro", 1250), ("Centro", 1250)]
