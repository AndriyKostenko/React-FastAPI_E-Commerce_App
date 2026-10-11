"""Signed, immutable references to generated print artwork."""

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
