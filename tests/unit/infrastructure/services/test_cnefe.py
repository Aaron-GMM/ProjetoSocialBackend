import csv
import gzip
import json
from pathlib import Path

import pytest

from src.infrastructure.services.cnefe import (
    DivisoesDoPonto,
    EnderecoEscolhido,
    EnderecoVizinho,
    bairro_oficial,
    canonizar_logradouros,
    chave_logradouro,
    chave_nome,
    escolher_endereco,
    formatar_cep,
    formatar_nome,
    ler_bairros_correios,
    ler_base_cnefe,
    ler_divisoes,
    montar_logradouro,
    resolver_bairro,
)

SCRIPTS = Path(__file__).resolve().parents[4] / "scripts"
BASE_REAL = SCRIPTS / "data" / "cnefe_2311306_quixada.csv.gz"
DIVISOES_REAIS = SCRIPTS / "data" / "divisoes_2311306_quixada.geojson"
CORREIOS_REAL = SCRIPTS / "data" / "correios_bairros_2311306_quixada.csv"
POLIGONO_QUIXADA = SCRIPTS / "quixada.geojson"


def envelope_quixada() -> tuple[float, float, float, float]:
    """(min_lng, min_lat, max_lng, max_lat) do polígono oficial do IBGE."""
    geom = json.loads(POLIGONO_QUIXADA.read_text())["features"][0]["geometry"]
    pontos = []

    def coletar(coords):
        if isinstance(coords[0], (int, float)):
            pontos.append(coords)
        else:
            for c in coords:
                coletar(c)

    coletar(geom["coordinates"])
    lngs = [p[0] for p in pontos]
    lats = [p[1] for p in pontos]
    return min(lngs), min(lats), max(lngs), max(lats)


# ---------------------------------------------------------------------------
# Formatação de nomes (CNEFE grava MAIÚSCULAS sem acento)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("CENTRO", "Centro"),
        ("ALTO SAO FRANCISCO", "Alto São Francisco"),
        ("SAO JOAO DOS QUEIROZES", "São João dos Queirozes"),
        ("PUTIU", "Putiú"),
        ("JARDIM DOS MONOLITOS", "Jardim dos Monólitos"),
        ("PLANALTO UNIVERSITARIO", "Planalto Universitário"),
        ("NOSSA SENHORA DE FATIMA", "Nossa Senhora de Fátima"),
        ("CONCEICAO", "Conceição"),
        ("SEBASTIAO", "Sebastião"),
        ("CANCOES", "Canções"),
        ("MAGALHAES", "Magalhães"),
        ("JUVENCIO", "Juvêncio"),
        ("VENANCIO", "Venâncio"),
        ("CESARIO", "Cesário"),
        ("EPITACIO", "Epitácio"),
        ("BASILIO", "Basílio"),
        ("OTAVIO", "Otávio"),
        # exceções que a regra de sufixo erraria
        ("CANECAO", "Canecão"),
        ("CRISTOVAO", "Cristóvão"),
        # conectivos minúsculos, exceto no início
        ("DE FRENTE AO POSTO", "De Frente ao Posto"),
        ("LAGOA DA PEDRA", "Lagoa da Pedra"),
        ("JOSE E MARIA", "José e Maria"),
        ("RUA E", "Rua E"),
        ("RUA DE", "Rua De"),
        # números, romanos, letras e códigos preservados
        ("RUA 01", "Rua 01"),
        ("JOAQUIM MEDEIROS II", "Joaquim Medeiros II"),
        ("TRAVESSA DOM LUCAS I", "Travessa Dom Lucas I"),
        ("RUA A", "Rua A"),
        ("BR-122", "BR-122"),
        # palavras curtas não passam por regra de sufixo
        ("MAO", "Mao"),
        # espaços extras e entrada mista
        ("  campo   velho ", "Campo Velho"),
    ],
)
def test_formatar_nome(entrada, esperado):
    assert formatar_nome(entrada) == esperado


