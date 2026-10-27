from contextlib import suppress
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from geoalchemy2 import WKTElement
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.deps import get_current_user
from src.application.schemas.placa_schema import (
    EnderecoResponse,
    EventoPlacaResponse,
    PlacaCreate,
    PlacaListResponse,
    PlacaQueryParams,
    PlacaResponse,
    PlacaTipoItem,
)
from src.domain.enums.placa_enums import CONTRAN_DESCRICOES, TipoEvento
from src.domain.models.endereco import Enderecos
from src.domain.models.eventos_placa import EventosPlaca
from src.domain.models.placa import Placa
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions import placa as placa_functions
from src.infrastructure.storage.minio_client import StorageError, minio_service

QUIXADA_CODIGO_IBGE = "2311306"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

router = APIRouter(prefix="/placas", tags=["Placas"])


async def _serialize_placa_rows(rows: list[Any]) -> list[PlacaResponse]:
    """Converte as linhas retornadas pelo banco em objetos PlacaResponse."""
    items: list[PlacaResponse] = []
    for row in rows:
        placa = row[0]
        endereco = row[1]
        lat = row.latitude
        lng = row.longitude

        evento_response = None
        if row.ev_id is not None:
            foto_url = row.ev_foto_url
            if foto_url:
                foto_url = minio_service.get_public_url(foto_url)

            evento_response = EventoPlacaResponse(
                id=row.ev_id,
                created_by=row.ev_created_by,
                tipo_evento=row.ev_tipo_evento,
                estado_conservacao=row.ev_estado_conservacao,
                estado_pelicula=row.ev_estado_pelicula,
                estado_substrato=row.ev_estado_substrato,
                estado_suporte=row.ev_estado_suporte,
                foto_url=foto_url,
                observacao=row.ev_observacao,
                timestamp=row.ev_timestamp,
            )

        endereco_response = (
            EnderecoResponse.model_validate(endereco) if endereco is not None else None
        )

        contran_val = (
            placa.codigo_contran.value
            if hasattr(placa.codigo_contran, "value")
            else str(placa.codigo_contran)
        )
        items.append(
            PlacaResponse(
                id=placa.id,
                codigo_contran=placa.codigo_contran,
                descricao_contran=CONTRAN_DESCRICOES.get(contran_val),
                afastamento=placa.afastamento,
                tipo_pelicula=placa.tipo_pelicula,
                tipo_substrato=placa.tipo_substrato,
                tipo_suporte=placa.tipo_suporte,
                latitude=lat,
                longitude=lng,
                created_at=placa.created_at,
                endereco=endereco_response,
                ultimo_evento=evento_response,
            )
        )
    return items


