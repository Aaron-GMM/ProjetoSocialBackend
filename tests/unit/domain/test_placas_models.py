from datetime import datetime
from uuid import UUID

import pytest
from geoalchemy2.elements import WKTElement

from src.domain.enums.placa_enums import (
    CodigoContran,
    EstadoConservacao,
    TipoEvento,
    TipoPelicula,
    TipoSubstrato,
    TipoSuporte,
)
from src.domain.enums.role import Role
from src.domain.models.endereco import Enderecos
from src.domain.models.eventos_placa import EventosPlaca
from src.domain.models.placa import Placa
from src.domain.models.user import User


def test_instanciar_placa_com_campos_obrigatorios_e_opcionais_nulos():
    placa = Placa(
        codigo_contran=CodigoContran.R_1,
        location="POINT(-39.0147 -4.9708)",
    )

    assert isinstance(placa.id, UUID)
    assert placa.codigo_contran == CodigoContran.R_1
    assert placa.afastamento is None
    assert placa.tipo_pelicula is None
    assert placa.tipo_substrato is None
    assert placa.tipo_suporte is None
    assert isinstance(placa.created_at, datetime)


def test_instanciar_placa_completa_com_enums():
    placa = Placa(
        codigo_contran=CodigoContran.R_19,
        afastamento=1.5,
        tipo_pelicula=TipoPelicula.TIPO_III,
        tipo_substrato=TipoSubstrato.ALUMINIO,
        tipo_suporte=TipoSuporte.POSTE_ACO,
        location="POINT(-39.0147 -4.9708)",
    )

    assert placa.codigo_contran == "R-19"
    assert placa.afastamento == 1.5
    assert placa.tipo_pelicula == TipoPelicula.TIPO_III
    assert placa.tipo_substrato == TipoSubstrato.ALUMINIO
    assert placa.tipo_suporte == TipoSuporte.POSTE_ACO


def test_instanciar_endereco_e_evento_placa():
    placa = Placa(codigo_contran=CodigoContran.A_18, location="POINT(-39.01 -4.97)")

    endereco = Enderecos(
        placa_id=placa.id,
        logradouro="Av. Plácido Castelo",
        bairro="Centro",
        cep="63900-000",
    )
    assert isinstance(endereco.id, UUID)
    assert endereco.referencia is None

    evento = EventosPlaca(
        placa_id=placa.id,
        created_by=1,
        tipo_evento=TipoEvento.CRIACAO,
        estado_conservacao=EstadoConservacao.BOM,
        estado_pelicula=EstadoConservacao.BOM,
        estado_substrato=EstadoConservacao.REGULAR,
        estado_suporte=EstadoConservacao.RUIM,
    )
    assert isinstance(evento.id, UUID)
    assert evento.foto_url is None
    assert evento.observacao is None
    assert evento.estado_pelicula == EstadoConservacao.BOM
    assert evento.estado_substrato == EstadoConservacao.REGULAR
    assert evento.estado_suporte == EstadoConservacao.RUIM


@pytest.mark.asyncio
async def test_persistencia_multiplas_placas_mesmo_codigo_contran_e_relacionamentos(
    db_session,
):
    """
    Garante que múltiplas placas possam ter o mesmo código CONTRAN (ex: duas placas R-1)
    e que os relacionamentos 1:1 (Enderecos) e 1:N (EventosPlaca) persistam no PostGIS.
    """
    agente = User(
        nome="Agente Teste",
        email="agente.placas@quixada.ce.gov.br",
        password_hash="hash123",
        role=Role.AGENTE,
    )
    db_session.add(agente)
    await db_session.commit()
    await db_session.refresh(agente)
    agente_id = agente.id

    placa1 = Placa(
        codigo_contran=CodigoContran.R_1,
        afastamento=0.8,
        tipo_pelicula=TipoPelicula.TIPO_I,
        tipo_substrato=TipoSubstrato.ACO,
        tipo_suporte=TipoSuporte.POSTE_ACO,
        location=WKTElement("POINT(-39.0147 -4.9708)", srid=4326),
    )
    placa2 = Placa(
        codigo_contran=CodigoContran.R_1,
        location=WKTElement("POINT(-39.0155 -4.9712)", srid=4326),
    )
    db_session.add_all([placa1, placa2])
    await db_session.commit()
    await db_session.refresh(placa1)
    await db_session.refresh(placa2)

    placa1_id = placa1.id
    assert placa1_id != placa2.id
    assert placa1.codigo_contran == placa2.codigo_contran == CodigoContran.R_1

    endereco1 = Enderecos(
        placa_id=placa1_id,
        logradouro="Rua José de Queiroz Pessoa",
        bairro="Centro",
        cep="63900-000",
        referencia="Próximo à Praça",
    )
    evento1 = EventosPlaca(
        placa_id=placa1_id,
        created_by=agente_id,
        tipo_evento=TipoEvento.CRIACAO,
        estado_conservacao=EstadoConservacao.BOM,
        estado_pelicula=EstadoConservacao.BOM,
        estado_substrato=EstadoConservacao.BOM,
        estado_suporte=EstadoConservacao.REGULAR,
        observacao="Cadastro inicial da placa R-1",
    )
    db_session.add_all([endereco1, evento1])
    await db_session.commit()
    await db_session.refresh(endereco1)
    await db_session.refresh(evento1)

    assert endereco1.placa_id == placa1_id
    assert evento1.placa_id == placa1_id
