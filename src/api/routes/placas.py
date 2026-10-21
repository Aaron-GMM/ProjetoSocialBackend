from contextlib import suppress
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from geoalchemy2 import WKTElement
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.deps import get_current_user
from src.application.schemas.placa_schema import (
    EnderecoResponse,
    EventoPlacaResponse,
    PlacaCreate,
    PlacaResponse,
)
from src.domain.enums.placa_enums import TipoEvento
from src.domain.models.endereco import Enderecos
from src.domain.models.eventos_placa import EventosPlaca
from src.domain.models.placa import Placa
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions import placa as placa_functions
from src.infrastructure.database.functions.geo_validator import is_point_in_municipio
from src.infrastructure.storage.minio_client import StorageError, minio_service

QUIXADA_CODIGO_IBGE = "2311306"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

router = APIRouter(prefix="/placas", tags=["Placas"])


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
        "- As coordenadas devem estar dentro do polígono de Quixadá.\n"
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

    municipio = await placa_functions.get_municipio_by_codigo_ibge(
        db, QUIXADA_CODIGO_IBGE
    )
    if not municipio:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Município de Quixadá não cadastrado.",
        )

    is_inside = await is_point_in_municipio(
        db, placa_create.latitude, placa_create.longitude, municipio.id
    )
    if not is_inside:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="As coordenadas da placa estão fora de Quixadá!",
        )

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

    endereco = Enderecos(placa_id=placa.id, **placa_create.endereco.model_dump())
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
    with suppress(StorageError):
        evento_response.foto_url = await minio_service.get_presigned_url_async(
            object_name
        )

    return PlacaResponse(
        id=created_placa.id,
        codigo_contran=created_placa.codigo_contran,
        afastamento=created_placa.afastamento,
        tipo_pelicula=created_placa.tipo_pelicula,
        tipo_substrato=created_placa.tipo_substrato,
        tipo_suporte=created_placa.tipo_suporte,
        latitude=placa_create.latitude,
        longitude=placa_create.longitude,
        created_at=created_placa.created_at,
        endereco=EnderecoResponse.model_validate(endereco),
        ultimo_evento=evento_response,
    )