@router.post(
    "/",
    response_model=PlacaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra uma nova placa com foto",
    description=(
        "Cadastra uma placa via `multipart/form-data` com os dados da placa, "
        "do endereço, do estado de conservação inicial e a foto obrigatória.\n\n"
        "**Regras de Negócio:**\n"
        "- Requer usuário autenticado (Agente ou Administrador).\n"
        "- Valida o tipo da imagem (`image/jpeg`, `image/png`, `image/webp`).\n"
        "- Realiza o upload da foto para o MinIO antes do commit no banco.\n"
        "- A Placa, o Endereço e o evento `CRIACAO` são inseridos em uma única "
        "transação atômica (Append-Only). Caso o banco falhe, o arquivo órfão "
        "é removido do MinIO."
    ),
    response_description="Placa criada com endereço, evento inicial e URL da foto.",
)
async def create_placa(
    placa_create: Annotated[PlacaCreate, Depends(PlacaCreate.as_form)],
    foto: Annotated[
        UploadFile,
        File(..., description="Arquivo de imagem da placa (JPEG, PNG ou WEBP)"),
    ],
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    if foto.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de imagem inválido. Envie JPEG, PNG ou WEBP.",
        )

    file_bytes = await foto.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo de imagem enviado está vazio.",
        )

    # Validação de Quixadá desativada temporariamente para ambiente de desenvolvimento:
    # municipio = await placa_functions.get_municipio_by_codigo_ibge(
    #     db, QUIXADA_CODIGO_IBGE
    # )
    # if not municipio:
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail="Município de Quixadá não cadastrado.",
    #     )
    # is_inside = await is_point_in_municipio(
    #     db, placa_create.latitude, placa_create.longitude, municipio.id
    # )
    # if not is_inside:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="As coordenadas da placa estão fora de Quixadá!",
    #     )

    placa = Placa(
        codigo_contran=placa_create.codigo_contran,
        afastamento=placa_create.afastamento,
        tipo_pelicula=placa_create.tipo_pelicula,
        tipo_substrato=placa_create.tipo_substrato,
        tipo_suporte=placa_create.tipo_suporte,
        location=WKTElement(
            f"POINT({placa_create.longitude} {placa_create.latitude})", srid=4326
        ),
    )

    try:
        await minio_service.ensure_bucket_exists_async()
        object_name = await minio_service.upload_file_async(
            file_data=file_bytes,
            filename=foto.filename or "placa.jpg",
            content_type=foto.content_type,
            context="placas",
            entity_id=str(placa.id),
        )
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de armazenamento de imagens indisponível no momento.",
        ) from exc

    endereco = None
    if placa_create.endereco is not None:
        has_endereco_info = any(
            v is not None and v.strip() != ""
            for v in (
                placa_create.endereco.logradouro,
                placa_create.endereco.bairro,
                placa_create.endereco.cep,
                placa_create.endereco.referencia,
            )
        )
        if has_endereco_info:
            endereco = Enderecos(
                placa_id=placa.id,
                logradouro=placa_create.endereco.logradouro or "",
                bairro=placa_create.endereco.bairro or "",
                cep=placa_create.endereco.cep or "",
                referencia=placa_create.endereco.referencia,
            )

    evento = EventosPlaca(
        placa_id=placa.id,
        created_by=current_user.id,
        tipo_evento=TipoEvento.CRIACAO,
        estado_conservacao=placa_create.estado_conservacao,
        estado_pelicula=placa_create.estado_pelicula,
        estado_substrato=placa_create.estado_substrato,
        estado_suporte=placa_create.estado_suporte,
        foto_url=object_name,
        observacao=placa_create.observacao,
    )

    try:
        created_placa = await placa_functions.create_placa(db, placa, endereco, evento)
    except Exception:
        with suppress(StorageError):
            await minio_service.delete_file_async(object_name)
        raise

    evento_response = EventoPlacaResponse.model_validate(evento)
    if object_name:
        evento_response.foto_url = minio_service.get_public_url(object_name)

    endereco_response = (
        EnderecoResponse.model_validate(endereco) if endereco is not None else None
    )

    contran_val = (
        created_placa.codigo_contran.value
        if hasattr(created_placa.codigo_contran, "value")
        else str(created_placa.codigo_contran)
    )

    return PlacaResponse(
        id=created_placa.id,
        codigo_contran=created_placa.codigo_contran,
        descricao_contran=CONTRAN_DESCRICOES.get(contran_val),
        afastamento=created_placa.afastamento,
        tipo_pelicula=created_placa.tipo_pelicula,
        tipo_substrato=created_placa.tipo_substrato,
        tipo_suporte=created_placa.tipo_suporte,
        latitude=placa_create.latitude,
        longitude=placa_create.longitude,
        created_at=created_placa.created_at,
        endereco=endereco_response,
        ultimo_evento=evento_response,
    )


@router.get(
    "/tipos",
    response_model=list[PlacaTipoItem],
    status_code=status.HTTP_200_OK,
    summary="Catálogo de tipos e códigos de placas CONTRAN",
    description=(
        "Retorna a lista de todos os códigos CONTRAN e suas descrições para filtros."
    ),
)
async def list_tipos_placas() -> list[PlacaTipoItem]:
    return [
        PlacaTipoItem(codigo=codigo, descricao=descricao)
        for codigo, descricao in CONTRAN_DESCRICOES.items()
    ]


@router.get(
    "/",
    response_model=PlacaListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lista placas paginadas com filtros de endereço e conservação",
    description=(
        "Recupera uma lista paginada de placas unificando Endereço "
        "e o último EventoPlaca.\n\n"
        "**Recursos e Filtros:**\n"
        "- Paginação (`page`, `page_size`).\n"
        "- Filtros parciais por `bairro` e `logradouro` (case-insensitive).\n"
        "- Filtro por `estado_conservacao` atual da placa."
    ),
    response_description="Lista paginada de placas com endereço e último evento.",
)
async def list_placas(
    params: Annotated[PlacaQueryParams, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    total, rows = await placa_functions.list_placas(session, params)
    items = await _serialize_placa_rows(rows)

    return PlacaListResponse(
        total=total,
        page=params.page,
        page_size=params.page_size,
        items=items,
    )
