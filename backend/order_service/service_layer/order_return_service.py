"""Customer returns: asked for by the customer, decided by an admin, paid out as refunds."""

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from database_layer.order_refund_repository import OrderRefundRepository
from database_layer.order_repository import OrderRepository
from database_layer.order_return_repository import ReturnRequestRepository
from database_layer.order_saga_repository import OrderSagaRepository
from exceptions.order_exceptions import (
    InvalidReturnError,
    OrderNotFoundError,
    ReturnNotAllowedError,
    ReturnNotFoundError,
)
from models.order_item_models import OrderItem
from models.order_models import Order
from models.order_refund_models import OrderRefund
from models.order_return_models import ReturnLineRow, ReturnPhotoRow, ReturnRequest
from schemas.order_refund_schemas import RefundLineRequest, RefundRequest
from schemas.order_return_schemas import (
    ReturnableLine,
    ReturnEligibility,
    ReturnRequestCreate,
    ReturnRequestSchema,
)
from service_layer.order_refund_service import OrderRefundService, RefundState
from service_layer.outbox_event_service import OutboxEventService
from service_layer.return_evidence_storage import (
    EvidencePhoto,
    EvidencePhotoSniffer,
    ReturnEvidenceStorage,
)
from service_layer.return_policy import ReturnPolicies
from shared.auth.route_guards import ensure_owner_or_admin
from shared.contracts.events import OrderReturnEvent
from shared.contracts.returns import (
    ReturnFault,
    ReturnLineSummary,
    ReturnReason,
    ReturnStatus,
)
from shared.enums.event_enums import OrderEvents
from shared.enums.status_enums import LineFulfillmentStatus, OrderStatus
from shared.settings import Settings
from shared.utils.authenticated_caller import AuthenticatedCaller


