"""Regras da base de endereços oficiais (IBGE e Correios).

Fontes (todas versionadas em ``scripts/data`` e carregadas pelo seed):
- CNEFE/IBGE (Censo 2022): endereços com coordenada, logradouro e CEP. Grava
  nomes em MAIÚSCULAS e sem acento (ex.: ``SAO JOAO``), convertidos aqui para
  a grafia de exibição (``São João``).
- Malhas do IBGE (Censo 2022): limites dos 21 bairros oficiais e dos 13
  distritos de Quixadá.
- Correios (ViaCEP): bairro de cada CEP, usado só para endereços da sede fora
  dos 21 bairros e só quando é um bairro oficial (ex.: Cedro).

Regra do bairro sugerido para um ponto:
1. Dentro de um dos 21 bairros oficiais: o nome desse bairro.
2. Fora deles, em outro distrito (zona rural): o nome do distrito oficial.
3. Na sede, fora dos 21 bairros: o bairro mais frequente entre os endereços
   vizinhos (já resolvido pelo seed, ex.: Cedro); ``None`` na zona rural da
   sede, que não pertence a bairro nem a outro distrito.
"""

import csv
import gzip
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

# Municípios com base carregada: código IBGE -> (cidade, estado).
MUNICIPIOS = {"2311306": ("Quixadá", "Ceará")}

# Bairros oficiais que não estão na malha do IBGE de 2022.
# Cedro: criado pela Lei Municipal nº 2.319/2007 de Quixadá; os Correios o
# usam para a região do Residencial Rachel de Queiroz.
BAIRROS_OFICIAIS_EXTRAS = {"Cedro"}

# Grafias dos Correios que diferem do nome oficial. Chave: nome normalizado.
ALIASES_BAIRROS = {
    "NOVA JESUSALEM": "Nova Jerusalém",
    "ALTO BOA VISTA": "Alto da Boa Vista",
}

