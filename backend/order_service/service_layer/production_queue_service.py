"""The in-house print queue: the operator's view of what to make and post."""

from datetime import UTC, datetime
from uuid import UUID

from database_layer.order_fulfillment_repository import CustomProductionJobRepository
from exceptions.production_exceptions import (
    InvalidProductionTransitionError,
    ProductionArtworkUnavailableError,
    ProductionJobNotFoundError,
)
from models.order_fulfillment_models import CustomProductionJob
from schemas.production_schemas import (
    ArtworkDownloadSchema,
    PackingSlipSchema,
    ProductionJobSchema,
    ProductionQueuePage,
)
from service_layer.artwork_asset_client import ArtworkAssetClient, ArtworkDownloadError
from service_layer.order_fulfillment_status_service import OrderFulfillmentStatusService
from service_layer.outbox_event_service import OutboxEventService
from service_layer.packing_slip_service import PackingSlipBuilder
from shared.contracts.events import (
    ProductionJobCancelledEvent,
    ProductionJobDeliveredEvent,
    ProductionJobPrintedEvent,
    ProductionJobShippedEvent,
    ProductionJobStartedEvent,
)
from shared.enums.event_enums import ProductionEvents
from shared.enums.services_enums import Services
from shared.enums.status_enums import ProductionJobStatus


class ProductionJobStateMachine:
    """The single authority on whether a queue action is legal.

    Keeping the transition table here rather than scattering ``if status ==``
    checks across the service means an illegal move — reprinting a posted
    parcel, shipping something never printed — is refused the same way from
    every entry point.
    """

    _TRANSITIONS: dict[ProductionJobStatus, frozenset[ProductionJobStatus]] = {
        ProductionJobStatus.QUEUED: frozenset(
            {
                ProductionJobStatus.IN_PRODUCTION,
                ProductionJobStatus.ON_HOLD,
                ProductionJobStatus.CANCELLED,
            }
        ),
        ProductionJobStatus.IN_PRODUCTION: frozenset(
            {
                ProductionJobStatus.PRINTED,
                ProductionJobStatus.ON_HOLD,
                ProductionJobStatus.CANCELLED,
            }
        ),
        ProductionJobStatus.PRINTED: frozenset(
            {
                ProductionJobStatus.SHIPPED,
                ProductionJobStatus.ON_HOLD,
                ProductionJobStatus.CANCELLED,
            }
        ),
        ProductionJobStatus.SHIPPED: frozenset(
            {ProductionJobStatus.DELIVERED, ProductionJobStatus.CANCELLED}
        ),
        ProductionJobStatus.ON_HOLD: frozenset(
            {
                ProductionJobStatus.QUEUED,
                ProductionJobStatus.IN_PRODUCTION,
                ProductionJobStatus.PRINTED,
                ProductionJobStatus.CANCELLED,
            }
        ),
        ProductionJobStatus.DELIVERED: frozenset(),
        ProductionJobStatus.CANCELLED: frozenset(),
    }

    def allows(
        self, current: ProductionJobStatus, target: ProductionJobStatus
    ) -> bool:
        return target in self._TRANSITIONS[current]

    def ensure(
        self,
        job_id: UUID,
        current: ProductionJobStatus,
        target: ProductionJobStatus,
    ) -> None:
        if not self.allows(current, target):
            raise InvalidProductionTransitionError(job_id, current, target)

    @staticmethod
    def resume_target(job: CustomProductionJob) -> ProductionJobStatus:
        """Where a held job returns to, read off the work already done.

        The timestamps record what physically happened, so a job resumed after
        a hold picks up exactly where it stopped rather than being sent back
        to the start of the queue.
        """
        if job.printed_at is not None:
            return ProductionJobStatus.PRINTED
        if job.started_at is not None:
            return ProductionJobStatus.IN_PRODUCTION
        return ProductionJobStatus.QUEUED


