"""Signed, immutable references to generated print artwork."""

import base64
import hashlib
import hmac

from pydantic import BaseModel, Field, PositiveInt


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

    def signing_payload(self) -> bytes:
        return (
            f"v1|{self.key}|{self.width_px}|{self.height_px}|"
            f"{self.embedded_dpi}|{self.sha256}"
        ).encode("utf-8")


def sign_artwork_asset(asset: GeneratedArtworkAsset, secret: str) -> str:
    """Return a URL-safe provenance signature for measured asset metadata."""

    digest = hmac.new(
        secret.encode("utf-8"), asset.signing_payload(), hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def verify_artwork_asset(asset: GeneratedArtworkAsset, secret: str) -> bool:
    """Prove the asset manifest was issued by a trusted backend service."""

    return hmac.compare_digest(asset.token, sign_artwork_asset(asset, secret))
