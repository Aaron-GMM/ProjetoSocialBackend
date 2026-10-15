from __future__ import annotations

import io
import mimetypes
import posixpath
from datetime import datetime, timezone
from typing import BinaryIO
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

from minio import Minio
from minio.error import S3Error
from starlette.concurrency import run_in_threadpool

from src.core.config import settings


class StorageError(Exception):
    """Exceção base para erros em operações no Object Storage."""


class MinioStorageService:
    """Serviço de gerenciamento de arquivos e objetos no MinIO/S3.

    Implementa pool de conexões (Keep-Alive via urllib3/Minio SDK) e provê
    métodos simplificados síncronos e assíncronos para a equipe.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket_name: str | None = None,
        secure: bool | None = None,
        public_url: str | None = None,
    ) -> None:
        self.endpoint = endpoint or settings.MINIO_ENDPOINT
        self.access_key = (
            access_key if access_key is not None else settings.MINIO_APP_ACCESS_KEY
        )
        self.secret_key = (
            secret_key if secret_key is not None else settings.MINIO_APP_SECRET_KEY
        )
        self.bucket_name = bucket_name or settings.MINIO_BUCKET_NAME
        self.secure = secure if secure is not None else settings.MINIO_SECURE
        self.public_url = public_url or settings.MINIO_PUBLIC_URL

        self._client: Minio | None = None

    @property
    def client(self) -> Minio:
        """Instancia o cliente Minio sob demanda (Lazy Singleton)."""
        if self._client is None:
            self._client = Minio(
                endpoint=self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
        return self._client

    def ensure_bucket_exists(self, bucket_name: str | None = None) -> None:
        """Garante a existência do bucket de forma idempotente."""
        target_bucket = bucket_name or self.bucket_name
        try:
            if not self.client.bucket_exists(target_bucket):
                self.client.make_bucket(target_bucket)
        except S3Error as exc:
            raise StorageError(
                f"Erro ao verificar/criar bucket '{target_bucket}': {exc}"
            ) from exc

    async def ensure_bucket_exists_async(self, bucket_name: str | None = None) -> None:
        """Versão assíncrona para garantir existência do bucket."""
        await run_in_threadpool(self.ensure_bucket_exists, bucket_name)

    @staticmethod
    def generate_object_path(
        filename: str,
        context: str = "placas",
        entity_id: str | int | None = None,
        now: datetime | None = None,
    ) -> str:
        """Gera um caminho estruturado no padrão:

        {context}/{ano}/{mes:02d}/{dia:02d}/{prefixo}_{uuid}.{ext}
        Exemplo: placas/2026/10/15/placa_42_a8f9c1b2.jpg
        """
        dt = now or datetime.now(timezone.utc)
        ext = posixpath.splitext(filename)[1].lower()
        if not ext:
            ext = ".jpg"

        random_suffix = uuid4().hex[:8]
        prefix = f"{context}_{entity_id}" if entity_id is not None else context
        unique_name = f"{prefix}_{random_suffix}{ext}"

        return posixpath.join(
            context,
            f"{dt.year:04d}",
            f"{dt.month:02d}",
            f"{dt.day:02d}",
            unique_name,
        )

    def upload_file(
        self,
        file_data: bytes | BinaryIO,
        filename: str,
        content_type: str | None = None,
        context: str = "placas",
        entity_id: str | int | None = None,
        bucket_name: str | None = None,
    ) -> str:
        """Faz o upload síncrono de um arquivo para o MinIO.

        Retorna o object_name (caminho relativo) salvo no bucket.
        """
        target_bucket = bucket_name or self.bucket_name
        object_name = self.generate_object_path(
            filename=filename, context=context, entity_id=entity_id
        )

        resolved_content_type = content_type
        if not resolved_content_type:
            guessed_type, _ = mimetypes.guess_type(filename)
            resolved_content_type = guessed_type or "application/octet-stream"

        if isinstance(file_data, bytes):
            stream = io.BytesIO(file_data)
            length = len(file_data)
        else:
            stream = file_data
            # Se for um stream seekable, calcula o tamanho restante
            if hasattr(stream, "seek") and hasattr(stream, "tell"):
                current_pos = stream.tell()
                stream.seek(0, io.SEEK_END)
                length = stream.tell() - current_pos
                stream.seek(current_pos)
            else:
                length = -1

        try:
            self.client.put_object(
                bucket_name=target_bucket,
                object_name=object_name,
                data=stream,
                length=length,
                part_size=10 * 1024 * 1024 if length < 0 else 0,
                content_type=resolved_content_type,
            )
            return object_name
        except S3Error as exc:
            raise StorageError(
                f"Falha no upload para o MinIO no caminho '{object_name}': {exc}"
            ) from exc

    async def upload_file_async(
        self,
        file_data: bytes | BinaryIO,
        filename: str,
        content_type: str | None = None,
        context: str = "placas",
        entity_id: str | int | None = None,
        bucket_name: str | None = None,
    ) -> str:
        """Wrapper assíncrono para upload_file sem bloquear o event loop."""
        return await run_in_threadpool(
            self.upload_file,
            file_data=file_data,
            filename=filename,
            content_type=content_type,
            context=context,
            entity_id=entity_id,
            bucket_name=bucket_name,
        )

    def get_presigned_url(
        self,
        object_name: str,
        expires_seconds: int = 3600,
        bucket_name: str | None = None,
        inline: bool = True,
    ) -> str:
        """Gera URL pré-assinada de visualização (Presigned URL).

        Configura response-content-disposition='inline' para visualização direta
        no navegador/mobile e reescreve o host para a URL pública se necessário.
        """
        target_bucket = bucket_name or self.bucket_name
        response_headers = {"response-content-disposition": "inline"} if inline else {}

        try:
            from datetime import timedelta

            raw_url = self.client.presigned_get_object(
                bucket_name=target_bucket,
                object_name=object_name,
                expires=timedelta(seconds=expires_seconds),
                response_headers=response_headers,
            )

            # Ajusta o hostname para a URL pública (resolve issue em Docker Compose)
            if self.public_url:
                parsed_public = urlparse(self.public_url)
                parsed_raw = urlparse(raw_url)
                # Mantém o scheme e netloc da URL pública configurada
                adjusted_url = urlunparse(
                    (
                        parsed_public.scheme or parsed_raw.scheme,
                        parsed_public.netloc or parsed_raw.netloc,
                        parsed_raw.path,
                        parsed_raw.params,
                        parsed_raw.query,
                        parsed_raw.fragment,
                    )
                )
                return adjusted_url

            return raw_url
        except S3Error as exc:
            raise StorageError(
                f"Erro ao gerar presigned URL para '{object_name}': {exc}"
            ) from exc

    async def get_presigned_url_async(
        self,
        object_name: str,
        expires_seconds: int = 3600,
        bucket_name: str | None = None,
        inline: bool = True,
    ) -> str:
        """Wrapper assíncrono para get_presigned_url."""
        return await run_in_threadpool(
            self.get_presigned_url,
            object_name=object_name,
            expires_seconds=expires_seconds,
            bucket_name=bucket_name,
            inline=inline,
        )

    def delete_file(self, object_name: str, bucket_name: str | None = None) -> None:
        """Remove um objeto do bucket de forma síncrona."""
        target_bucket = bucket_name or self.bucket_name
        try:
            self.client.remove_object(
                bucket_name=target_bucket, object_name=object_name
            )
        except S3Error as exc:
            raise StorageError(
                f"Erro ao remover objeto '{object_name}': {exc}"
            ) from exc

    async def delete_file_async(
        self, object_name: str, bucket_name: str | None = None
    ) -> None:
        """Wrapper assíncrono para delete_file."""
        await run_in_threadpool(
            self.delete_file, object_name=object_name, bucket_name=bucket_name
        )


# Singleton padrão para uso direto em todo o projeto
minio_service = MinioStorageService()
