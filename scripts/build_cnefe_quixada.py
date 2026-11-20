"""Gera ``scripts/data/cnefe_2311306_quixada.csv.gz`` a partir do CNEFE/IBGE.

O CNEFE (Cadastro Nacional de Endereços para Fins Estatísticos) do Censo 2022
traz todos os endereços do município com coordenadas, logradouro, bairro
(``DSC_LOCALIDADE``) e CEP. Este script baixa o arquivo oficial de Quixadá,
mantém só as colunas usadas pela geocodificação reversa, descarta coordenadas
imprecisas e remove duplicatas (ex.: apartamentos no mesmo ponto), que
distorceriam a votação do bairro.

Uso (só é necessário para atualizar a base versionada):
    python scripts/build_cnefe_quixada.py
    python scripts/build_cnefe_quixada.py --zip caminho/2311306_QUIXADA.zip
"""

import argparse
import csv
import gzip
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

SOURCE_URL = (
    "https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/"
    "Censo_Demografico_2022/Arquivos_CNEFE/CSV/Municipio/23_CE/2311306_QUIXADA.zip"
)
OUTPUT = Path(__file__).resolve().parent / "data" / "cnefe_2311306_quixada.csv.gz"

# NV_GEO_COORD 1-3: coordenada no nível do endereço. 4+ são aproximações
# (face de quadra, localidade, setor) e não servem para sugerir endereço.
NIVEIS_PRECISOS = {"1", "2", "3"}

COLUNAS = [
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


def _read_source(zip_path: Path | None) -> str:
    if zip_path is None:
        print(f"Baixando {SOURCE_URL} ...")
        with urllib.request.urlopen(SOURCE_URL, timeout=120) as resp:  # noqa: S310
            data = resp.read()
    else:
        data = zip_path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        (name,) = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        return zf.read(name).decode("utf-8")


def build(zip_path: Path | None) -> None:
    reader = csv.DictReader(io.StringIO(_read_source(zip_path)), delimiter=";")
    vistos: set[tuple] = set()
    linhas = []
    total = descartadas = 0
    for row in reader:
        total += 1
        if row["NV_GEO_COORD"] not in NIVEIS_PRECISOS or not row["LATITUDE"]:
            descartadas += 1
            continue
        chave = tuple(row[c] for c in COLUNAS[1:])
        if chave in vistos:
            continue
        vistos.add(chave)
        linhas.append([row[c] for c in COLUNAS])

    linhas.sort(key=lambda r: int(r[0]))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0 deixa o .gz determinístico (mesmo conteúdo => mesmo arquivo)
    with gzip.GzipFile(OUTPUT, "wb", mtime=0) as gz:
        with io.TextIOWrapper(gz, encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow(COLUNAS)
            writer.writerows(linhas)

    print(
        f"{total} endereços lidos, {descartadas} com coordenada imprecisa, "
        f"{len(linhas)} únicos gravados em {OUTPUT}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, help="ZIP do CNEFE já baixado")
    args = parser.parse_args()
    try:
        build(args.zip)
    except Exception as exc:  # pragma: no cover - script de manutenção
        print(f"Erro ao gerar a base do CNEFE: {exc}", file=sys.stderr)
        sys.exit(1)
