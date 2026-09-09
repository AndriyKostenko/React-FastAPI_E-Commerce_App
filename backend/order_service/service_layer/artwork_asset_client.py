"""Internal product-service client for resolving stored print files."""

from types import TracebackType
from typing import Self

from httpx import AsyncClient, HTTPStatusError, RequestError
from pydantic import BaseModel

from shared.contracts.artwork import GeneratedArtworkAsset
from shared.exceptions.base_exceptions import BaseAPIException
from shared.settings import Settings


class ArtworkDownloadError(BaseAPIException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=502, detail=detail)


class ArtworkDownload(BaseModel):
    """A short-lived way for the operator's browser to fetch one print file."""

    download_url: str
    filename: str
    sha256: str
    content_type: str = "image/png"
    expires_in_seconds: int


class ArtworkAssetClient:
    """Exchanges a stored artwork manifest for a download URL.

    product_service owns the artwork object, so order_service never reads the
    bytes itself: it presents the signed manifest captured with the order and
    receives back a URL the operator can open. Presenting the manifest is what
    proves the request belongs to a real paid line.
    """

    def __init__(self, settings: Settings, http_client: AsyncClient | None = None):
        self.settings = settings
        self._client = http_client
        self._owns_client = http_client is None

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def start(self) -> None:
        if self._client is None:
            self._client = AsyncClient(timeout=10.0)

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def get_download(self, asset: GeneratedArtworkAsset) -> ArtworkDownload:
        await self.start()
        assert self._client is not None
        try:
            response = await self._client.post(
                f"{self.settings.FULL_PRODUCT_SERVICE_URL}/artwork/download-link",
                json={"asset": asset.model_dump(mode="json")},
            )
            response.raise_for_status()
            return ArtworkDownload(**response.json())
        except HTTPStatusError as exc:
            raise ArtworkDownloadError(
                f"Product service refused the artwork manifest: {exc.response.text}"
            ) from exc
        except RequestError as exc:
            raise ArtworkDownloadError(
                f"Unable to reach product service for artwork: {exc}"
            ) from exc
