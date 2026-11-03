import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.application.schemas.placa_schema import PlacaQueryParams
from src.domain.enums.placa_enums import EstadoConservacao, TipoEvento
from src.domain.models.eventos_placa import EventosPlaca
from src.domain.models.placa import Placa
from src.domain.models.user import User
from src.infrastructure.database.functions import placa as placa_functions


@pytest.mark.asyncio
async def test_list_eventos_placa(db_session: AsyncSession):
    """Testa listagem de eventos de uma placa com sucesso."""
    user = User(
        nome="Test User",
        email="test@example.com",
        password_hash="hashed_password",
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

    evento1 = EventosPlaca(
        placa_id=placa_id,
        created_by=user_id,
        tipo_evento=TipoEvento.CRIACAO,
        estado_conservacao=EstadoConservacao.BOM,
        estado_pelicula=EstadoConservacao.BOM,
        estado_substrato=EstadoConservacao.BOM,
        estado_suporte=EstadoConservacao.BOM,
        observacao="Instalação inicial",
    )

    db_session.add(evento1)
    await db_session.commit()

    params = PlacaQueryParams(page=1, page_size=20)
    total, eventos = await placa_functions.list_eventos_placa(
        db_session, placa_id, params
    )

    assert total == 1
    assert len(eventos) == 1
    assert eventos[0].tipo_evento == TipoEvento.CRIACAO
    assert eventos[0].observacao == "Instalação inicial"
