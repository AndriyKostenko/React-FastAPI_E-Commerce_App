from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from dependencies.dependencies import production_queue_service_dependency
from schemas.production_schemas import (
    ArtworkDownloadSchema,
    CancelProductionJobRequest,
    HoldProductionJobRequest,
    MarkPrintedRequest,
    PackingSlipSchema,
    ProductionJobSchema,
    ProductionQueuePage,
    ShipProductionJobRequest,
    StartProductionJobRequest,
)
from shared.enums.status_enums import ProductionJobStatus


production_routes = APIRouter(tags=["production"], prefix="/admin/production")

"""
Admin API for the in-house print queue.

This is the terminal path for a custom T-shirt line: nothing else writes to a
``CustomProductionJob`` once the Saga queues it, so without these endpoints an
order that is printed at home stays confirmed forever and the customer never
learns their parcel was posted. Access is restricted at the API gateway, which
is the only route into these paths from outside the mesh.
"""


@production_routes.get(
    "/jobs",
    response_model=ProductionQueuePage,
    summary="List the in-house production queue",
    status_code=status.HTTP_200_OK,
)
async def list_production_jobs(
    request: Request,
    production_queue_service: production_queue_service_dependency,
    job_status: list[ProductionJobStatus] | None = Query(default=None, alias="status"),
    order_id: UUID | None = Query(default=None),
    reconciliation_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ProductionQueuePage:
    return await production_queue_service.list_jobs(
        statuses=[value.value for value in job_status] if job_status else None,
        order_id=order_id,
        reconciliation_only=reconciliation_only,
        limit=limit,
        offset=offset,
    )


@production_routes.get(
    "/jobs/{job_id}",
    response_model=ProductionJobSchema,
    summary="Get one production job",
    status_code=status.HTTP_200_OK,
)
async def get_production_job(
    request: Request,
    job_id: UUID,
    production_queue_service: production_queue_service_dependency,
) -> ProductionJobSchema:
    return await production_queue_service.get_job(job_id)


@production_routes.get(
    "/jobs/{job_id}/artwork",
    response_model=ArtworkDownloadSchema,
    summary="Resolve the print-ready artwork download for a job",
    status_code=status.HTTP_200_OK,
)
async def get_production_job_artwork(
    request: Request,
    job_id: UUID,
    production_queue_service: production_queue_service_dependency,
) -> ArtworkDownloadSchema:
    return await production_queue_service.get_artwork_download(job_id)


@production_routes.get(
    "/jobs/{job_id}/packing-slip",
    response_model=PackingSlipSchema,
    summary="Build the packing slip that ships with the garment",
    status_code=status.HTTP_200_OK,
)
async def get_production_job_packing_slip(
    request: Request,
    job_id: UUID,
    production_queue_service: production_queue_service_dependency,
) -> PackingSlipSchema:
    return await production_queue_service.get_packing_slip(job_id)


@production_routes.post(
    "/jobs/{job_id}/start",
    response_model=ProductionJobSchema,
    summary="Take a queued job to the press",
    status_code=status.HTTP_200_OK,
)
async def start_production_job(
    request: Request,
    job_id: UUID,
    production_queue_service: production_queue_service_dependency,
    job_data: StartProductionJobRequest,
) -> ProductionJobSchema:
    return await production_queue_service.start_job(job_id, notes=job_data.notes)


@production_routes.post(
    "/jobs/{job_id}/printed",
    response_model=ProductionJobSchema,
    summary="Mark a job as printed and awaiting post",
    status_code=status.HTTP_200_OK,
)
async def mark_production_job_printed(
    request: Request,
    job_id: UUID,
    production_queue_service: production_queue_service_dependency,
    job_data: MarkPrintedRequest,
) -> ProductionJobSchema:
    return await production_queue_service.mark_printed(job_id, notes=job_data.notes)


@production_routes.post(
    "/jobs/{job_id}/ship",
    response_model=ProductionJobSchema,
    summary="Record the tracking number and notify the customer",
    status_code=status.HTTP_200_OK,
)
async def ship_production_job(
    request: Request,
    job_id: UUID,
    production_queue_service: production_queue_service_dependency,
    job_data: ShipProductionJobRequest,
) -> ProductionJobSchema:
    return await production_queue_service.ship_job(
        job_id,
        tracking_number=job_data.tracking_number,
        carrier=job_data.carrier,
        tracking_url=job_data.tracking_url,
        notes=job_data.notes,
    )


@production_routes.post(
    "/jobs/{job_id}/delivered",
    response_model=ProductionJobSchema,
    summary="Close a job out as delivered",
    status_code=status.HTTP_200_OK,
)
async def mark_production_job_delivered(
    request: Request,
    job_id: UUID,
    production_queue_service: production_queue_service_dependency,
) -> ProductionJobSchema:
    return await production_queue_service.mark_delivered(job_id)


@production_routes.post(
    "/jobs/{job_id}/hold",
    response_model=ProductionJobSchema,
    summary="Park a job that cannot be worked yet",
    status_code=status.HTTP_200_OK,
)
async def hold_production_job(
    request: Request,
    job_id: UUID,
    production_queue_service: production_queue_service_dependency,
    job_data: HoldProductionJobRequest,
) -> ProductionJobSchema:
    return await production_queue_service.hold_job(job_id, reason=job_data.reason)


@production_routes.post(
    "/jobs/{job_id}/resume",
    response_model=ProductionJobSchema,
    summary="Return a held job to the step it had reached",
    status_code=status.HTTP_200_OK,
)
async def resume_production_job(
    request: Request,
    job_id: UUID,
    production_queue_service: production_queue_service_dependency,
) -> ProductionJobSchema:
    return await production_queue_service.resume_job(job_id)


@production_routes.post(
    "/jobs/{job_id}/cancel",
    response_model=ProductionJobSchema,
    summary="Take a job off the queue without fulfilling it",
    status_code=status.HTTP_200_OK,
)
async def cancel_production_job(
    request: Request,
    job_id: UUID,
    production_queue_service: production_queue_service_dependency,
    job_data: CancelProductionJobRequest,
) -> ProductionJobSchema:
    return await production_queue_service.cancel_job(job_id, reason=job_data.reason)