@pytest.mark.parametrize("entrada", [None, "", "   "])
def test_formatar_nome_vazio(entrada):
    assert formatar_nome(entrada) is None


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("63900207", "63900-207"),
        ("63900-207", "63900-207"),
        ("6390020", None),
        ("", None),
        (None, None),
    ],
)
def test_formatar_cep(entrada, esperado):
    assert formatar_cep(entrada) == esperado


@pytest.mark.parametrize(
    ("tipo", "titulo", "nome", "esperado"),
    [
        ("RUA", "", "RUI BARBOSA", "Rua Rui Barbosa"),
        ("RUA", "SAO", "JOAO", "Rua São João"),
        (
            "AVENIDA",
            "PRESIDENTE",
            "CASTELO BRANCO",
            "Avenida Presidente Castelo Branco",
        ),
        ("FAZENDA", "", "BOLIVIA", "Fazenda Bolívia"),
        ("RUA", "", "SEM DENOMINACAO", None),
        ("RUA", "", "  SEM   NOME ", None),
        ("RUA", "", "", None),
    ],
)
def test_montar_logradouro(tipo, titulo, nome, esperado):
    assert montar_logradouro(tipo, titulo, nome) == esperado


# ---------------------------------------------------------------------------
# Escolha do endereço a partir dos vizinhos
# ---------------------------------------------------------------------------


def vizinho(distancia, bairro="Centro", logradouro="Rua A", cep="63900-001"):
    return EnderecoVizinho(
        logradouro=logradouro,
        bairro=bairro,
        cep=cep,
        cidade="Quixadá",
        estado="Ceará",
        distancia_m=distancia,
    )


def test_escolher_endereco_sem_vizinhos():
    assert escolher_endereco([]) is None


def test_escolher_endereco_usa_rua_e_cep_do_mais_proximo():
    escolhido = escolher_endereco(
        [
            vizinho(40, logradouro="Rua Longe", cep="63900-999"),
            vizinho(5, logradouro="Rua Perto", cep="63900-111"),
        ]
    )
    assert escolhido == EnderecoEscolhido(
        logradouro="Rua Perto",
        bairro="Centro",
        cep="63900-111",
        cidade="Quixadá",
        estado="Ceará",
        completo=True,
    )


def test_escolher_endereco_bairro_pela_maioria():
    # o mais próximo diverge, mas a maioria dos vizinhos é do Combate
    escolhido = escolher_endereco(
        [
            vizinho(3, bairro="Centro"),
            vizinho(10, bairro="Combate"),
            vizinho(12, bairro="Combate"),
            vizinho(20, bairro="Combate"),
            vizinho(25, bairro="Centro"),
        ]
    )
    assert escolhido.bairro == "Combate"
    assert escolhido.logradouro == "Rua A"


def test_escolher_endereco_empate_resolve_pelo_mais_proximo():
    escolhido = escolher_endereco(
        [
            vizinho(30, bairro="Herval"),
            vizinho(8, bairro="Centro"),
            vizinho(15, bairro="Herval"),
            vizinho(20, bairro="Centro"),
        ]
    )
    assert escolhido.bairro == "Centro"


def test_escolher_endereco_sem_bairro_conta_como_voto():
    # zona rural da sede: a maioria dos vizinhos não tem bairro oficial
    escolhido = escolher_endereco(
        [vizinho(1, bairro=None), vizinho(5, bairro=None), vizinho(9, bairro="Cedro")]
    )
    assert escolhido.bairro is None


def test_escolher_endereco_bairro_vence_quando_e_maioria():
    escolhido = escolher_endereco(
        [
            vizinho(1, bairro=None),
            vizinho(5, bairro="Cedro"),
            vizinho(9, bairro="Cedro"),
        ]
    )
    assert escolhido.bairro == "Cedro"


def test_escolher_endereco_parcial_alem_do_raio_de_endereco():
    escolhido = escolher_endereco(
        [vizinho(200, bairro="Herval"), vizinho(250, bairro="Herval")],
        raio_endereco_m=150,
    )
    assert escolhido.completo is False
    assert (escolhido.logradouro, escolhido.cep) == (None, None)
    assert escolhido.bairro == "Herval"