# Palavras com acentuação inequívoca em nomes de logradouros/bairros de
# Quixadá. Chave: forma do CNEFE (maiúscula, sem acento).
ACENTOS = {
    "ACUDE": "Açude",
    "AGUA": "Água",
    "ALIVIO": "Alívio",
    "ALUISIO": "Aluísio",
    "AMBROSIO": "Ambrósio",
    "AMERICA": "América",
    "ANALIA": "Anália",
    "ANTONIA": "Antônia",
    "ANTONIO": "Antônio",
    "ARAPUA": "Arapuá",
    "ARAUJO": "Araújo",
    "ATRAS": "Atrás",
    "BANABUIU": "Banabuiú",
    "BASILIO": "Basílio",
    "BELEM": "Belém",
    "BOLIVIA": "Bolívia",
    "BRASILIA": "Brasília",
    "CACADAS": "Caçadas",
    "CAFE": "Café",
    "CALIFORNIA": "Califórnia",
    "CAMARA": "Câmara",
    "CANADA": "Canadá",
    "CANAFISTULA": "Canafístula",
    "CANDIDO": "Cândido",
    "CANECAO": "Canecão",
    "CARAUBAS": "Caraúbas",
    "CEARA": "Ceará",
    "CHORO": "Choró",
    "CICERO": "Cícero",
    "CIPO": "Cipó",
    "COLEGIO": "Colégio",
    "CONEGO": "Cônego",
    "CRIANCAS": "Crianças",
    "CRISTOVAO": "Cristóvão",
    "CROATA": "Croatá",
    "CUSTODIO": "Custódio",
    "EMILIA": "Emília",
    "ENEAS": "Enéas",
    "ENGRACIA": "Engrácia",
    "ESPERANCA": "Esperança",
    "ESPIRITO": "Espírito",
    "EUDASIO": "Eudásio",
    "EUSEBIO": "Eusébio",
    "FATIMA": "Fátima",
    "FE": "Fé",
    "GOIAS": "Goiás",
    "GONCALO": "Gonçalo",
    "GONCALVES": "Gonçalves",
    "GUARUJA": "Guarujá",
    "HERMINIO": "Hermínio",
    "INACIO": "Inácio",
    "IRAJA": "Irajá",
    "JATOBA": "Jatobá",
    "JERUSALEM": "Jerusalém",
    "JONATAS": "Jônatas",
    "JOSE": "José",
    "JUA": "Juá",
    "LAZARO": "Lázaro",
    "LOURENCO": "Lourenço",
    "LUCIA": "Lúcia",
    "LUCIO": "Lúcio",
    "LUIS": "Luís",
    "MASSAPE": "Massapê",
    "MAURICIO": "Maurício",
    "MELQUIADES": "Melquíades",
    "MEXICO": "México",
    "MONOLITOS": "Monólitos",
    "MUQUEM": "Muquém",
    "NAO": "Não",
    "OLIVENCA": "Olivença",
    "ONCA": "Onça",
    "ORQUIDEAS": "Orquídeas",
    "OVIDIO": "Ovídio",
    "PARAIBA": "Paraíba",
    "PARAISO": "Paraíso",
    "PARANA": "Paraná",
    "PIAUI": "Piauí",
    "PLACIDO": "Plácido",
    "POCO": "Poço",
    "PRACA": "Praça",
    "PRINCIPIO": "Princípio",
    "PUTIU": "Putiú",
    "QUIXADA": "Quixadá",
    "SAIDA": "Saída",
    "SANTAREM": "Santarém",
    "SAO": "São",
    "SATIRO": "Sátiro",
    "SINESIO": "Sinésio",
    "SITIA": "Sitiá",
    "SITIO": "Sítio",
    "TAMANDUA": "Tamanduá",
    "TAPUIARA": "Tapuiará",
    "TIMBAUBA": "Timbaúba",
    "TRES": "Três",
    "TRIANGULO": "Triângulo",
    "VALENCA": "Valença",
    "VARZEA": "Várzea",
    "VITORIA": "Vitória",
    "ZE": "Zé",
}

# Sufixos com acentuação regular no português (ex.: CONCEICAO → Conceição,
# SEBASTIAO → Sebastião, CESARIO → Cesário). Aplicados em ordem, depois do
# dicionário ACENTOS, que trata as exceções (ex.: CANECAO → Canecão).
SUFIXOS = (
    ("COES", "ções"),
    ("CAO", "ção"),
    ("OES", "ões"),
    ("AES", "ães"),
    ("AO", "ão"),
    ("ENCIO", "êncio"),
    ("ANCIO", "âncio"),
    ("ARIO", "ário"),
    ("ACIO", "ácio"),
    ("ILIO", "ílio"),
    ("AVIO", "ávio"),
)
_SUFIXO_MIN_LEN = 4  # evita mexer em palavras curtas/abreviações

CONECTIVOS = {"DE", "DA", "DO", "DAS", "DOS", "E", "EM", "NA", "NO", "AO", "AOS"}
ROMANOS = re.compile(r"^(I{1,3}|IV|V|VI{0,3}|IX|X{1,3})$")

# Logradouros sem nome real no cadastro.
SEM_NOME = {"SEM DENOMINACAO", "SEM NOME", "SEM DENOMINACA"}


def _formatar_palavra(palavra: str, nas_pontas: bool) -> str:
    if not palavra.isalpha():
        return palavra  # números e códigos (ex.: "BR-122", "2") ficam como estão
    # Conectivo só no meio do nome: "José e Maria", mas "Rua E" (rua com nome
    # de letra) e "De Frente ao Posto" mantêm a maiúscula.
    if palavra in CONECTIVOS and not nas_pontas:
        return palavra.lower()
    if ROMANOS.match(palavra) or len(palavra) == 1:
        return palavra  # "II", "III", "Rua A"
    if palavra in ACENTOS:
        return ACENTOS[palavra]
    if len(palavra) >= _SUFIXO_MIN_LEN:
        for sufixo, acentuado in SUFIXOS:
            if palavra.endswith(sufixo):
                return palavra[: -len(sufixo)].capitalize() + acentuado
    return palavra.capitalize()


