"""Partial refunds of an order, decided here and paid out by payment-service."""

from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from database_layer.order_refund_repository import OrderRefundRepository
from database_layer.order_repository import OrderRepository
from database_layer.order_saga_repository import OrderSagaRepository
from exceptions.order_exceptions import InvalidOrderRefundError, OrderNotFoundError, OrderRefundNotAllowedError
from models.order_models import Order
from models.order_refund_models import OrderRefund
from schemas.order_refund_schemas import OrderRefundSchema, RefundLineRequest, RefundRequest
from service_layer.outbox_event_service import OutboxEventService
from shared.contracts.events import PaymentRefundRequested
from shared.enums.event_enums import PaymentCommands
from shared.enums.services_enums import Services
from shared.enums.status_enums import OrderStatus
from shared.utils.money import to_cents


class RefundState(StrEnum):
    REQUESTED = "requested"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class OrderRefundService:
    """
    Validates and records a partial refund, then asks payment-service to make it.

    Rules, checked under the order's saga lock so two requests cannot both pass:
    - the order is confirmed (a pending one has no charge; a cancelled one was
      refunded in full by the cancellation);
    - a line is refunded at most as many times as it was bought, counting
      every refund not already failed;
    - shipping is refunded at most once;
    - the running total never exceeds what the order cost.
    """

    def __init__(
        self,
        order_repository: OrderRepository,
        saga_repository: OrderSagaRepository,
        refund_repository: OrderRefundRepository,
        outbox_event_service: OutboxEventService,
    ) -> None:
        self._orders = order_repository
        self._sagas = saga_repository
        self._refunds = refund_repository
        self._outbox = outbox_event_service

    async def request(self, order_id: UUID, request: RefundRequest, requested_by: UUID | None) -> OrderRefundSchema:
        if await self._sagas.get_for_update(order_id) is None:
            raise OrderNotFoundError(order_id)
        order = await self._orders.get_with_fulfillment(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)
        if order.status != OrderStatus.CONFIRMED:
            raise OrderRefundNotAllowedError(order_id, f"it is {order.status}")

        active = [r for r in await self._refunds.list_for_order(order_id) if r.status != RefundState.FAILED]
        lines = self._price_lines(order, request.lines, active)
        shipping = self._shipping(order, request.include_shipping, active)
        amount = sum((line["amount_value"] for line in lines), start=Decimal("0")) + shipping
        if amount <= 0:
            raise InvalidOrderRefundError("nothing to refund: the amount is zero")
        already = sum((r.amount for r in active), start=Decimal("0"))
        if already + amount > Decimal(order.amount):
            raise InvalidOrderRefundError(
                f"refunding {amount} would exceed the order total ({already} already refunded of {order.amount})"
            )

        refund = await self._refunds.create(
            OrderRefund(
                order_id=order.id,
                amount=amount,
                includes_shipping=shipping > 0,
                lines=[{k: v for k, v in line.items() if k != "amount_value"} for line in lines],
                reason=request.reason,
                status=RefundState.REQUESTED,
                requested_by=requested_by,
            )
        )
        await self._outbox.add_outbox_event(
            event_type=PaymentCommands.REFUND_REQUESTED,
            payload=PaymentRefundRequested(
                service=Services.ORDER_SERVICE,
                order_id=order.id,
                user_id=order.user_id,
                user_email=order.user_email,
                refund_id=refund.id,
                amount_cents=to_cents(amount),
                reason=request.reason,
            ),
        )
        return OrderRefundSchema.model_validate(refund)

    async def record_result(self, refund_id: UUID, *, succeeded: bool, failure_reason: str | None = None) -> None:
        """payment-service's answer. Repeats and unknown ids are ignored."""
        refund = await self._refunds.get_by_id(refund_id)
        if refund is None or refund.status != RefundState.REQUESTED:
            return
        refund.status = RefundState.SUCCEEDED if succeeded else RefundState.FAILED
        refund.failure_reason = None if succeeded else (failure_reason or "")[:500]
        refund.settled_at = datetime.now(UTC)
        await self._refunds.update(refund)

    async def list_for_order(self, order_id: UUID) -> list[OrderRefundSchema]:
        return [OrderRefundSchema.model_validate(r) for r in await self._refunds.list_for_order(order_id)]

    # ------------------------------------------------------------------ rules

    @staticmethod
    def _price_lines(
        order: Order, requested: list[RefundLineRequest], active: list[OrderRefund]
    ) -> list[dict[str, str | int | Decimal]]:
        items = {item.id: item for item in order.items}
        refunded = Counter()
        for refund in active:
            for line in refund.lines:
                refunded[UUID(str(line["order_item_id"]))] += int(line["quantity"])

        priced: list[dict[str, str | int | Decimal]] = []
        for line in requested:
            item = items.get(line.order_item_id)
            if item is None:
                raise InvalidOrderRefundError(f"line {line.order_item_id} is not part of order {order.id}")
            left = item.quantity - refunded[item.id]
            if line.quantity > left:
                raise InvalidOrderRefundError(
                    f"line {item.id}: {line.quantity} requested, only {left} of {item.quantity} still refundable"
                )
            value = (Decimal(item.price) * line.quantity).quantize(Decimal("0.01"))
            priced.append({
                "order_item_id": str(item.id), "quantity": line.quantity,
                "amount": str(value), "amount_value": value,
            })
        return priced

    @staticmethod
    def _shipping(order: Order, include: bool, active: list[OrderRefund]) -> Decimal:
        if not include:
            return Decimal("0")
        if any(r.includes_shipping for r in active):
            raise InvalidOrderRefundError("shipping has already been refunded")
        return Decimal(order.shipping_amount or 0)
