"""
Object stores: the one place product-service writes and reads image bytes.

Two stores exist and are never mixed (``ObjectStorageProvider``):
  catalogue -- public-read: product, variant and category images;
  private   -- generated designs, reached only through presigned URLs.

Each is an ``ObjectStore``, so the services above never see boto3 or the
disk. ``S3ObjectStore`` is the production adapter; ``LocalObjectStore`` keeps
the ``local`` backend (files under MEDIA_ROOT, served at /media) working.
"""

import base64
import os
from abc import ABC, abstractmethod
from asyncio import to_thread
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol
from urllib.parse import quote

from botocore.exceptions import BotoCoreError, ClientError


class ObjectStorageError(Exception):
    """The store could not be written to or read from."""


class ObjectMissingError(ObjectStorageError):
    """The key names no stored object."""


class ObjectStorageNotConfiguredError(RuntimeError):
    """A setting the configured backend needs is missing; the message names it."""


class S3Client(Protocol):
    """The part of boto3's S3 client the stores use."""

    def put_object(self, **kwargs: object) -> dict[str, object]: ...

    def get_object(self, **kwargs: object) -> dict[str, BinaryIO]: ...

    def head_object(self, **kwargs: object) -> dict[str, object]: ...

    def generate_presigned_url(
        self, ClientMethod: str, Params: dict[str, str], ExpiresIn: int
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class ObjectWrite:
    """One object to store, with the headers it is served with."""

    key: str
    body: bytes
    content_type: str
    cache_control: str
    content_disposition: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    # Hex SHA-256 of ``body``. S3 recomputes it and refuses the write on a
    # mismatch, so a corrupted upload never becomes the stored object.
    sha256: str | None = None


class ObjectStore(ABC):
    @abstractmethod
    async def put(self, obj: ObjectWrite) -> None: ...

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        """The object's bytes, or None when nothing is stored under the key."""

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def presign_get(
        self,
        key: str,
        ttl_seconds: int,
        download_filename: str | None = None,
        content_type: str | None = None,
    ) -> str:
        """A URL a browser can GET the object from until it expires."""


class S3ObjectStore(ObjectStore):
    """One bucket. Every write is server-side encrypted (SSE-S3, or SSE-KMS
    when a key is configured) and never carries an ACL: access is decided by
    the bucket policy alone."""

    def __init__(self, client: S3Client, bucket: str, kms_key_id: str | None = None) -> None:
        self._client = client
        self._bucket = bucket
        self._kms_key_id = kms_key_id

    @property
    def bucket(self) -> str:
        return self._bucket

    async def put(self, obj: ObjectWrite) -> None:
        request: dict[str, object] = {
            "Bucket": self._bucket,
            "Key": obj.key,
            "Body": obj.body,
            "ContentType": obj.content_type,
            "CacheControl": obj.cache_control,
            "Metadata": obj.metadata,
        }
        if obj.content_disposition:
            request["ContentDisposition"] = obj.content_disposition
        if obj.sha256:
            request["ChecksumSHA256"] = base64.b64encode(bytes.fromhex(obj.sha256)).decode("ascii")
        if self._kms_key_id:
            request["ServerSideEncryption"] = "aws:kms"
            request["SSEKMSKeyId"] = self._kms_key_id
        else:
            request["ServerSideEncryption"] = "AES256"
        try:
            await to_thread(self._client.put_object, **request)
        except (BotoCoreError, ClientError) as error:
            raise ObjectStorageError(f"Could not store s3://{self._bucket}/{obj.key}: {error}") from error

    async def get(self, key: str) -> bytes | None:
        def read() -> bytes | None:
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=key)
            except ClientError as error:
                if self._is_missing(error):
                    return None
                raise
            return response["Body"].read()

        try:
            return await to_thread(read)
        except (BotoCoreError, ClientError) as error:
            raise ObjectStorageError(f"Could not read s3://{self._bucket}/{key}: {error}") from error

    async def exists(self, key: str) -> bool:
        def head() -> bool:
            try:
                self._client.head_object(Bucket=self._bucket, Key=key)
            except ClientError as error:
                if self._is_missing(error):
                    return False
                raise
            return True

        try:
            return await to_thread(head)
        except (BotoCoreError, ClientError) as error:
            raise ObjectStorageError(f"Could not check s3://{self._bucket}/{key}: {error}") from error

    async def presign_get(
        self,
        key: str,
        ttl_seconds: int,
        download_filename: str | None = None,
        content_type: str | None = None,
    ) -> str:
        params = {"Bucket": self._bucket, "Key": key}
        if download_filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{download_filename}"'
        if content_type:
            params["ResponseContentType"] = content_type
        try:
            # Signing is local computation; no request leaves the process.
            return self._client.generate_presigned_url("get_object", Params=params, ExpiresIn=ttl_seconds)
        except (BotoCoreError, ClientError) as error:
            raise ObjectStorageError(f"Could not presign s3://{self._bucket}/{key}: {error}") from error

    @staticmethod
    def _is_missing(error: ClientError) -> bool:
        code = str(error.response.get("Error", {}).get("Code", ""))
        return code in {"NoSuchKey", "404", "NotFound"}


class LocalObjectStore(ObjectStore):
    """Files under one directory, served by the /media static mount.

    Only for the ``local`` backend: there is no access control here, so the
    "private" store is as reachable as the catalogue one.
    """

    def __init__(self, root: Path, public_prefix: str = "/media") -> None:
        self._root = root.resolve()
        self._public_prefix = public_prefix.rstrip("/")

    def _path(self, key: str) -> Path:
        # Keys are built by the services, but none may climb out of the root
        # whatever it contains.
        relative = PurePosixPath(key)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ObjectStorageError(f"Invalid object key: {key!r}")
        path = (self._root / relative).resolve()
        if not path.is_relative_to(self._root):
            raise ObjectStorageError(f"Invalid object key: {key!r}")
        return path

    async def put(self, obj: ObjectWrite) -> None:
        path = self._path(obj.key)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Written aside and renamed, so a reader never sees half a file.
            temporary = path.with_name(f".{path.name}.tmp")
            try:
                temporary.write_bytes(obj.body)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)

        try:
            await to_thread(write)
        except OSError as error:
            raise ObjectStorageError(f"Could not store {obj.key}: {error}") from error

    async def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return await to_thread(lambda: path.read_bytes() if path.is_file() else None)

    async def exists(self, key: str) -> bool:
        path = self._path(key)
        return await to_thread(path.is_file)

    async def presign_get(
        self,
        key: str,
        ttl_seconds: int,
        download_filename: str | None = None,
        content_type: str | None = None,
    ) -> str:
        if not await self.exists(key):
            raise ObjectMissingError(f"No stored object under {key!r}")
        # Relative on purpose: the browser reaches media through the API
        # gateway's origin, not product-service directly.
        return f"{self._public_prefix}/{quote(key, safe='/')}"
