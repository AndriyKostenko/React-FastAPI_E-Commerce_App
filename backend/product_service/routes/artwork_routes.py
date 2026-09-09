from fastapi import APIRouter, Request, status

from dependencies.dependencies import artwork_asset_service_dependency
from helpers.internal_access_helper import internal_access_helper
from schemas.artwork_schema import ArtworkDownloadRequest, ArtworkDownloadResponse
from shared.exceptions.base_exceptions import BaseAPIException


artwork_routes = APIRouter(tags=["artwork"])


class ArtworkAccessForbiddenError(BaseAPIException):
    """Raised when a print-file download is requested from outside the mesh."""

    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            detail="Artwork downloads are available to internal services only",
        )


@artwork_routes.post(
    "/artwork/download-link",
    response_model=ArtworkDownloadResponse,
    summary="Resolve a signed artwork manifest into a print-file download",
    status_code=status.HTTP_200_OK,
)
async def create_artwork_download_link(
    request: Request,
    artwork_asset_service: artwork_asset_service_dependency,
    download_data: ArtworkDownloadRequest,
) -> ArtworkDownloadResponse:
    """Give an internal caller a short-lived way to fetch one print file.

    order_service calls this on behalf of the operator working the in-house
    production queue. It is deliberately not exposed through the API gateway:
    the artwork belongs to a paying customer and is not a public asset.
    """
    if not internal_access_helper.is_internal_client(request):
        raise ArtworkAccessForbiddenError()

    download = await artwork_asset_service.build_download(download_data.asset)
    return ArtworkDownloadResponse(
        download_url=download.download_url,
        filename=download.filename,
        sha256=download.sha256,
        content_type=download.content_type,
        expires_in_seconds=download.expires_in_seconds,
    )
