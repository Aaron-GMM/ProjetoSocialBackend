"""Gera ``scripts/data/divisoes_2311306_quixada.geojson`` a partir do IBGE.

Extrai das malhas oficiais do Censo 2022 os limites de Quixadá:
- bairros (21 bairros oficiais do distrito-sede);
- distritos (13 distritos, inclusive a sede).

As coordenadas estão em SIRGAS 2000 (EPSG:4674), que na prática coincide com
WGS 84 (EPSG:4326) — a diferença é menor que 1 m.

Uso (só é necessário para atualizar a base versionada):
    python scripts/build_divisoes_quixada.py
    python scripts/build_divisoes_quixada.py --bairros CE_bairros.gpkg \
        --distritos CE_distritos.gpkg
"""

import argparse
import json
import sqlite3
import struct
import sys
import tempfile
import urllib.request
from pathlib import Path

BASE_URL = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/"
    "malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/"
)
BAIRROS_URL = BASE_URL + "bairros/gpkg/UF/CE/CE_bairros_CD2022.gpkg"
DISTRITOS_URL = BASE_URL + "distritos/gpkg/UF/CE/CE_distritos_CD2022.gpkg"

CODIGO_MUNICIPIO = "2311306"
# O distrito-sede tem o código do município seguido de "05".
CODIGO_DISTRITO_SEDE = CODIGO_MUNICIPIO + "05"
OUTPUT = Path(__file__).resolve().parent / "data" / "divisoes_2311306_quixada.geojson"
CASAS_DECIMAIS = 6  # ~0,1 m


def _baixar(url: str, destino: Path) -> Path:
    print(f"Baixando {url} ...")
    with urllib.request.urlopen(url, timeout=300) as resp:  # noqa: S310
        destino.write_bytes(resp.read())
    return destino


def _wkb_para_geojson(wkb: bytes) -> dict:
    """Converte WKB (Polygon/MultiPolygon) em geometria GeoJSON MultiPolygon."""
    pos = 0

    def ler(fmt: str, ordem: str):
        nonlocal pos
        valores = struct.unpack_from(ordem + fmt, wkb, pos)
        pos += struct.calcsize(ordem + fmt)
        return valores

    def ler_poligono(ordem: str, dim: int) -> list:
        (n_aneis,) = ler("I", ordem)
        aneis = []
        for _ in range(n_aneis):
            (n_pontos,) = ler("I", ordem)
            pontos = ler(f"{dim * n_pontos}d", ordem)
            aneis.append(
                [
                    [
                        round(pontos[i], CASAS_DECIMAIS),
                        round(pontos[i + 1], CASAS_DECIMAIS),
                    ]
                    for i in range(0, len(pontos), dim)
                ]
            )
        return aneis

    def ler_geometria() -> list:
        nonlocal pos
        ordem = "<" if wkb[pos] == 1 else ">"
        pos += 1
        (tipo_raw,) = ler("I", ordem)
        dim_flag, tipo = divmod(tipo_raw, 1000)
        dim = {0: 2, 1: 3, 2: 3, 3: 4}.get(dim_flag)
        if dim is None:
            raise ValueError(f"Tipo de geometria WKB não suportado: {tipo_raw}")
        if tipo == 3:
            return [ler_poligono(ordem, dim)]
        if tipo == 6:
            (n,) = ler("I", ordem)
            poligonos = []
            for _ in range(n):
                poligonos.extend(ler_geometria())
            return poligonos
        raise ValueError(f"Tipo de geometria WKB não suportado: {tipo_raw}")

    return {"type": "MultiPolygon", "coordinates": ler_geometria()}


def _geometria_gpkg(blob: bytes) -> dict:
    """Remove o cabeçalho GeoPackage e converte o WKB restante."""
    if blob[:2] != b"GP":
        raise ValueError("Geometria GeoPackage inválida")
    envelope = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(blob[3] >> 1) & 0x07]
    return _wkb_para_geojson(blob[8 + envelope :])


def _ler(gpkg: Path, sql: str) -> list[tuple]:
    with sqlite3.connect(gpkg) as conn:
        tabela = conn.execute("SELECT table_name FROM gpkg_contents").fetchone()[0]
        return conn.execute(sql.format(tabela=tabela), (CODIGO_MUNICIPIO,)).fetchall()


def build(bairros_gpkg: Path, distritos_gpkg: Path) -> None:
    features = []
    for codigo, nome, blob in _ler(
        bairros_gpkg,
        'SELECT CD_BAIRRO, NM_BAIRRO, geom FROM "{tabela}" WHERE CD_MUN = ? '
        "ORDER BY CD_BAIRRO",
    ):
        features.append(_feature(codigo, "bairro", nome, False, blob))
    for codigo, nome, blob in _ler(
        distritos_gpkg,
        'SELECT CD_DIST, NM_DIST, geom FROM "{tabela}" WHERE CD_MUN = ? '
        "ORDER BY CD_DIST",
    ):
        features.append(
            _feature(codigo, "distrito", nome, codigo == CODIGO_DISTRITO_SEDE, blob)
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": features},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    tipos = [f["properties"]["tipo"] for f in features]
    print(
        f"{tipos.count('bairro')} bairros e {tipos.count('distrito')} distritos "
        f"gravados em {OUTPUT}"
    )


def _feature(codigo: str, tipo: str, nome: str, sede: bool, blob: bytes) -> dict:
    return {
        "type": "Feature",
        "properties": {
            "codigo": codigo,
            "tipo": tipo,
            "nome": nome,
            "sede": sede,
            "codigo_municipio": CODIGO_MUNICIPIO,
        },
        "geometry": _geometria_gpkg(blob),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bairros", type=Path, help="GeoPackage de bairros do IBGE")
    parser.add_argument("--distritos", type=Path, help="GeoPackage de distritos")
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            bairros = args.bairros or _baixar(BAIRROS_URL, Path(tmp) / "b.gpkg")
            distritos = args.distritos or _baixar(DISTRITOS_URL, Path(tmp) / "d.gpkg")
            build(bairros, distritos)
    except Exception as exc:  # pragma: no cover - script de manutenção
        print(f"Erro ao gerar as divisões territoriais: {exc}", file=sys.stderr)
        sys.exit(1)