class ProductionQueueService:
    """Drives one in-house print job from queued garment to delivered parcel.

    This is the terminal path for a custom line. Nothing else writes to
    ``CustomProductionJob`` after the Saga queues it, so without an operator
    working this queue a personal order stays confirmed forever and the
    customer never hears that their T-shirt was posted.

    Every transition does three things in one transaction: move the job, move
    the order line it belongs to (which re-derives the order-level delivery
    status), and write the outbox event that notifies the customer.
    """

    def __init__(
        self,
        repository: CustomProductionJobRepository,
        fulfillment_status_service: OrderFulfillmentStatusService,
        outbox_event_service: OutboxEventService,
        packing_slip_builder: PackingSlipBuilder,
        artwork_client: ArtworkAssetClient | None = None,
        state_machine: ProductionJobStateMachine | None = None,
    ) -> None:
        self.repository = repository
        self.fulfillment_status_service = fulfillment_status_service
        self.outbox_event_service = outbox_event_service
        self.packing_slip_builder = packing_slip_builder
        self.artwork_client = artwork_client
        self.state_machine = state_machine or ProductionJobStateMachine()

    # ---------------- queue reads ----------------

    async def list_jobs(
        self,
        *,
        statuses: list[str] | None = None,
        order_id: UUID | None = None,
        reconciliation_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> ProductionQueuePage:
        jobs = await self.repository.list_queue(
            statuses=statuses,
            order_id=order_id,
            reconciliation_only=reconciliation_only,
            limit=limit,
            offset=offset,
        )
        total = await self.repository.count_queue(
            statuses=statuses,
            order_id=order_id,
            reconciliation_only=reconciliation_only,
        )
        return ProductionQueuePage(
            items=[self._to_schema(job) for job in jobs],
            total=total,
            limit=limit,
            offset=offset,
            status_counts=await self.repository.count_by_status(),
        )

    async def get_job(self, job_id: UUID) -> ProductionJobSchema:
        return self._to_schema(await self._require_job(job_id))

    async def get_packing_slip(self, job_id: UUID) -> PackingSlipSchema:
        """The slip that goes in the box, ready for the admin UI to print."""
        return self.packing_slip_builder.build(await self._require_job(job_id))

    async def get_artwork_download(self, job_id: UUID) -> ArtworkDownloadSchema:
        """Where the operator can fetch this job's print-ready PNG."""
        job = await self._require_job(job_id)
        asset = job.artwork_asset
        if asset is None:
            raise ProductionArtworkUnavailableError(
                job_id, "this job carries no generated design"
            )
        if self.artwork_client is None:
            raise ProductionArtworkUnavailableError(
                job_id, "artwork downloads are not configured on this process"
            )
        # The job is loaded; don't pin a connection while product-service answers.
        await self.repository.end_read_phase()
        try:
            download = await self.artwork_client.get_download(asset)
        except ArtworkDownloadError as exc:
            raise ProductionArtworkUnavailableError(job_id, str(exc.detail)) from exc

        return ArtworkDownloadSchema(
            download_url=download.download_url,
            filename=download.filename,
            sha256=download.sha256,
            content_type=download.content_type,
            expires_in_seconds=download.expires_in_seconds,
            width_px=asset.width_px,
            height_px=asset.height_px,
            embedded_dpi=asset.embedded_dpi,
        )

    # ---------------- queue transitions ----------------

    async def start_job(
        self, job_id: UUID, notes: str | None = None
    ) -> ProductionJobSchema:
        """The operator has taken the garment to the press."""
        job = await self._transition(
            job_id, ProductionJobStatus.IN_PRODUCTION, notes=notes
        )
        job.started_at = job.started_at or datetime.now(UTC)
        await self.repository.update(job)
        await self._publish(job, ProductionEvents.PRODUCTION_JOB_STARTED)
        return self._to_schema(job)

    async def mark_printed(
        self, job_id: UUID, notes: str | None = None
    ) -> ProductionJobSchema:
        """The garment is printed and waiting to be packed."""
        job = await self._transition(job_id, ProductionJobStatus.PRINTED, notes=notes)
        job.printed_at = datetime.now(UTC)
        await self.repository.update(job)
        await self._publish(job, ProductionEvents.PRODUCTION_JOB_PRINTED)
        return self._to_schema(job)

    async def ship_job(
        self,
        job_id: UUID,
        *,
        tracking_number: str,
        carrier: str | None = None,
        tracking_url: str | None = None,
        notes: str | None = None,
    ) -> ProductionJobSchema:
        """The parcel is in the post; this is what the customer is told."""
        job = await self._transition(job_id, ProductionJobStatus.SHIPPED, notes=notes)
        job.tracking_number = tracking_number
        job.carrier = carrier
        job.tracking_url = tracking_url
        job.shipped_at = datetime.now(UTC)
        await self.repository.update(job)
        await self._publish(job, ProductionEvents.PRODUCTION_JOB_SHIPPED)
        return self._to_schema(job)

    async def mark_delivered(self, job_id: UUID) -> ProductionJobSchema:
        """Delivery confirmed, closing out the line."""
        job = await self._transition(job_id, ProductionJobStatus.DELIVERED)
        job.delivered_at = datetime.now(UTC)
        await self.repository.update(job)
        await self._publish(job, ProductionEvents.PRODUCTION_JOB_DELIVERED)
        return self._to_schema(job)

    async def hold_job(self, job_id: UUID, reason: str) -> ProductionJobSchema:
        """Park a job that cannot be worked yet (out of blanks, bad print)."""
        job = await self._transition(
            job_id, ProductionJobStatus.ON_HOLD, notes=f"On hold: {reason}"
        )
        await self.repository.update(job)
        return self._to_schema(job)

    async def resume_job(self, job_id: UUID) -> ProductionJobSchema:
        """Return a held job to the step it had actually reached."""
        job = await self._require_locked_job(job_id)
        target = self.state_machine.resume_target(job)
        self.state_machine.ensure(job.id, job.job_status, target)
        await self._apply_status(job, target)
        await self.repository.update(job)
        return self._to_schema(job)

    async def cancel_job(self, job_id: UUID, reason: str) -> ProductionJobSchema:
        """Take a job off the queue without fulfilling it.

        A job cancelled after the garment was printed or posted is flagged for
        reconciliation rather than quietly written off: the blank and the ink
        are already spent, and any refund is a human decision.
        """
        job = await self._require_locked_job(job_id)
        previous = job.job_status
        self.state_machine.ensure(job.id, previous, ProductionJobStatus.CANCELLED)
        needs_review = previous in ProductionJobStatus.needs_reconciliation_on_cancel()

        await self._apply_status(job, ProductionJobStatus.CANCELLED)
        job.cancelled_at = datetime.now(UTC)
        job.cancellation_reason = reason[:500]
        job.reconciliation_required = job.reconciliation_required or needs_review
        await self.repository.update(job)
        await self._publish(
            job, ProductionEvents.PRODUCTION_JOB_CANCELLED, reason=reason
        )
        return self._to_schema(job)

    # ---------------- internals ----------------

    async def _require_job(self, job_id: UUID) -> CustomProductionJob:
        job = await self.repository.get_with_context(job_id)
        if job is None:
            raise ProductionJobNotFoundError(job_id)
        return job

    async def _require_locked_job(self, job_id: UUID) -> CustomProductionJob:
        """Lock the row so two operators cannot advance the same job at once."""
        job = await self.repository.get_for_update(job_id)
        if job is None:
            raise ProductionJobNotFoundError(job_id)
        return job

    async def _transition(
        self,
        job_id: UUID,
        target: ProductionJobStatus,
        *,
        notes: str | None = None,
    ) -> CustomProductionJob:
        job = await self._require_locked_job(job_id)
        self.state_machine.ensure(job.id, job.job_status, target)
        await self._apply_status(job, target)
        if notes:
            job.notes = f"{job.notes}\n{notes}" if job.notes else notes
        return job

    async def _apply_status(
        self, job: CustomProductionJob, target: ProductionJobStatus
    ) -> None:
        """Move the job and the order line it belongs to together.

        The line status is what the order-level delivery status is derived
        from, so letting the two drift is what made a mixed cart report a
        T-shirt as dispatched while it was still on the queue.
        """
        job.status = target
        await self.fulfillment_status_service.mark_lines(
            job.order,
            target.line_status,
            order_item_ids={job.order_item_id},
        )

    async def _publish(
        self,
        job: CustomProductionJob,
        event_type: ProductionEvents,
        *,
        reason: str = "",
    ) -> None:
        order = job.order
        common = {
            "service": Services.ORDER_SERVICE,
            "event_type": event_type,
            "order_id": order.id,
            "user_id": order.user_id,
            "user_email": order.user_email,
            "job_id": job.id,
            "order_item_id": job.order_item_id,
            "quantity": job.quantity,
            "product_name": self._product_name(job),
        }

        match event_type:
            case ProductionEvents.PRODUCTION_JOB_STARTED:
                payload = ProductionJobStartedEvent(**common)
            case ProductionEvents.PRODUCTION_JOB_PRINTED:
                payload = ProductionJobPrintedEvent(**common)
            case ProductionEvents.PRODUCTION_JOB_SHIPPED:
                payload = ProductionJobShippedEvent(
                    **common,
                    tracking_number=job.tracking_number or "",
                    carrier=job.carrier,
                    tracking_url=job.tracking_url,
                    shipped_at=job.shipped_at or datetime.now(UTC),
                )
            case ProductionEvents.PRODUCTION_JOB_DELIVERED:
                payload = ProductionJobDeliveredEvent(
                    **common,
                    tracking_number=job.tracking_number,
                    delivered_at=job.delivered_at or datetime.now(UTC),
                )
            case ProductionEvents.PRODUCTION_JOB_CANCELLED:
                payload = ProductionJobCancelledEvent(
                    **common,
                    reason=reason,
                    reconciliation_required=job.reconciliation_required,
                )
            case _:
                raise ValueError(f"Unsupported production event: {event_type}")

        await self.outbox_event_service.add_outbox_event(
            event_type=event_type, payload=payload
        )

    @staticmethod
    def _product_name(job: CustomProductionJob) -> str | None:
        fulfillment = job.order_item.fulfillment if job.order_item else None
        return fulfillment.product_name if fulfillment else None

    def _to_schema(self, job: CustomProductionJob) -> ProductionJobSchema:
        slip = self.packing_slip_builder
        specification = slip.parse_specification(job)
        return ProductionJobSchema(
            id=job.id,
            order_id=job.order_id,
            order_item_id=job.order_item_id,
            status=job.job_status,
            quantity=job.quantity,
            customer_email=job.order.user_email if job.order else None,
            product_name=self._product_name(job),
            tracking_number=job.tracking_number,
            carrier=job.carrier,
            tracking_url=job.tracking_url,
            notes=job.notes,
            reconciliation_required=job.reconciliation_required,
            cancellation_reason=job.cancellation_reason,
            print_specification=slip.describe_print(specification),
            date_created=job.date_created,
            started_at=job.started_at,
            printed_at=job.printed_at,
            shipped_at=job.shipped_at,
            delivered_at=job.delivered_at,
            cancelled_at=job.cancelled_at,
        )
