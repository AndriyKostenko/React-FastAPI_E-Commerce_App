"""
Private storage for the photos a customer sends with a return.

They are evidence about a customer's parcel, so they never go under
MEDIA_ROOT (which product-service serves to anyone): only the admin route
reads them back. The storage is a port so an S3 backend can replace the
local disk without the return service noticing.
"""

from abc import ABC, abstractmethod
from asyncio import to_thread
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

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
