"""Padronização de nomes de rua e bairro para a grafia oficial.

Evita que a mesma rua ou o mesmo bairro apareça com grafias diferentes nos
relatórios (ex.: "centro" x "Centro", "Rua Benjamin Barroso" x "Rua Benjamim
Barroso"). Só troca o texto quando ele corresponde a um nome oficial:
- bairro: nome oficial de bairro/distrito (ou alias conhecido) igual ao
  informado, ignorando acentos e maiúsculas;
- rua: mesma chave de grafia de uma rua oficial do IBGE perto do ponto.
Textos sem correspondência oficial são mantidos como informados.
"""

from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import settings
from src.infrastructure.database.functions.endereco_referencia import (
    buscar_logradouro_canonico,
    listar_nomes_divisoes,
)
from src.infrastructure.services.cnefe import BAIRROS_OFICIAIS_EXTRAS, bairro_oficial


async def padronizar_logradouro(
    db: AsyncSession, nome: str | None, latitude: float, longitude: float
) -> str | None:
    if not nome or not nome.strip():
        return nome
    canonico = await buscar_logradouro_canonico(
        db, nome, latitude, longitude, settings.GEOCODING_PADRONIZACAO_RAIO_M
    )
    return canonico or nome.strip()


async def padronizar_bairro(db: AsyncSession, nome: str | None) -> str | None:
    if not nome or not nome.strip():
        return nome
    oficiais = [*await listar_nomes_divisoes(db), *BAIRROS_OFICIAIS_EXTRAS]
    return bairro_oficial(nome, oficiais) or nome.strip()