class OrderReturnService:
    """
    Rules, checked under the order's saga lock (the one refunds take), so two
    requests — or a return and an admin refund — cannot both claim a unit:

    - only the order's owner (or an admin) may ask, and only on a confirmed order;
    - only delivered lines, within RETURN_WINDOW_DAYS of their delivery;
    - each unit bought is returned at most once: units already refunded, and
      units in a return still open, are no longer returnable;
    - the line's fulfilment policy decides whether the reason is accepted and
      whether the goods must come back; the seller's fault needs a photo.

    Money moves only through OrderRefundService, so its caps (never more than
    was bought or paid, shipping once) hold for returns too.
    """

    def __init__(
        self,
        order_repository: OrderRepository,
        saga_repository: OrderSagaRepository,
        return_repository: ReturnRequestRepository,
        refund_repository: OrderRefundRepository,
        refund_service: OrderRefundService,
        outbox_event_service: OutboxEventService,
        storage: ReturnEvidenceStorage,
        settings: Settings,
        policies: ReturnPolicies | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._orders = order_repository
        self._sagas = saga_repository
        self._returns = return_repository
        self._refunds = refund_repository
        self._refund_service = refund_service
        self._outbox = outbox_event_service
        self._storage = storage
        self._settings = settings
        self._policies = policies or ReturnPolicies()
        self._now = clock or (lambda: datetime.now(UTC))

    @property
    def _window(self) -> timedelta:
        return timedelta(days=self._settings.RETURN_WINDOW_DAYS)

    # ------------------------------------------------------------- customer

    async def eligibility(self, order_id: UUID, caller: AuthenticatedCaller) -> ReturnEligibility:
        """What the return form may offer, computed by the same rules a request is checked with."""
        order = await self._owned_order(order_id, caller)
        taken = await self._units_taken(order_id)
        now = self._now()
        return ReturnEligibility(
            order_id=order.id,
            window_days=self._settings.RETURN_WINDOW_DAYS,
            photo_required_for=ReturnReason.for_fault(ReturnFault.SELLER),
            lines=[self._returnable(order, item, taken, now) for item in order.items],
        )

    async def request(
        self,
        order_id: UUID,
        caller: AuthenticatedCaller,
        create: ReturnRequestCreate,
        uploads: list[bytes],
    ) -> ReturnRequestSchema:
        photos = self._check_photos(uploads)
        if await self._sagas.get_for_update(order_id) is None:
            raise OrderNotFoundError(order_id)
        order = await self._owned_order(order_id, caller)
        if order.status != OrderStatus.CONFIRMED:
            raise ReturnNotAllowedError(f"Order {order_id} cannot be returned: it is {order.status}")

        fault = create.reason.fault
        taken = await self._units_taken(order_id)
        now = self._now()
        items = {item.id: item for item in order.items}
        lines: list[ReturnLineRow] = []
        needs_photo = refund_shipping = False
        for requested in create.lines:
            item = items.get(requested.order_item_id)
            if item is None:
                raise InvalidReturnError(f"line {requested.order_item_id} is not part of order {order_id}")
            returnable = self._returnable(order, item, taken, now)
            if returnable.unavailable_reason is not None:
                raise InvalidReturnError(f"{returnable.product_name}: {returnable.unavailable_reason}")
            if requested.quantity > returnable.returnable_quantity:
                raise InvalidReturnError(
                    f"{returnable.product_name}: {requested.quantity} requested, "
                    f"only {returnable.returnable_quantity} can still be returned"
                )
            policy = self._policies.for_type(item.fulfillment.fulfillment_type)
            if not policy.allows(fault):
                raise InvalidReturnError(
                    f"{returnable.product_name} is made to order: it can only be returned when "
                    "it arrived defective, damaged, misprinted or was the wrong item"
                )
            needs_photo = needs_photo or policy.requires_photo(fault)
            refund_shipping = refund_shipping or policy.refunds_shipping(fault)
            lines.append({
                "order_item_id": str(item.id),
                "quantity": requested.quantity,
                "ships_back": policy.ships_back(fault),
                "refunded": False,
            })
        if needs_photo and not photos:
            raise InvalidReturnError("Please add at least one photo showing the problem")

        return_id = uuid4()
        # Written before the row commits: a failed commit leaves an orphan
        # file behind, never a return that points at a missing photo.
        stored = await self._store_photos(order_id, return_id, photos)
        record = await self._returns.create(
            ReturnRequest(
                id=return_id,
                order_id=order.id,
                user_id=order.user_id,
                reason=create.reason,
                fault=fault,
                description=create.description,
                lines=lines,
                photos=stored,
                refund_shipping=refund_shipping,
                status=ReturnStatus.REQUESTED,
            )
        )
        await self._publish(OrderEvents.RETURN_REQUESTED, order, record)
        return ReturnRequestSchema.model_validate(record)

    async def list_for_order(self, order_id: UUID, caller: AuthenticatedCaller) -> list[ReturnRequestSchema]:
        await self._owned_order(order_id, caller)
        return [ReturnRequestSchema.model_validate(r) for r in await self._returns.list_for_order(order_id)]

    async def cancel(self, order_id: UUID, return_id: UUID, caller: AuthenticatedCaller) -> ReturnRequestSchema:
        """The customer withdraws a return nobody has decided on yet."""
        record = await self._locked_return(return_id)
        if record.order_id != order_id:
            raise ReturnNotFoundError(return_id)
        await self._owned_order(order_id, caller)
        if record.return_status is not ReturnStatus.REQUESTED:
            raise ReturnNotAllowedError(f"Return {return_id} is {record.status}: it can no longer be withdrawn")
        record.status = ReturnStatus.CANCELLED
        await self._returns.update(record)
        return ReturnRequestSchema.model_validate(record)

    # ---------------------------------------------------------------- admin

    async def list_queue(self, status: ReturnStatus | None, *, limit: int, offset: int) -> list[ReturnRequestSchema]:
        rows = await self._returns.list_by_status(status, limit=limit, offset=offset)
        return [ReturnRequestSchema.model_validate(r) for r in rows]

    async def get(self, return_id: UUID) -> ReturnRequestSchema:
        record = await self._returns.get_by_id(return_id)
        if record is None:
            raise ReturnNotFoundError(return_id)
        return ReturnRequestSchema.model_validate(record)

    async def approve(self, return_id: UUID, admin_id: UUID, note: str | None) -> ReturnRequestSchema:
        """
        Accept the return. Lines whose goods stay with the customer are
        refunded now; the rest wait for the parcel (``receive``).
        """
        record = await self._locked_return(return_id)
        if record.return_status is not ReturnStatus.REQUESTED:
            raise ReturnNotAllowedError(f"Return {return_id} is {record.status}: only a requested return can be approved")
        record.status = ReturnStatus.APPROVED
        self._decide(record, admin_id, note)
        await self._refund(record, admin_id, ships_back=False)
        if all(line["refunded"] for line in record.lines):
            record.status = ReturnStatus.COMPLETED
        await self._returns.update(record)
        order = await self._order(record.order_id)
        await self._publish(OrderEvents.RETURN_APPROVED, order, record)
        return ReturnRequestSchema.model_validate(record)

    async def receive(self, return_id: UUID, admin_id: UUID, note: str | None) -> ReturnRequestSchema:
        """The parcel came back and passed inspection: refund what it held."""
        record = await self._locked_return(return_id)
        if record.return_status is not ReturnStatus.APPROVED:
            raise ReturnNotAllowedError(f"Return {return_id} is {record.status}: only an approved return can be received")
        record.received_at = self._now()
        if note:
            record.admin_note = self._append_note(record.admin_note, note)
        await self._refund(record, admin_id, ships_back=True)
        record.status = ReturnStatus.COMPLETED
        await self._returns.update(record)
        return ReturnRequestSchema.model_validate(record)

    async def reject(self, return_id: UUID, admin_id: UUID, note: str) -> ReturnRequestSchema:
        """
        Refuse a request, or close an approved one whose goods never came
        back or failed inspection. Lines already refunded stay refunded; the
        rest become returnable again only through a new request.
        """
        record = await self._locked_return(return_id)
        if record.return_status not in ReturnStatus.open():
            raise ReturnNotAllowedError(f"Return {return_id} is {record.status}: it cannot be rejected")
        if record.return_status is ReturnStatus.REQUESTED:
            self._decide(record, admin_id, note)
        else:
            record.admin_note = self._append_note(record.admin_note, note)
        record.status = ReturnStatus.REJECTED
        await self._returns.update(record)
        order = await self._order(record.order_id)
        await self._publish(OrderEvents.RETURN_REJECTED, order, record)
        return ReturnRequestSchema.model_validate(record)

    async def photo(self, return_id: UUID, index: int) -> tuple[bytes, str]:
        record = await self._returns.get_by_id(return_id)
        if record is None or not 0 <= index < len(record.photos):
            raise ReturnNotFoundError(return_id)
        photo = record.photos[index]
        content = await self._storage.load(str(photo["key"]))
        if content is None:
            raise ReturnNotFoundError(return_id)
        return content, str(photo["content_type"])

    # ---------------------------------------------------------------- rules

    def _returnable(self, order: Order, item: OrderItem, taken: Counter[UUID], now: datetime) -> ReturnableLine:
        """One line's eligibility; ``unavailable_reason`` says why it is not returnable."""
        fulfillment = item.fulfillment
        policy = self._policies.for_type(fulfillment.fulfillment_type)
        delivered_at = fulfillment.delivered_at or (
            fulfillment.date_updated if fulfillment.status == LineFulfillmentStatus.DELIVERED else None
        )
        return_by = delivered_at + self._window if delivered_at else None
        left = max(item.quantity - taken[item.id], 0)

        unavailable: str | None = None
        if order.status != OrderStatus.CONFIRMED:
            unavailable = f"the order is {order.status}"
        elif fulfillment.status != LineFulfillmentStatus.DELIVERED:
            unavailable = "it has not been delivered yet"
        elif return_by is not None and now > return_by:
            unavailable = f"the {self._settings.RETURN_WINDOW_DAYS}-day return window has closed"
        elif left == 0:
            unavailable = "every unit has already been returned or refunded"

        return ReturnableLine(
            order_item_id=item.id,
            product_name=fulfillment.product_name,
            fulfillment_type=fulfillment.fulfillment_type,
            quantity=item.quantity,
            returnable_quantity=0 if unavailable else left,
            return_by=return_by,
            allowed_reasons=policy.allowed_reasons(),
            unavailable_reason=unavailable,
        )

    async def _units_taken(self, order_id: UUID) -> Counter[UUID]:
        """
        Units no longer returnable, per line: every unit refunded (by a
        return or an admin), plus the not-yet-refunded units of open returns.
        A refunded return line is counted once, through its refund.
        """
        taken: Counter[UUID] = Counter()
        refunds: list[OrderRefund] = await self._refunds.list_for_order(order_id)
        for refund in refunds:
            if refund.status == RefundState.FAILED:
                continue
            for line in refund.lines:
                taken[UUID(str(line["order_item_id"]))] += int(line["quantity"])
        for record in await self._returns.list_for_order(order_id):
            if record.return_status not in ReturnStatus.open():
                continue
            for row in record.lines:
                if not row["refunded"]:
                    taken[UUID(str(row["order_item_id"]))] += int(row["quantity"])
        return taken

    def _check_photos(self, uploads: list[bytes]) -> list[EvidencePhoto]:
        if len(uploads) > self._settings.RETURN_PHOTO_MAX_COUNT:
            raise InvalidReturnError(f"At most {self._settings.RETURN_PHOTO_MAX_COUNT} photos can be attached")
        photos: list[EvidencePhoto] = []
        for number, content in enumerate(uploads, start=1):
            if len(content) > self._settings.RETURN_PHOTO_MAX_BYTES:
                limit_mb = self._settings.RETURN_PHOTO_MAX_BYTES / (1024 * 1024)
                raise InvalidReturnError(f"Photo {number} is larger than {limit_mb:g} MB")
            photo = EvidencePhotoSniffer.sniff(content)
            if photo is None:
                raise InvalidReturnError(f"Photo {number} is not a JPEG, PNG or WebP image")
            photos.append(photo)
        return photos

    # -------------------------------------------------------------- helpers

    async def _refund(self, record: ReturnRequest, admin_id: UUID, *, ships_back: bool) -> None:
        """Refund the lines of one kind (returnless / shipped back) not refunded yet."""
        due = [row for row in record.lines if bool(row["ships_back"]) is ships_back and not row["refunded"]]
        if not due:
            return
        include_shipping = record.refund_shipping and not await self._shipping_refunded(record.order_id)
        await self._refund_service.request(
            record.order_id,
            RefundRequest(
                lines=[
                    RefundLineRequest(order_item_id=UUID(str(row["order_item_id"])), quantity=int(row["quantity"]))
                    for row in due
                ],
                include_shipping=include_shipping,
                reason=f"Return {record.id}: {record.reason}",
            ),
            requested_by=admin_id,
            return_request_id=record.id,
        )
        # A new list, not an in-place edit: SQLAlchemy only sees a JSON
        # column change when the attribute is reassigned.
        record.lines = [
            {**row, "refunded": True} if row in due else row
            for row in record.lines
        ]

    async def _shipping_refunded(self, order_id: UUID) -> bool:
        return any(
            refund.includes_shipping and refund.status != RefundState.FAILED
            for refund in await self._refunds.list_for_order(order_id)
        )

    async def _store_photos(self, order_id: UUID, return_id: UUID, photos: list[EvidencePhoto]) -> list[ReturnPhotoRow]:
        stored: list[ReturnPhotoRow] = []
        for index, photo in enumerate(photos):
            key = f"{order_id}/{return_id}/{index}.{photo.extension}"
            await self._storage.save(key, photo)
            stored.append({"key": key, "content_type": photo.content_type, "size": len(photo.content)})
        return stored

    async def _locked_return(self, return_id: UUID) -> ReturnRequest:
        """The return, re-read under its order's saga lock."""
        record = await self._returns.get_by_id(return_id)
        if record is None:
            raise ReturnNotFoundError(return_id)
        await self._sagas.get_for_update(record.order_id)
        # Read again now the lock is held: the copy above may predate a
        # decision another request committed while this one waited.
        await self._returns.session.refresh(record)
        return record

    async def _order(self, order_id: UUID) -> Order:
        order = await self._orders.get_with_fulfillment(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)
        return order

    async def _owned_order(self, order_id: UUID, caller: AuthenticatedCaller) -> Order:
        order = await self._order(order_id)
        ensure_owner_or_admin(caller, order.user_id)
        return order

    def _decide(self, record: ReturnRequest, admin_id: UUID, note: str | None) -> None:
        record.decided_by = admin_id
        record.decided_at = self._now()
        if note:
            record.admin_note = self._append_note(record.admin_note, note)

    @staticmethod
    def _append_note(existing: str | None, note: str) -> str:
        return (f"{existing}\n{note}" if existing else note)[:1000]

    async def _publish(self, event_type: OrderEvents, order: Order, record: ReturnRequest) -> None:
        names = {item.id: item.fulfillment.product_name for item in order.items}
        ships_back = any(row["ships_back"] for row in record.lines)
        await self._outbox.add_outbox_event(
            event_type=event_type,
            payload=OrderReturnEvent(
                event_type=event_type,
                order_id=order.id,
                user_id=order.user_id,
                user_email=order.user_email,
                return_id=record.id,
                reason=ReturnReason(record.reason),
                fault=ReturnFault(record.fault),
                description=record.description,
                lines=[
                    ReturnLineSummary(
                        product_name=names.get(UUID(str(row["order_item_id"])), "item"),
                        quantity=int(row["quantity"]),
                        ships_back=bool(row["ships_back"]),
                    )
                    for row in record.lines
                ],
                photo_count=len(record.photos),
                admin_note=record.admin_note,
                return_address=(
                    self._settings.RETURN_ADDRESS
                    if event_type == OrderEvents.RETURN_APPROVED and ships_back
                    else None
                ),
            ),
        )
