import io
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from minio.error import S3Error

from src.infrastructure.storage.minio_client import (
    MinioStorageService,
    StorageError,
)


@pytest.fixture
def mock_minio_client():
    return MagicMock()


@pytest.fixture
def storage_service(mock_minio_client):
    service = MinioStorageService(
        endpoint="localhost:9000",
        access_key="test-access",
        secret_key="test-secret",
        bucket_name="test-bucket",
        secure=False,
        public_url="http://localhost:9000",
    )
    service._client = mock_minio_client
    return service


def test_lazy_client_initialization():
    service = MinioStorageService(
        endpoint="custom-endpoint:9000",
        access_key="my-key",
        secret_key="my-secret",
        bucket_name="custom-bucket",
        secure=True,
    )
    with patch("src.infrastructure.storage.minio_client.Minio") as mock_minio_cls:
        client = service.client
        mock_minio_cls.assert_called_once_with(
            endpoint="custom-endpoint:9000",
            access_key="my-key",
            secret_key="my-secret",
            secure=True,
        )
        assert client == mock_minio_cls.return_value
        # Reutilização do singleton interno (lazy property)
        assert service.client == client


def test_ensure_bucket_exists_when_not_existing(storage_service, mock_minio_client):
    mock_minio_client.bucket_exists.return_value = False

    storage_service.ensure_bucket_exists("novo-bucket")

    mock_minio_client.bucket_exists.assert_called_once_with("novo-bucket")
    mock_minio_client.make_bucket.assert_called_once_with("novo-bucket")


def test_ensure_bucket_exists_when_already_exists(storage_service, mock_minio_client):
    mock_minio_client.bucket_exists.return_value = True

    storage_service.ensure_bucket_exists()

    mock_minio_client.bucket_exists.assert_called_once_with("test-bucket")
    mock_minio_client.make_bucket.assert_not_called()


def test_ensure_bucket_exists_s3_error(storage_service, mock_minio_client):
    mock_minio_client.bucket_exists.side_effect = S3Error(
        code="AccessDenied",
        message="Acesso negado",
        resource="/test-bucket",
        request_id="req-1",
        host_id="host-1",
        response=MagicMock(status=403),
    )

    with pytest.raises(StorageError) as exc_info:
        storage_service.ensure_bucket_exists()
    assert "Erro ao verificar/criar bucket" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ensure_bucket_exists_async(storage_service, mock_minio_client):
    mock_minio_client.bucket_exists.return_value = True

    await storage_service.ensure_bucket_exists_async("async-bucket")

    mock_minio_client.bucket_exists.assert_called_once_with("async-bucket")


def test_generate_object_path():
    fixed_date = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Sem extensão e sem entity_id
    path1 = MinioStorageService.generate_object_path(
        filename="foto", context="placas", now=fixed_date
    )
    assert path1.startswith("placas/2026/10/15/placas_")
    assert path1.endswith(".jpg")

    # 2. Com entity_id e extensão específica
    path2 = MinioStorageService.generate_object_path(
        filename="sinalizacao.PNG",
        context="vistorias",
        entity_id=42,
        now=fixed_date,
    )
    assert path2.startswith("vistorias/2026/10/15/vistorias_42_")
    assert path2.endswith(".png")


def test_upload_file_bytes(storage_service, mock_minio_client):
    file_bytes = b"conteudo da imagem fake"
    filename = "imagem.jpg"

    object_name = storage_service.upload_file(
        file_data=file_bytes,
        filename=filename,
        context="placas",
        entity_id=10,
    )

    assert object_name.startswith("placas/")
    assert object_name.endswith(".jpg")
    mock_minio_client.put_object.assert_called_once()
    _, kwargs = mock_minio_client.put_object.call_args
    assert kwargs["bucket_name"] == "test-bucket"
    assert kwargs["length"] == len(file_bytes)
    assert kwargs["content_type"] == "image/jpeg"


def test_upload_file_stream_with_explicit_content_type(
    storage_service, mock_minio_client
):
    stream = io.BytesIO(b"dados webp")

    object_name = storage_service.upload_file(
        file_data=stream,
        filename="imagem_sem_extensao",
        content_type="image/webp",
    )

    mock_minio_client.put_object.assert_called_once()
    _, kwargs = mock_minio_client.put_object.call_args
    assert kwargs["content_type"] == "image/webp"
    assert kwargs["length"] == len(b"dados webp")
    assert object_name.endswith(".jpg")  # fallback de extensão