def test_escolher_endereco_completo_dentro_do_raio_de_endereco():
    escolhido = escolher_endereco([vizinho(149)], raio_endereco_m=150)
    assert escolhido.completo is True
    assert escolhido.logradouro == "Rua A"


def test_escolher_endereco_nao_usa_rua_de_outro_vizinho():
    # o ponto mais próximo está numa via sem nome: não sugerir outra rua
    escolhido = escolher_endereco(
        [vizinho(2, logradouro=None), vizinho(10, logradouro="Rua Vizinha")]
    )
    assert escolhido.logradouro is None


# ---------------------------------------------------------------------------
# Nomes oficiais de bairro e regra do bairro sugerido
# ---------------------------------------------------------------------------

OFICIAIS = ["Centro", "Nova Jerusalém", "Alto da Boa Vista", "Putiú"]


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("São João", "SAO JOAO"),
        ("  nova   jerusalém ", "NOVA JERUSALEM"),
        ("", ""),
        (None, ""),
    ],
)
def test_chave_nome(entrada, esperado):
    assert chave_nome(entrada) == esperado


@pytest.mark.parametrize(
    ("correios", "esperado"),
    [
        ("Centro", "Centro"),
        ("CENTRO", "Centro"),
        ("Putiu", "Putiú"),
        # grafias dos Correios que diferem do nome oficial
        ("Nova Jesusalém", "Nova Jerusalém"),
        ("Alto Boa Vista", "Alto da Boa Vista"),
        # nomes de distrito / zona rural não são bairros
        ("Custódio", None),
        ("Área Rural de Quixadá", None),
        ("", None),
        (None, None),
    ],
)
def test_bairro_oficial(correios, esperado):
    assert bairro_oficial(correios, OFICIAIS) == esperado


def test_bairro_oficial_aceita_bairros_extras_quando_incluidos():
    assert bairro_oficial("Cedro", OFICIAIS) is None
    assert bairro_oficial("Cedro", [*OFICIAIS, "Cedro"]) == "Cedro"


def divisoes(bairro=None, distrito=None, sede=False):
    return DivisoesDoPonto(
        bairro=bairro, distrito=distrito, distrito_sede=sede, codigo_municipio="2311306"
    )


@pytest.mark.parametrize(
    ("divisoes_ponto", "vizinhos", "esperado"),
    [
        # dentro de um bairro oficial: o limite oficial prevalece
        (divisoes("Centro", "Quixadá", True), "Combate", "Centro"),
        # outro distrito (zona rural): o distrito oficial
        (divisoes(None, "Juatama"), "Fazenda Bolívia", "Juatama"),
        # sede fora dos 21 bairros: o bairro dos vizinhos (ex.: Cedro)
        (divisoes(None, "Quixadá", True), "Cedro", "Cedro"),
        (divisoes(None, "Quixadá", True), None, None),
        # fora das divisões conhecidas
        (divisoes(), "Centro", "Centro"),
        (None, "Centro", "Centro"),
    ],
)
def test_resolver_bairro(divisoes_ponto, vizinhos, esperado):
    assert resolver_bairro(divisoes_ponto, vizinhos) == esperado


# ---------------------------------------------------------------------------
# Leitura dos arquivos de scripts/data
# ---------------------------------------------------------------------------

