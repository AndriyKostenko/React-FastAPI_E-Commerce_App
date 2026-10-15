"""
Avatar images: checked, re-encoded and kept in the public catalogue bucket.

An avatar is public (anyone with its URL can load it), so the stored file is
never the uploaded one: it is decoded and re-encoded as a square WebP, which
drops every metadata block a phone adds -- EXIF GPS coordinates included.

The users row keeps the object *key* (``avatars/<user id>/<random>.webp``);
the public origin is added on the way out (``AvatarUrlResolver``), as
product-service does for catalogue images.
"""

import base64
import hashlib
from abc import ABC, abstractmethod
from asyncio import to_thread
from io import BytesIO
from typing import Protocol, cast
from urllib.parse import quote
from uuid import UUID, uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image, ImageOps, UnidentifiedImageError

from settings import Settings


AVATAR_PREFIX = "avatars"


class InvalidAvatarError(ValueError):
    """The upload is not an image this service accepts."""


class AvatarStorageUnavailableError(RuntimeError):
    """No object store is configured, or it could not be reached."""


class AvatarImageProcessor:
    """
    Turns an uploaded file into the avatar that is stored.

    The type is read from the file's own first bytes (the client's
    Content-Type and filename are not trusted); only JPEG, PNG and WebP are
    accepted. The picture is turned upright (EXIF orientation), cropped to a
    centred square and scaled to ``size`` pixels.
    """

    # A decompression bomb is a tiny file that decodes to a gigantic image;
    # anything over this many pixels is refused before it is decoded.
    MAX_SOURCE_PIXELS = 40_000_000
    _SIGNATURES: tuple[tuple[bytes, str], ...] = (
        (b"\xff\xd8\xff", "JPEG"),
        (b"\x89PNG\r\n\x1a\n", "PNG"),
    )

    def __init__(self, size: int, max_bytes: int) -> None:
        self._size = size
        self._max_bytes = max_bytes

    def _format_of(self, content: bytes) -> str | None:
        for signature, name in self._SIGNATURES:
            if content.startswith(signature):
                return name
        if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            return "WEBP"
        return None

    def process(self, content: bytes) -> bytes:
        if not content:
            raise InvalidAvatarError("The file is empty")
        if len(content) > self._max_bytes:
            raise InvalidAvatarError(f"The image must be at most {self._max_bytes // (1024 * 1024)} MB")
        expected_format = self._format_of(content)
        if expected_format is None:
            raise InvalidAvatarError("Upload a JPEG, PNG or WebP image")

        try:
            with Image.open(BytesIO(content), formats=[expected_format]) as source:
                width, height = source.size
                if width * height > self.MAX_SOURCE_PIXELS:
                    raise InvalidAvatarError("The image is too large")
                upright = ImageOps.exif_transpose(source)
                # Keep transparency where the source has it; everything else is RGB.
                mode = "RGBA" if upright.mode in ("RGBA", "LA", "P") else "RGB"
                square = ImageOps.fit(
                    upright.convert(mode), (self._size, self._size), method=Image.Resampling.LANCZOS
                )
                output = BytesIO()
                # No exif= / icc_profile= arguments: the new file carries no metadata.
                square.save(output, format="WEBP", quality=85, method=4)
                return output.getvalue()
        except InvalidAvatarError:
            raise
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
            raise InvalidAvatarError("The image could not be read") from error


class AvatarStore(ABC):
    @abstractmethod
    async def put(self, key: str, content: bytes) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...


class S3Client(Protocol):
    """The part of boto3's S3 client the avatar store uses."""

    def put_object(self, **kwargs: object) -> dict[str, object]: ...

    def delete_object(self, **kwargs: object) -> dict[str, object]: ...


class S3AvatarStore(AvatarStore):
    """The catalogue bucket, under ``avatars/`` only."""

    def __init__(self, settings: Settings, client: S3Client | None = None) -> None:
        if not settings.AWS_S3_CATALOGUE_BUCKET:
            raise AvatarStorageUnavailableError("AWS_S3_CATALOGUE_BUCKET is required when OBJECT_STORAGE_BACKEND=s3")
        self._bucket = settings.AWS_S3_CATALOGUE_BUCKET
        self._client = client or self._create_client(settings)

    @staticmethod
    def _create_client(settings: Settings) -> S3Client:
        credentials: dict[str, str] = {}
        if settings.AWS_S3_ACCESS_KEY_ID and settings.AWS_S3_SECRET_ACCESS_KEY:
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

    @staticmethod
    def _checked(key: str) -> str:
        # Keys are built by AvatarService, but nothing outside avatars/ may
        # ever be written or deleted through this store.
        if not key.startswith(f"{AVATAR_PREFIX}/") or ".." in key.split("/"):
            raise ValueError(f"Not an avatar key: {key!r}")
        return key

    async def put(self, key: str, content: bytes) -> None:
        request: dict[str, object] = {
            "Bucket": self._bucket,
            "Key": self._checked(key),
            "Body": content,
            "ContentType": "image/webp",
            # Each upload gets a new key, so an object never changes once written.
            "CacheControl": "public, max-age=31536000, immutable",
            "ChecksumSHA256": base64.b64encode(hashlib.sha256(content).digest()).decode("ascii"),
            "ServerSideEncryption": "AES256",
        }
        try:
            await to_thread(self._client.put_object, **request)
        except (BotoCoreError, ClientError) as error:
            raise AvatarStorageUnavailableError(f"Could not store avatar {key}: {error}") from error

    async def delete(self, key: str) -> None:
        try:
            await to_thread(self._client.delete_object, Bucket=self._bucket, Key=self._checked(key))
        except (BotoCoreError, ClientError) as error:
            raise AvatarStorageUnavailableError(f"Could not delete avatar {key}: {error}") from error


class AvatarStoreFactory:
    """The store for the configured backend, one per process (a boto3 client
    is thread-safe and expensive to build). None when there is no object store."""

    _instance: AvatarStore | None = None

    @classmethod
    def get(cls, settings: Settings) -> AvatarStore | None:
        if settings.OBJECT_STORAGE_BACKEND != "s3":
            return None
        if cls._instance is None:
            cls._instance = S3AvatarStore(settings)
        return cls._instance


class AvatarKeys:
    """Where a user's avatars are kept, and whether a stored value is one of ours."""

    @staticmethod
    def new(user_id: UUID) -> str:
        # A new key per upload: the public URL changes with the picture, so no
        # cache anywhere keeps showing the old one.
        return f"{AVATAR_PREFIX}/{user_id}/{uuid4().hex}.webp"

    @staticmethod
    def owned_by(value: str | None, user_id: UUID) -> bool:
        """True for a key this service stored for the user (not a Google picture URL)."""
        return bool(value) and str(value).startswith(f"{AVATAR_PREFIX}/{user_id}/")


class AvatarUrlResolver:
    """
    A users.image value -> a URL a browser can load.

    A stored key gets the catalogue bucket's public origin; a value that is
    already a URL (a Google profile picture) passes through untouched.
    """

    _PASSTHROUGH_PREFIXES = ("http://", "https://")

    def __init__(self, public_base_url: str | None) -> None:
        self._base = public_base_url.rstrip("/") if public_base_url else None

    def resolve(self, value: str | None) -> str | None:
        if not value or value.startswith(self._PASSTHROUGH_PREFIXES):
            return value
        if self._base is None:
            # A key with no public origin configured cannot be shown.
            return None
        return f"{self._base}/{quote(value, safe='/')}"