def formatar_nome(valor: str | None) -> str | None:
    """Converte ``SAO JOAO DOS QUEIROZES`` em ``São João dos Queirozes``."""
    if not valor or not valor.strip():
        return None
    palavras = valor.upper().split()
    ultima = len(palavras) - 1
    return " ".join(
        _formatar_palavra(p, i in (0, ultima)) for i, p in enumerate(palavras)
    )


def formatar_cep(valor: str | None) -> str | None:
    digitos = re.sub(r"\D", "", valor or "")
    if len(digitos) != 8:
        return None
    return f"{digitos[:5]}-{digitos[5:]}"


def montar_logradouro(tipo: str, titulo: str, nome: str) -> str | None:
    """Compõe ``RUA`` + ``SAO`` + ``JOAO`` em ``Rua São João``."""
    nome = " ".join((nome or "").upper().split())
    if not nome or nome in SEM_NOME:
        return None
    partes = [p for p in (tipo, titulo, nome) if p and p.strip()]
    return formatar_nome(" ".join(partes))


def chave_nome(nome: str | None) -> str:
    """Normaliza para comparação: sem acento, maiúsculas, espaços simples."""
    sem_acento = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore")
    return " ".join(sem_acento.decode().upper().split())


def bairro_oficial(nome: str | None, oficiais: Iterable[str]) -> str | None:
    """Converte um nome de bairro (ex.: dos Correios) para o nome oficial.

    Retorna ``None`` se o nome não for de um bairro oficial (ex.: nomes de
    distrito ou "Área Rural de Quixadá").
    """
    chave = chave_nome(nome)
    if not chave:
        return None
    if chave in ALIASES_BAIRROS:
        return ALIASES_BAIRROS[chave]
    por_chave = {chave_nome(o): o for o in oficiais}
    return por_chave.get(chave)


@dataclass(frozen=True)
class DivisoesDoPonto:
    """Divisões oficiais que contêm uma coordenada."""

    bairro: str | None
    distrito: str | None
    distrito_sede: bool
    codigo_municipio: str | None


def resolver_bairro(
    divisoes: DivisoesDoPonto | None, bairro_vizinhos: str | None
) -> str | None:
    """Aplica a regra do bairro sugerido (ver docstring do módulo)."""
    if divisoes is not None and divisoes.bairro:
        return divisoes.bairro
    if divisoes is not None and divisoes.distrito and not divisoes.distrito_sede:
        return divisoes.distrito
    return bairro_vizinhos


@dataclass(frozen=True)
class EnderecoVizinho:
    """Endereço de referência próximo à coordenada consultada."""

    logradouro: str | None
    bairro: str | None
    cep: str | None
    cidade: str
    estado: str
    distancia_m: float


@dataclass(frozen=True)
class EnderecoEscolhido:
    logradouro: str | None
    bairro: str | None
    cep: str | None
    cidade: str
    estado: str
    # False quando o endereço mais próximo está além do raio de endereço: só o
    # bairro (área) é confiável; rua e CEP precisam vir de outra fonte.
    completo: bool = True


