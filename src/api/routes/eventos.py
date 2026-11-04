from contextlib import suppress
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.deps import get_current_user
from src.api.routes import placas as placas_route
from src.application.schemas.evento_schema import (
    EventoPlacaListResponse,
    EventoPlacaResponse,
    EventoPlacaUpdate,
    EventoQueryParams,
    VistoriaCreate,
)
from src.domain.enums.placa_enums import TipoEvento
from src.domain.enums.role import Role
from src.domain.models.eventos_placa import EventosPlaca
from src.domain.models.user import User
from src.infrastructure.database.connection import get_session
from src.infrastructure.database.functions import evento as evento_functions
from src.infrastructure.database.functions import placa as placa_functions
from src.infrastructure.storage.minio_client import StorageError
from src.infrastructure.storage.minio_client import (
    minio_service as _default_minio_service,
)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

minio_service = _default_minio_service
_orig_create_evento = evento_functions.create_evento
_orig_update_evento = evento_functions.update_evento

router = APIRouter(
    prefix="/placas/{placa_id}",
    tags=["Eventos/Relatórios das Placas"],
)


def _resolve_minio_service() -> Any:
    """Retorna o serviço MinIO ativo (suporta monkeypatch em eventos ou placas)."""
    if minio_service is not _default_minio_service:
        return minio_service
    if (
        getattr(placas_route, "minio_service", _default_minio_service)
        is not _default_minio_service
    ):
        return placas_route.minio_service
    return minio_service


async def _read_image(foto: UploadFile) -> bytes:
    """Valida o tipo da imagem enviada e retorna seu conteúdo."""
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
    return file_bytes


async def _upload_image(foto: UploadFile, file_bytes: bytes, placa_id: UUID) -> str:
    """Envia a imagem ao MinIO e retorna o object_name salvo."""
    storage = _resolve_minio_service()
    try:
        await storage.ensure_bucket_exists_async()
        return await storage.upload_file_async(
            file_data=file_bytes,
            filename=foto.filename or "placa.jpg",
            content_type=foto.content_type,
            context="placas",
            entity_id=str(placa_id),
        )
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de armazenamento de imagens indisponível no momento.",
        ) from exc


async def _get_placa_row_or_404(db: AsyncSession, placa_id: UUID) -> Any:
    """Valida se a placa existe no banco ou lança HTTP 404."""
    row = await placa_functions.get_placa_by_id(db, placa_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Placa não encontrada."
        )
    return row


async def _get_evento_or_404(
    db: AsyncSession, evento_id: UUID, placa_id: UUID
) -> EventosPlaca:
    """Busca o evento específico vinculado à placa ou lança HTTP 404."""
    evento = await evento_functions.get_evento_by_id(db, evento_id, placa_id)
    if evento is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado para esta placa.",
        )
    return evento


