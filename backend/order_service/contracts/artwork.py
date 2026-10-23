"""Signed, immutable references to generated print artwork."""

import base64
import hashlib
import hmac
from datetime import UTC, datetime

from pydantic import AwareDatetime, BaseModel, Field, PositiveInt


class GeneratedArtworkAsset(BaseModel):
    """Production metadata measured by the image service, never by the browser."""

    key: str = Field(
        min_length=1,
        max_length=512,
        pattern=r"^generated-designs/\d{4}/\d{2}/[0-9a-f]{32}\.png$",
    )
    width_px: PositiveInt = Field(le=30_000)
    height_px: PositiveInt = Field(le=30_000)
    embedded_dpi: PositiveInt = Field(ge=72, le=1_200)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    token: str = Field(min_length=43, max_length=128)
    # When the image service made the design, signed with the rest: checkout
    # refuses a design too close to being deleted as never ordered. Manifests
    # issued before the field existed have none (and are signed as v1).
    issued_at: AwareDatetime | None = None

    def signing_payload(self) -> bytes:
        measured = (
            f"{self.key}|{self.width_px}|{self.height_px}|"
            f"{self.embedded_dpi}|{self.sha256}"
        )
        if self.issued_at is None:
            return f"v1|{measured}".encode("utf-8")
        # Whole seconds in UTC, so the same instant signs the same way
        # however the browser wrote it back.
        issued = self.issued_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return f"v2|{measured}|{issued}".encode("utf-8")


def issue_time(now: datetime | None = None) -> datetime:
    """The issued_at to stamp on a new manifest: now, to the second, in UTC."""
    return (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)


def sign_artwork_asset(asset: GeneratedArtworkAsset, secret: str) -> str:
    """Return a URL-safe provenance signature for measured asset metadata."""

    digest = hmac.new(
        secret.encode("utf-8"), asset.signing_payload(), hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def verify_artwork_asset(asset: GeneratedArtworkAsset, secret: str) -> bool:
    """Prove the asset manifest was issued by a trusted backend service."""

    return hmac.compare_digest(asset.token, sign_artwork_asset(asset, secret))
