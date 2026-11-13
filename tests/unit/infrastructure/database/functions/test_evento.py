from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.application.schemas.evento_schema import EventoQueryParams
from src.domain.enums.placa_enums import EstadoConservacao, TipoEvento
from src.domain.models.eventos_placa import EventosPlaca
from src.domain.models.placa import Placa
from src.domain.models.user import User
from src.infrastructure.database.functions import evento as evento_functions


@pytest.mark.asyncio
async def test_evento_crud_and_list(db_session: AsyncSession):
    """Testa criação, busca por ID, atualização in-place e listagem de eventos."""
    user = User(
        nome="Agente Teste",
        email="agente.evento@example.com",
        password_hash="hashed_password",
        created_at=datetime.now(),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user_id = user.id

    placa = Placa(
        codigo_contran="R-1",
        location="POINT(-39.0154 -4.9714)",
    )
    db_session.add(placa)
    await db_session.commit()
    await db_session.refresh(placa)
    placa_id = placa.id

    evento = EventosPlaca(
        placa_id=placa_id,
        created_by=user_id,
        tipo_evento=TipoEvento.CRIACAO,
        estado_conservacao=EstadoConservacao.BOM,
        observacao="Observação original",
    )
    created = await evento_functions.create_evento(db_session, evento)
    evento_id = created.id

    fetched = await evento_functions.get_evento_by_id(db_session, evento_id, placa_id)
    assert fetched is not None
    assert fetched.id == evento_id
    assert fetched.observacao == "Observação original"

    # Busca com placa_id incorreto deve retornar None
    wrong_placa = await evento_functions.get_evento_by_id(
        db_session, evento_id, uuid4()
    )
    assert wrong_placa is None

    # Update in-place
    fetched.estado_conservacao = EstadoConservacao.RUIM
    fetched.observacao = "Observação retificada"
    updated = await evento_functions.update_evento(db_session, fetched)
    assert updated.id == evento_id
    assert updated.estado_conservacao == EstadoConservacao.RUIM
    assert updated.observacao == "Observação retificada"

    params = EventoQueryParams(page=1, page_size=20)
    total, items = await evento_functions.list_eventos_by_placa(
        db_session, placa_id, params
    )
    assert total == 1
    assert len(items) == 1
    assert items[0].observacao == "Observação retificada"


@pytest.mark.asyncio
async def test_update_evento_rollback_on_commit_error():
    """Garante rollback quando o commit falha na atualização do evento."""
    mock_db = MagicMock()
    mock_db.commit = AsyncMock(side_effect=RuntimeError("Erro ao atualizar evento"))
    mock_db.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="Erro ao atualizar evento"):
        await evento_functions.update_evento(mock_db, MagicMock())

    mock_db.rollback.assert_awaited_once()