CABECALHO = [
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


def escrever_base(caminho: Path, linhas: list[list[str]]) -> Path:
    with gzip.open(caminho, "wt", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(CABECALHO)
        writer.writerows(linhas)
    return caminho


def linha_cnefe(cod, lat="-4.970198", municipio="2311306", localidade="RESIDENCIAL"):
    return [
        cod,
        municipio,
        "231130605",
        "63902740",
        localidade,
        "RUA",
        "",
        "RUI BARBOSA",
        lat,
        "-39.019579",
    ]


def test_ler_base_cnefe_converte_linhas(tmp_path):
    base = escrever_base(tmp_path / "base.csv.gz", [linha_cnefe("1")])

    (linha,) = list(
        ler_base_cnefe(base, {"63902740": "Cedro"}, bairros_oficiais=["Centro"])
    )

    assert linha == {
        "cod_unico_endereco": 1,
        "codigo_municipio": "2311306",
        "codigo_distrito": "231130605",
        "logradouro": "Rua Rui Barbosa",
        "localidade": "Residencial",
        # Cedro é bairro oficial mesmo fora da malha do IBGE
        "bairro_correios": "Cedro",
        "bairro": None,
        "cep": "63902-740",
        "cidade": "Quixadá",
        "estado": "Ceará",
        "lat": -4.970198,
        "lng": -39.019579,
    }


def test_ler_base_cnefe_descarta_bairro_correios_nao_oficial(tmp_path):
    base = escrever_base(tmp_path / "base.csv.gz", [linha_cnefe("1")])

    (linha,) = list(ler_base_cnefe(base, {"63902740": "Área Rural de Quixadá"}))

    assert linha["bairro_correios"] is None


def test_ler_base_cnefe_ignora_linhas_invalidas(tmp_path):
    base = escrever_base(
        tmp_path / "base.csv.gz",
        [
            linha_cnefe("1", lat=""),
            linha_cnefe("2", lat="abc"),
            linha_cnefe("3", lat="-95"),
            linha_cnefe("4", municipio="9999999"),
            linha_cnefe("5"),
        ],
    )

    linhas = list(ler_base_cnefe(base))

    assert [linha["cod_unico_endereco"] for linha in linhas] == [5]


def test_ler_bairros_correios_ignora_cep_sem_bairro(tmp_path):
    arquivo = tmp_path / "correios.csv"
    arquivo.write_text(
        "CEP;BAIRRO_CORREIOS\n63900207;Centro\n63900000;\n", encoding="utf-8"
    )

    assert ler_bairros_correios(arquivo) == {"63900207": "Centro"}


def test_base_versionada_e_valida():
    """A base versionada no repositório deve carregar inteira e sem lixo."""
    divisoes_reais = ler_divisoes(DIVISOES_REAIS)
    oficiais = [d["nome"] for d in divisoes_reais if d["tipo"] == "bairro"]
    linhas = list(
        ler_base_cnefe(BASE_REAL, ler_bairros_correios(CORREIOS_REAL), oficiais)
    )
    min_lng, min_lat, max_lng, max_lat = envelope_quixada()

    assert len(linhas) > 40_000
    assert len({linha["cod_unico_endereco"] for linha in linhas}) == len(linhas)
    for linha in linhas:
        # todas as coordenadas dentro do envelope do polígono de Quixadá
        assert min_lat <= linha["lat"] <= max_lat
        assert min_lng <= linha["lng"] <= max_lng
        assert linha["cep"] is not None
        assert linha["cidade"] == "Quixadá"
        assert linha["codigo_distrito"].startswith("2311306")
    localidades = {linha["localidade"] for linha in linhas}
    assert {"Centro", "Alto São Francisco", "Campo Velho", "Putiú"} <= localidades
    # nenhuma grafia sem acento sobrou para as palavras do dicionário
    assert not any(b and ("Sao " in b or b.endswith(" Sao")) for b in localidades)
    # bairros dos Correios só podem ser oficiais
    bairros_correios = {linha["bairro_correios"] for linha in linhas} - {None}
    assert bairros_correios <= {*oficiais, "Cedro"}
    assert {"Cedro", "Nova Jerusalém", "Alto da Boa Vista"} <= bairros_correios


def test_divisoes_versionadas_sao_as_oficiais():
    divisoes_reais = ler_divisoes(DIVISOES_REAIS)
    bairros = [d for d in divisoes_reais if d["tipo"] == "bairro"]
    distritos = [d for d in divisoes_reais if d["tipo"] == "distrito"]

    assert len(bairros) == 21
    assert len(distritos) == 13
    assert [d["nome"] for d in distritos if d["sede"]] == ["Quixadá"]
    assert {"Centro", "Putiú", "Jardim dos Monólitos"} <= {b["nome"] for b in bairros}
    assert {"Juatama", "Custódio", "Tapuiará"} <= {d["nome"] for d in distritos}
    for divisao in divisoes_reais:
        assert json.loads(divisao["geojson"])["type"] == "MultiPolygon"


# ---------------------------------------------------------------------------
# Grafias diferentes da mesma rua (casos reais da base de Quixadá)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Rua Benjamim Barroso", "Rua Benjamin Barroso"),
        ("Rua Manoel Pereira Santana", "Rua Manoel Pereira de Santana"),
        ("Assentamento Bomfim 2", "Assentamento Bonfim 2"),
        ("Estrada Arisco", "Estrada do Arisco"),
        (
            "Rodovia Presidente Presidente Costa e Silva",
            "Rodovia Presidente Costa e Silva",
        ),
        ("Fazenda Jerusalém", "Fazenda Jeruzalem"),
        ("Rua Francisco Moreira de Sousa", "Rua Francisco Moreira de Souza"),
        ("Estrada Olho D Água", "Estrada Olho D'Água"),
        ("Rua 01", "Rua 1"),
        ("rua basilio pinto", "Rua Basílio Pinto"),
    ],
)
def test_chave_logradouro_une_grafias_da_mesma_rua(a, b):
    assert chave_logradouro(a) == chave_logradouro(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        # tipo diferente = logradouro diferente
        ("Rua João Ricardo da Silveira", "Travessa João Ricardo da Silveira"),
        ("Rua Alfredo Tavares de Almeida", "Rua Raimundo Tavares de Almeida"),
        ("Fazenda Palmari", "Fazenda Palmas"),
        ("Rua 01", "Rua 02"),
        # letras que também são conectivos, no fim do nome, são o nome da rua
        ("Rua D", "Rua E"),
        ("Rua D", "Rua"),
    ],
)
def test_chave_logradouro_separa_ruas_diferentes(a, b):
    assert chave_logradouro(a) != chave_logradouro(b)


