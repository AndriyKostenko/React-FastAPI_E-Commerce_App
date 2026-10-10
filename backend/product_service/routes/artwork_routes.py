from fastapi import APIRouter, Request, status

from dependencies.dependencies import artwork_asset_service_dependency
from schemas.artwork_schema import ArtworkDownloadRequest, ArtworkDownloadResponse
from shared.auth.service_assertion import require_service
from typing import Annotated
from fastapi import Depends

# Called by order-service directly, never through the gateway: only a request
# order-service signed with its own key is accepted (bug list 5).
OrderServiceCaller = Annotated[str, Depends(require_service("order-service"))]


artwork_routes = APIRouter(tags=["artwork"])


@artwork_routes.post(
    "/artwork/download-link",
    response_model=ArtworkDownloadResponse,
    summary="Resolve a signed artwork manifest into a print-file download",
    status_code=status.HTTP_200_OK,
)
async def create_artwork_download_link(
    caller_service: OrderServiceCaller,
    request: Request,
    artwork_asset_service: artwork_asset_service_dependency,
    download_data: ArtworkDownloadRequest,
) -> ArtworkDownloadResponse:
    """Give an internal caller a short-lived way to fetch one print file.

    order_service calls this on behalf of the operator working the in-house
    production queue. It is deliberately not exposed through the API gateway:
    the artwork belongs to a paying customer and is not a public asset.
    """
    # The signed order-service assertion (OrderServiceCaller) is the access
    # check. A client-IP test used to sit here too; it held only inside
    # Docker's private network and refused every local call from 127.0.0.1.
    download = await artwork_asset_service.build_download(download_data.asset)
    return ArtworkDownloadResponse(
        download_url=download.download_url,
        filename=download.filename,
        sha256=download.sha256,
        content_type=download.content_type,
        expires_in_seconds=download.expires_in_seconds,
    )
