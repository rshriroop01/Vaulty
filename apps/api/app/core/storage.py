"""Object storage behind a provider interface (ARCHITECTURE.md: portable on the
riskiest dependencies). S3-compatible impl covers MinIO locally and AWS S3 in prod.

Files never flow through the API (<2s upload target): clients PUT/GET directly
against presigned URLs. Presigning uses the *public* endpoint (what the browser
can reach); head/delete use the internal endpoint (container network).
"""

from typing import Protocol

import anyio.to_thread
import boto3
from botocore.client import Config as BotoConfig

from app.core.config import get_settings

PRESIGN_TTL_SECONDS = 900


class StorageProvider(Protocol):
    async def presign_upload(self, key: str, content_type: str) -> str: ...

    async def presign_download(self, key: str, file_name: str) -> str: ...

    async def object_size(self, key: str) -> int | None:
        """Size in bytes, or None if the object doesn't exist."""
        ...

    async def get_object(self, key: str) -> bytes: ...

    async def delete_object(self, key: str) -> None: ...


class S3StorageProvider:
    def __init__(self) -> None:
        settings = get_settings()
        self._bucket = settings.s3_bucket
        boto_config = BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"})
        common = {
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
            "region_name": "us-east-1",
            "config": boto_config,
        }
        self._internal = boto3.client("s3", endpoint_url=settings.s3_endpoint_url, **common)
        self._public = boto3.client("s3", endpoint_url=settings.s3_public_endpoint_url, **common)

    async def presign_upload(self, key: str, content_type: str) -> str:
        def _sign() -> str:
            return str(
                self._public.generate_presigned_url(
                    "put_object",
                    Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
                    ExpiresIn=PRESIGN_TTL_SECONDS,
                )
            )

        return await anyio.to_thread.run_sync(_sign)

    async def presign_download(self, key: str, file_name: str) -> str:
        def _sign() -> str:
            return str(
                self._public.generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket": self._bucket,
                        "Key": key,
                        "ResponseContentDisposition": f'attachment; filename="{file_name}"',
                    },
                    ExpiresIn=PRESIGN_TTL_SECONDS,
                )
            )

        return await anyio.to_thread.run_sync(_sign)

    async def object_size(self, key: str) -> int | None:
        def _head() -> int | None:
            try:
                resp = self._internal.head_object(Bucket=self._bucket, Key=key)
                return int(resp["ContentLength"])
            except self._internal.exceptions.ClientError:
                return None

        return await anyio.to_thread.run_sync(_head)

    async def get_object(self, key: str) -> bytes:
        def _get() -> bytes:
            resp = self._internal.get_object(Bucket=self._bucket, Key=key)
            return bytes(resp["Body"].read())

        return await anyio.to_thread.run_sync(_get)

    async def delete_object(self, key: str) -> None:
        def _delete() -> None:
            self._internal.delete_object(Bucket=self._bucket, Key=key)

        await anyio.to_thread.run_sync(_delete)


def get_storage() -> StorageProvider:
    """FastAPI dependency — overridden with a fake in tests."""
    return S3StorageProvider()
