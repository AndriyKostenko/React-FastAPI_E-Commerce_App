from pydantic import BaseModel, Field

from shared.contracts.artwork import GeneratedArtworkAsset


class ArtworkDownloadRequest(BaseModel):
    """The signed manifest stored on a paid order line.

    The manifest is the credential: only a caller holding the manifest this
    service issued at generation time can obtain a download for the object.
    """

    asset: GeneratedArtworkAsset


class ArtworkDownloadResponse(BaseModel):
    download_url: str
    filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_type: str = "image/png"
    expires_in_seconds: int