@router.post(
    "/vistoria",
    response_model=EventoPlacaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registra uma nova vistoria em uma placa existente",
    description=(
        "Cadastra um novo relatório de vistoria via `multipart/form-data`.\n\n"
        "**Regras de Negócio:**\n"
        "- Requer usuário autenticado (Agente ou Administrador).\n"
        "- A tabela `placas` não é alterada: um novo evento `VISTORIA` é inserido "
        "em `eventos_placa` (Append-Only).\n"
        "- A foto é enviada ao MinIO antes do commit e removida caso o banco falhe."
    ),
    response_description="Evento de vistoria criado com a URL da foto.",
)
async def create_vistoria(
    placa_id: UUID,
    vistoria: Annotated[VistoriaCreate, Depends(VistoriaCreate.as_form)],
    foto: Annotated[
        UploadFile,
        File(..., description="Foto da placa no momento da vistoria"),
    ],
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await _get_placa_row_or_404(db, placa_id)
    file_bytes = await _read_image(foto)
    object_name = await _upload_image(foto, file_bytes, placa_id)
    storage = _resolve_minio_service()

    evento = EventosPlaca(
        placa_id=placa_id,
        created_by=current_user.id,
        tipo_evento=TipoEvento.VISTORIA,
        foto_url=object_name,
        **vistoria.model_dump(),
    )

    create_fn = (
        placa_functions.create_evento
        if placa_functions.create_evento is not evento_functions.create_evento
        else evento_functions.create_evento
    )

    try:
        evento = await create_fn(db, evento)
    except Exception:
        with suppress(StorageError):
            await storage.delete_file_async(object_name)
        raise

    evento_response = EventoPlacaResponse.model_validate(evento)
    evento_response.foto_url = storage.get_public_url(object_name)
    return evento_response


@router.get(
    "/historico",
    response_model=EventoPlacaListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lista eventos de uma placa específica",
    description=(
        "Recupera a linha do tempo paginada de eventos/relatórios de uma placa "
        "específica ordenada do mais recente para o mais antigo (`timestamp DESC`).\n\n"
        "**Recursos e Filtros:**\n"
        "- Paginação (`page`, `page_size`).\n"
    ),
    response_description="Lista paginada de eventos de uma placa específica.",
)
async def list_eventos_placa(
    placa_id: UUID,
    params: Annotated[EventoQueryParams, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await _get_placa_row_or_404(session, placa_id)
    storage = _resolve_minio_service()
    total, rows = await evento_functions.list_eventos_placa(session, placa_id, params)
    items: list[EventoPlacaResponse] = []
    for row in rows:
        item = EventoPlacaResponse.model_validate(row)
        if item.foto_url:
            item.foto_url = storage.get_public_url(item.foto_url)
        items.append(item)

    return EventoPlacaListResponse(
        total=total,
        page=params.page,
        page_size=params.page_size,
        items=items,
    )


@router.patch(
    "/eventos/{evento_id}",
    response_model=EventoPlacaResponse,
    status_code=status.HTTP_200_OK,
    summary="Edita os dados de um relatório/evento específico (HU-B4)",
    description=(
        "Realiza a edição (Update in-place) de um evento específico na linha "
        "do tempo da placa sem criar uma nova vistoria.\n\n"
        "**Regras de Negócio:**\n"
        "- Aceita `multipart/form-data` (com nova foto opcional) "
        "ou `application/json`.\n"
        "- Um `AGENTE` só pode editar eventos criados por ele mesmo "
        "(`created_by == current_user.id`).\n"
        "- Um `ADMINISTRADOR` pode editar eventos de qualquer agente.\n"
        "- Se uma nova `foto` for enviada, realiza upload no MinIO, atualiza "
        "`foto_url` e remove a imagem antiga do bucket após o commit."
    ),
    response_description="Evento editado com sucesso.",
)
async def update_evento_placa(
    placa_id: UUID,
    evento_id: UUID,
    evento_update: Annotated[EventoPlacaUpdate, Depends(EventoPlacaUpdate.as_form)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    foto: Annotated[
        UploadFile | None,
        File(description="Nova foto do evento/relatório (opcional)"),
    ] = None,
):
    await _get_placa_row_or_404(db, placa_id)
    evento = await _get_evento_or_404(db, evento_id, placa_id)

    if current_user.role != Role.ADMINISTRADOR and evento.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Você não tem permissão para editar um evento criado por outro agente."
            ),
        )

    update_data = evento_update.model_dump(exclude_none=True)
    if update_data:
        evento.sqlmodel_update(update_data)

    storage = _resolve_minio_service()
    new_object_name: str | None = None
    old_object_name: str | None = None

    if foto is not None:
        file_bytes = await _read_image(foto)
        new_object_name = await _upload_image(foto, file_bytes, placa_id)
        old_object_name = evento.foto_url
        evento.foto_url = new_object_name

    update_fn = (
        placa_functions.update_evento
        if placa_functions.update_evento is not evento_functions.update_evento
        else evento_functions.update_evento
    )

    try:
        evento = await update_fn(db, evento)
    except Exception:
        if new_object_name:
            with suppress(StorageError):
                await storage.delete_file_async(new_object_name)
        raise

    if old_object_name:
        with suppress(StorageError):
            await storage.delete_file_async(old_object_name)

    evento_response = EventoPlacaResponse.model_validate(evento)
    if evento_response.foto_url:
        evento_response.foto_url = storage.get_public_url(evento_response.foto_url)
    return evento_response


@router.delete(
    "/eventos/{evento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui logicamente um relatório/evento específico de uma placa (HU-B6)",
    description=(
        "Marca um relatório específico como inativo (`is_active = False`), "
        "fazendo a placa retornar ao estado do evento válido anterior.\n\n"
        "**Regras de Negócio:**\n"
        "- Um `AGENTE` só pode excluir eventos criados por ele mesmo "
        "(`created_by == current_user.id`).\n"
        "- Um `ADMINISTRADOR` pode excluir eventos de qualquer agente.\n"
        "- Não permite excluir o evento inicial (`CRIACAO`) caso seja o único "
        "evento ativo da placa."
    ),
)
async def delete_evento_placa(
    placa_id: UUID,
    evento_id: UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    await _get_placa_row_or_404(db, placa_id)
    evento = await _get_evento_or_404(db, evento_id, placa_id)

    if current_user.role != Role.ADMINISTRADOR and evento.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Você não tem permissão para excluir um evento criado por outro agente."
            ),
        )

    if evento.tipo_evento == TipoEvento.CRIACAO:
        total_ativos = await evento_functions.count_active_eventos_placa(db, placa_id)
        if total_ativos <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Não é permitido excluir o evento inicial de criação quando "
                    "for o único evento da placa. Para remover a placa inteira, "
                    "utilize DELETE /placas/{placa_id}."
                ),
            )

    await evento_functions.soft_delete_evento(db, evento)