def test_chave_logradouro_vazio():
    assert chave_logradouro(None) == ""
    assert chave_logradouro("  ") == ""


def test_canonizar_logradouros_usa_grafia_mais_frequente():
    linhas = canonizar_logradouros(
        [
            {"logradouro": "Rua Benjamim Constant"},
            {"logradouro": "Rua Benjamin Constant"},
            {"logradouro": "Rua Benjamin Constant"},
            {"logradouro": None},
            {"logradouro": "Rua Outra"},
        ]
    )

    assert [linha["logradouro"] for linha in linhas] == [
        "Rua Benjamin Constant",
        "Rua Benjamin Constant",
        "Rua Benjamin Constant",
        None,
        "Rua Outra",
    ]
    assert linhas[0]["chave_logradouro"] == chave_logradouro("Rua Benjamin Constant")
    assert linhas[3]["chave_logradouro"] is None


def test_canonizar_logradouros_evita_palavra_repetida_e_desempata():
    linhas = canonizar_logradouros(
        [
            {"logradouro": "Serra Serra do Padre"},
            {"logradouro": "Serra Serra do Padre"},
            {"logradouro": "Serra do Padre"},
            # empate: ordem alfabética
            {"logradouro": "Vila São José"},
            {"logradouro": "Vila de São José"},
        ]
    )

    assert {linha["logradouro"] for linha in linhas[:3]} == {"Serra do Padre"}
    assert {linha["logradouro"] for linha in linhas[3:]} == {"Vila São José"}


def test_base_versionada_nao_une_ruas_diferentes():
    """Auditoria da base real: só une grafias da mesma rua."""
    linhas = canonizar_logradouros(list(ler_base_cnefe(BASE_REAL)))
    nomes = {linha["logradouro"] for linha in linhas}

    assert {"Rua D", "Rua E"} <= nomes
    assert "Rua Benjamim Constant" not in nomes
    assert "Serra Serra do Padre" not in nomes
    assert "Rodovia Presidente Presidente Costa e Silva" not in nomes
    assert {
        "Rua João Ricardo da Silveira",
        "Travessa João Ricardo da Silveira",
    } <= nomes
