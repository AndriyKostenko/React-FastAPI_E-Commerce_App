"""
Private storage for the photos a customer sends with a return.

They are evidence about a customer's parcel, so they are never public: under
``local`` they stay out of MEDIA_ROOT (which product-service serves to anyone),
under ``s3`` they live in the private bucket. Either way only the admin route
reads them back, streaming the bytes itself -- no presigned link is handed
out, because a link works for anyone it is forwarded to while the route
checks the admin on every request.
"""

import base64
import hashlib
from abc import ABC, abstractmethod
from asyncio import to_thread
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol, cast

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from shared.settings import Settings


@dataclass(frozen=True)
class EvidencePhoto:
    """An uploaded photo, checked and typed from its own bytes."""

    content: bytes
    content_type: str
    extension: str


class EvidencePhotoSniffer:
    """
    The real image type, read from the file's first bytes.

    The client's Content-Type and filename are not trusted: anything that is
    not a JPEG, PNG or WebP is refused, whatever it claims to be.
    """

    @staticmethod
    def sniff(content: bytes) -> EvidencePhoto | None:
        if content.startswith(b"\xff\xd8\xff"):
            return EvidencePhoto(content, "image/jpeg", "jpg")
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return EvidencePhoto(content, "image/png", "png")
        if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            return EvidencePhoto(content, "image/webp", "webp")
        return None


class ReturnEvidenceStorage(ABC):
    @abstractmethod
    async def save(self, key: str, photo: EvidencePhoto) -> None: ...

    @abstractmethod
    async def load(self, key: str) -> bytes | None: ...


class LocalReturnEvidenceStorage(ReturnEvidenceStorage):
    def __init__(self, settings: Settings) -> None:
        self._root = Path(settings.RETURN_EVIDENCE_ROOT or "./private-media").resolve() / "return-evidence"

    def _path(self, key: str) -> Path:
        # Keys are built by the service, but a key must never climb out of
        # the root whatever it contains.
        relative = PurePosixPath(key)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Invalid evidence key: {key!r}")
        path = (self._root / relative).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError(f"Invalid evidence key: {key!r}")
        return path

    async def save(self, key: str, photo: EvidencePhoto) -> None:
        path = self._path(key)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(photo.content)

        await to_thread(write)

    async def load(self, key: str) -> bytes | None:
        path = self._path(key)

        def read() -> bytes | None:
            return path.read_bytes() if path.is_file() else None

        return await to_thread(read)


class S3Client(Protocol):
    """The part of boto3's S3 client the evidence store uses."""

    def put_object(self, **kwargs: object) -> dict[str, object]: ...

    def get_object(self, **kwargs: object) -> dict[str, BinaryIO]: ...


class ReturnEvidenceStorageError(RuntimeError):
    """The private bucket could not be written to or read from."""


class S3ReturnEvidenceStorage(ReturnEvidenceStorage):
    """The private bucket, under ``return-evidence/`` -- the only prefix
    order-service's credentials may touch."""

    PREFIX = "return-evidence"

    def __init__(self, settings: Settings, client: S3Client | None = None) -> None:
        if not settings.AWS_S3_PRIVATE_BUCKET:
            raise RuntimeError("AWS_S3_PRIVATE_BUCKET is required when OBJECT_STORAGE_BACKEND=s3")
        self._bucket = settings.AWS_S3_PRIVATE_BUCKET
        self._kms_key_id = settings.AWS_S3_KMS_KEY_ID
        self._client = client or self._create_client(settings)

    @staticmethod
    def _create_client(settings: Settings) -> S3Client:
        credentials: dict[str, str] = {}
        if settings.AWS_S3_ACCESS_KEY_ID and settings.AWS_S3_SECRET_ACCESS_KEY:
            # An S3-compatible server (the local SeaweedFS). In AWS both are
            # unset and the default chain finds the workload role.
            credentials = {
                "aws_access_key_id": settings.AWS_S3_ACCESS_KEY_ID.get_secret_value(),
                "aws_secret_access_key": settings.AWS_S3_SECRET_ACCESS_KEY.get_secret_value(),
            }
        config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if settings.AWS_S3_ENDPOINT_URL else "auto"},
            retries={"max_attempts": 3, "mode": "standard"},
        )
        client = boto3.client(
            "s3",
            region_name=settings.AWS_S3_REGION,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            config=config,
            **credentials,
        )
        return cast(S3Client, client)

    def _object_key(self, key: str) -> str:
        relative = PurePosixPath(key)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError(f"Invalid evidence key: {key!r}")
        return f"{self.PREFIX}/{relative}"

    async def save(self, key: str, photo: EvidencePhoto) -> None:
        request: dict[str, object] = {
            "Bucket": self._bucket,
            "Key": self._object_key(key),
            "Body": photo.content,
            "ContentType": photo.content_type,
            "CacheControl": "private, no-store",
            # S3 recomputes the digest and refuses a write that does not match.
            "ChecksumSHA256": base64.b64encode(hashlib.sha256(photo.content).digest()).decode("ascii"),
        }
        if self._kms_key_id:
            request.update({"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": self._kms_key_id})
        else:
            request["ServerSideEncryption"] = "AES256"
        try:
            await to_thread(self._client.put_object, **request)
        except (BotoCoreError, ClientError) as error:
            raise ReturnEvidenceStorageError(f"Could not store return evidence {key}: {error}") from error

    async def load(self, key: str) -> bytes | None:
        object_key = self._object_key(key)

        def read() -> bytes | None:
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=object_key)
            except ClientError as error:
                if str(error.response.get("Error", {}).get("Code", "")) in {"NoSuchKey", "404", "NotFound"}:
                    return None
                raise
            return response["Body"].read()

        try:
            return await to_thread(read)
        except (BotoCoreError, ClientError) as error:
            raise ReturnEvidenceStorageError(f"Could not read return evidence {key}: {error}") from error


class ReturnEvidenceStorageFactory:
    """The store for the configured backend; one per process (boto3's client
    is thread-safe and expensive to build)."""

    _instance: ReturnEvidenceStorage | None = None

    @classmethod
    def get(cls, settings: Settings) -> ReturnEvidenceStorage:
        if cls._instance is None:
            if settings.OBJECT_STORAGE_BACKEND == "s3":
                cls._instance = S3ReturnEvidenceStorage(settings)
            else:
                cls._instance = LocalReturnEvidenceStorage(settings)
        return cls._instance
