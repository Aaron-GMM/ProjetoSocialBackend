from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

from src.infrastructure.database.functions.geo_validator import is_point_in_municipio


@pytest.mark.asyncio
async def test_coordenada_exatamente_no_centro_do_municipio():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = True
    mock_db.execute.return_value = mock_result

    result = await is_point_in_municipio(
        mock_db, lat=-4.968, lng=-39.015, municipio_id=uuid4()
    )
    assert result is True
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_coordenada_fora_dos_limites_do_municipio():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = False
    mock_db.execute.return_value = mock_result

    result = await is_point_in_municipio(
        mock_db, lat=-3.732, lng=-38.526, municipio_id=uuid4()
    )
    assert result is False


@pytest.mark.asyncio
async def test_municipio_id_inexistente_no_banco():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    mock_db.execute.return_value = mock_result

    result = await is_point_in_municipio(
        mock_db, lat=-4.96, lng=-39.01, municipio_id=uuid4()
    )
    assert result is False


@pytest.mark.asyncio
async def test_falha_de_conexao_com_o_postgis():
    mock_db = AsyncMock()
    mock_db.execute.side_effect = OperationalError(
        "Conexão perdida", params={}, orig=None
    )

    with pytest.raises(OperationalError) as exc_info:
        await is_point_in_municipio(
            mock_db, lat=-4.96, lng=-39.01, municipio_id=uuid4()
        )

    assert "Conexão perdida" in str(exc_info.value)
