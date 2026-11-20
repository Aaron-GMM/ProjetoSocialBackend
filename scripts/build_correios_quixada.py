"""Gera ``scripts/data/correios_bairros_2311306_quixada.csv`` via ViaCEP.

Para cada CEP presente na base do CNEFE de Quixadá, consulta o bairro
registrado pelos Correios. Ele é usado para os endereços da sede que ficam
fora dos 21 bairros oficiais do IBGE (ex.: o Residencial Rachel de Queiroz,
que os Correios registram no bairro Cedro).

Uso (só é necessário para atualizar a base versionada):
    python scripts/build_correios_quixada.py
    python scripts/build_correios_quixada.py --cache respostas_viacep.json
"""

import argparse
import csv
import gzip
import json
import sys
import time
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
CNEFE = DATA / "cnefe_2311306_quixada.csv.gz"
OUTPUT = DATA / "correios_bairros_2311306_quixada.csv"
VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"
PAUSA_S = 0.25  # gentileza com o serviço público


def _ceps() -> list[str]:
    with gzip.open(CNEFE, "rt", encoding="utf-8", newline="") as fh:
        return sorted({row["CEP"] for row in csv.DictReader(fh, delimiter=";")})


def _consultar(cep: str) -> dict:
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(  # noqa: S310
                VIACEP_URL.format(cep=cep), timeout=15
            ) as resp:
                return json.load(resp)
        except Exception:
            time.sleep(2 * (tentativa + 1))
    return {"erro": "falha de rede"}


def build(cache: dict[str, dict]) -> None:
    linhas = []
    for cep in _ceps():
        if cep not in cache:
            cache[cep] = _consultar(cep)
            time.sleep(PAUSA_S)
        resposta = cache[cep]
        bairro = "" if resposta.get("erro") else (resposta.get("bairro") or "")
        linhas.append([cep, bairro.strip()])

    with OUTPUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["CEP", "BAIRRO_CORREIOS"])
        writer.writerows(linhas)
    com_bairro = sum(1 for _, b in linhas if b)
    print(f"{len(linhas)} CEPs ({com_bairro} com bairro) gravados em {OUTPUT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache",
        type=Path,
        help="JSON {cep: resposta_viacep} de uma consulta anterior",
    )
    args = parser.parse_args()
    try:
        build(json.loads(args.cache.read_text()) if args.cache else {})
    except Exception as exc:  # pragma: no cover - script de manutenção
        print(f"Erro ao gerar a base dos Correios: {exc}", file=sys.stderr)
        sys.exit(1)