def test_upload_file_non_seekable_stream(storage_service, mock_minio_client):
    class NonSeekableStream:
        def read(self, size=-1):
            return b""

    stream = NonSeekableStream()
    storage_service.upload_file(file_data=stream, filename="stream.jpg")

    mock_minio_client.put_object.assert_called_once()
    _, kwargs = mock_minio_client.put_object.call_args
    assert kwargs["length"] == -1
    assert kwargs["part_size"] == 10 * 1024 * 1024


def test_upload_file_s3_error(storage_service, mock_minio_client):
    mock_minio_client.put_object.side_effect = S3Error(
        code="InternalError",
        message="Erro interno",
        resource="/test-bucket",
        request_id="req-2",
        host_id="host-2",
        response=MagicMock(status=500),
    )

    with pytest.raises(StorageError) as exc_info:
        storage_service.upload_file(file_data=b"teste", filename="erro.jpg")
    assert "Falha no upload para o MinIO" in str(exc_info.value)


@pytest.mark.asyncio
async def test_upload_file_async(storage_service, mock_minio_client):
    object_name = await storage_service.upload_file_async(
        file_data=b"async upload bytes",
        filename="foto_async.png",
    )

    assert object_name.endswith(".png")
    mock_minio_client.put_object.assert_called_once()


def test_get_presigned_url_with_public_host_rewrite(storage_service, mock_minio_client):
    # Simula o MinIO gerando uma URL com host interno da rede Docker
    mock_minio_client.presigned_get_object.return_value = (
        "http://minio:9000/test-bucket/placas/foto.jpg?token=abc123xyz"
    )

    url = storage_service.get_presigned_url(
        object_name="placas/foto.jpg",
        expires_seconds=1800,
        inline=True,
    )

    # O host 'minio:9000' deve ser reescrito para 'localhost:9000' da URL pública
    assert url.startswith("http://localhost:9000/test-bucket/placas/foto.jpg?")
    assert "token=abc123xyz" in url
    mock_minio_client.presigned_get_object.assert_called_once()
    _, kwargs = mock_minio_client.presigned_get_object.call_args
    assert kwargs["response_headers"] == {"response-content-disposition": "inline"}


def test_get_presigned_url_inline_false(storage_service, mock_minio_client):
    storage_service.public_url = ""
    mock_minio_client.presigned_get_object.return_value = (
        "http://localhost:9000/test-bucket/foto.jpg?token=123"
    )

    url = storage_service.get_presigned_url(object_name="foto.jpg", inline=False)

    assert url == "http://localhost:9000/test-bucket/foto.jpg?token=123"
    _, kwargs = mock_minio_client.presigned_get_object.call_args
    assert kwargs["response_headers"] == {}


def test_get_presigned_url_s3_error(storage_service, mock_minio_client):
    mock_minio_client.presigned_get_object.side_effect = S3Error(
        code="NoSuchKey",
        message="Chave nao encontrada",
        resource="/test-bucket/inexistente.jpg",
        request_id="req-3",
        host_id="host-3",
        response=MagicMock(status=404),
    )

    with pytest.raises(StorageError) as exc_info:
        storage_service.get_presigned_url(object_name="inexistente.jpg")
    assert "Erro ao gerar presigned URL" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_presigned_url_async(storage_service, mock_minio_client):
    mock_minio_client.presigned_get_object.return_value = (
        "http://minio:9000/test-bucket/foto.jpg?token=123"
    )

    url = await storage_service.get_presigned_url_async(object_name="foto.jpg")

    assert url.startswith("http://localhost:9000/test-bucket/foto.jpg")


def test_delete_file(storage_service, mock_minio_client):
    storage_service.delete_file("placas/foto.jpg")
    mock_minio_client.remove_object.assert_called_once_with(
        bucket_name="test-bucket", object_name="placas/foto.jpg"
    )


def test_delete_file_s3_error(storage_service, mock_minio_client):
    mock_minio_client.remove_object.side_effect = S3Error(
        code="InternalError",
        message="Erro ao remover",
        resource="/test-bucket",
        request_id="req-4",
        host_id="host-4",
        response=MagicMock(status=500),
    )

    with pytest.raises(StorageError) as exc_info:
        storage_service.delete_file("placas/erro.jpg")
    assert "Erro ao remover objeto" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_file_async(storage_service, mock_minio_client):
    await storage_service.delete_file_async("placas/foto_async.jpg")
    mock_minio_client.remove_object.assert_called_once_with(
        bucket_name="test-bucket", object_name="placas/foto_async.jpg"
    )