def escolher_endereco(
    vizinhos: list[EnderecoVizinho], raio_endereco_m: float | None = None
) -> EnderecoEscolhido | None:
    """Escolhe o endereço sugerido a partir dos vizinhos mais próximos.

    - Logradouro e CEP: do endereço mais próximo (são específicos da rua),
      desde que ele esteja a no máximo ``raio_endereco_m``.
    - Bairro: o mais frequente entre os vizinhos (``None`` conta como voto),
      o que corrige pontos isolados com bairro divergente; empate é resolvido
      pelo mais próximo.
    """
    if not vizinhos:
        return None
    ordenados = sorted(vizinhos, key=lambda v: v.distancia_m)
    mais_proximo = ordenados[0]

    # "Sem bairro" (None) também é um voto: na zona rural da sede, vizinhos
    # sem bairro oficial não devem ser vencidos por um único vizinho urbano.
    contagem = Counter(v.bairro for v in ordenados)
    maximo = max(contagem.values())
    bairro = next(v.bairro for v in ordenados if contagem[v.bairro] == maximo)

    completo = raio_endereco_m is None or mais_proximo.distancia_m <= raio_endereco_m
    # Sem fallback para a rua de outro vizinho: se o endereço mais próximo
    # está numa via sem nome, sugerir outra rua seria errado.
    return EnderecoEscolhido(
        logradouro=mais_proximo.logradouro if completo else None,
        bairro=bairro,
        cep=mais_proximo.cep if completo else None,
        cidade=mais_proximo.cidade,
        estado=mais_proximo.estado,
        completo=completo,
    )


def ler_divisoes(caminho: Path) -> list[dict]:
    """Lê o GeoJSON gerado por ``scripts/build_divisoes_quixada.py``."""
    colecao = json.loads(caminho.read_text(encoding="utf-8"))
    return [
        {
            "codigo": f["properties"]["codigo"],
            "tipo": f["properties"]["tipo"],
            "nome": f["properties"]["nome"],
            "codigo_municipio": f["properties"]["codigo_municipio"],
            "sede": bool(f["properties"]["sede"]),
            "geojson": json.dumps(f["geometry"]),
        }
        for f in colecao["features"]
    ]


def ler_bairros_correios(caminho: Path) -> dict[str, str]:
    """Lê o CSV de ``scripts/build_correios_quixada.py``: CEP -> bairro."""
    with caminho.open(encoding="utf-8", newline="") as fh:
        return {
            row["CEP"]: row["BAIRRO_CORREIOS"]
            for row in csv.DictReader(fh, delimiter=";")
            if row["BAIRRO_CORREIOS"].strip()
        }


def ler_base_cnefe(
    caminho: Path,
    bairros_correios: dict[str, str] | None = None,
    bairros_oficiais: Iterable[str] = (),
) -> Iterator[dict]:
    """Lê o CSV.gz gerado por ``scripts/build_cnefe_quixada.py``.

    Gera dicionários prontos para ``inserir_enderecos``. O bairro dos Correios
    só é mantido se for um bairro oficial. O ``bairro`` final é resolvido
    depois, no banco (``resolver_bairros``). Linhas com coordenada inválida ou
    município desconhecido são ignoradas.
    """
    bairros_correios = bairros_correios or {}
    oficiais = set(bairros_oficiais) | BAIRROS_OFICIAIS_EXTRAS
    with gzip.open(caminho, "rt", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            municipio = MUNICIPIOS.get(row["COD_MUNICIPIO"])
            try:
                lat, lng = float(row["LATITUDE"]), float(row["LONGITUDE"])
            except (TypeError, ValueError):
                continue
            if municipio is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
                continue
            yield {
                "cod_unico_endereco": int(row["COD_UNICO_ENDERECO"]),
                "codigo_municipio": row["COD_MUNICIPIO"],
                "codigo_distrito": row["COD_DISTRITO"],
                "logradouro": montar_logradouro(
                    row["NOM_TIPO_SEGLOGR"],
                    row["NOM_TITULO_SEGLOGR"],
                    row["NOM_SEGLOGR"],
                ),
                "localidade": formatar_nome(row["DSC_LOCALIDADE"]),
                "bairro_correios": bairro_oficial(
                    bairros_correios.get(row["CEP"]), oficiais
                ),
                "bairro": None,
                "cep": formatar_cep(row["CEP"]),
                "cidade": municipio[0],
                "estado": municipio[1],
                "lat": lat,
                "lng": lng,
            }
