import pytest

from src.infrastructure.database.functions.endereco_referencia import (
    inserir_divisoes,
    inserir_enderecos,
)
from src.infrastructure.services.padronizacao_endereco import (
    padronizar_bairro,
    padronizar_logradouro,
)

LAT, LNG = -4.970198, -39.019579
QUADRADO = (
    '{"type":"Polygon","coordinates":[[[-39.02,-4.971],[-39.019,-4.971],'
    "[-39.019,-4.970],[-39.02,-4.970],[-39.02,-4.971]]]}"
)


async def preparar(db_session):
    conn = await db_session.connection()
    await inserir_divisoes(
        conn,
        [
            {
                "codigo": codigo,
                "tipo": tipo,
                "nome": nome,
                "codigo_municipio": "2311306",
                "sede": False,
                "geojson": QUADRADO,
            }
            for codigo, tipo, nome in [
                ("2311306008", "bairro", "Centro"),
                ("2311306016", "bairro", "Nova Jerusalém"),
                ("2311306001", "bairro", "Alto da Boa Vista"),
                ("231130650", "distrito", "Juatama"),
            ]
        ],
    )
    await inserir_enderecos(
        conn,
        [
            {
                "cod_unico_endereco": 1,
                "codigo_municipio": "2311306",
                "codigo_distrito": "231130605",
                "logradouro": "Rua Benjamin Constant",
                "cep": "63900-001",
                "cidade": "Quixadá",
                "estado": "Ceará",
                "lat": LAT,
                "lng": LNG,
            }
        ],
    )
    await db_session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("digitado", "gravado"),
    [
        ("centro", "Centro"),
        ("  CENTRO ", "Centro"),
        ("Nova Jerusalem", "Nova Jerusalém"),
        ("Nova Jesusalém", "Nova Jerusalém"),  # grafia dos Correios
        ("Alto Boa Vista", "Alto da Boa Vista"),
        ("cedro", "Cedro"),  # bairro oficial fora da malha do IBGE
        ("juatama", "Juatama"),  # distrito
        ("  Bairro Novo  ", "Bairro Novo"),  # sem correspondência: mantém
        ("", ""),
        (None, None),
    ],
)
async def test_padronizar_bairro(db_session, digitado, gravado):
    await preparar(db_session)

    assert await padronizar_bairro(db_session, digitado) == gravado


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("digitado", "dlat", "gravado"),
    [
        ("rua benjamim constant", 0.0005, "Rua Benjamin Constant"),  # ~55 m
        ("Rua Benjamin Constant", 0.0, "Rua Benjamin Constant"),
        # mesma rua, mas longe (> 300 m): não há como afirmar que é a mesma
        ("rua benjamim constant", 0.005, "rua benjamim constant"),
        ("Travessa Benjamin Constant", 0.0, "Travessa Benjamin Constant"),
        ("  Rua Sem Cadastro ", 0.0, "Rua Sem Cadastro"),
        ("", 0.0, ""),
        (None, 0.0, None),
    ],
)
async def test_padronizar_logradouro(db_session, digitado, dlat, gravado):
    await preparar(db_session)

    assert await padronizar_logradouro(db_session, digitado, LAT + dlat, LNG) == gravado
