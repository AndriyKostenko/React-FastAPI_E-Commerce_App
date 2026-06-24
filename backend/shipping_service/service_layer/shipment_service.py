from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from database_layer.shipping_repository import ShipmentRepository, ShippingMethodRepository
from events_publisher.shipping_event_publisher import shipping_event_publisher
from exceptions.shipping_exceptions import (
    DuplicateShipmentError,
    InvalidShipmentStatusError,
    ShipmentNotCancellableError,
    ShipmentNotFoundError,
    ShippingMethodNotFoundError,
)
from models.shipping_models import Shipment
from shared.schemas.shipping_schemas import (
    CreateShipment,
    ShipmentSchema,
    ShippingRateRequest,
    UpdateShipment,
)


VALID_STATUS_TRANSITIONS = {
    "pending": {"shipped", "cancelled"},
    "shipped": {"delivered", "cancelled"},
    "delivered": set(),
    "cancelled": set(),
}


class ShipmentService:
    """Service layer for shipment management."""

    def __init__(
        self,
        shipment_repository: ShipmentRepository,
        method_repository: ShippingMethodRepository,
    ):
        self.shipment_repository: ShipmentRepository = shipment_repository
        self.method_repository: ShippingMethodRepository = method_repository

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    async def create_shipment_from_order_event(
        self,
        order_id: UUID,
        user_id: UUID,
        user_email: str,
        method_id: UUID,
    ) -> ShipmentSchema:
        """Create a shipment after an order is confirmed."""
        method = await self.method_repository.get_by_id(method_id)
        if not method:
            raise ShippingMethodNotFoundError(method_id=method_id)

        existing = await self.shipment_repository.get_by_order_id(order_id)
        if existing:
            return ShipmentSchema.model_validate(existing)

        estimated_delivery = self._now() + timedelta(days=method.estimated_days)
        shipment = Shipment(
            order_id=order_id,
            user_id=user_id,
            method_id=method_id,
            status="pending",
            estimated_delivery=estimated_delivery,
        )

        try:
            created = await self.shipment_repository.create(shipment)
        except IntegrityError:
            raise DuplicateShipmentError(order_id=order_id)

        await shipping_event_publisher.publish_shipment_created(
            event_data={
                "shipment_id": str(created.id),
                "order_id": str(created.order_id),
                "user_id": str(created.user_id),
                "user_email": user_email,
                "method_id": str(created.method_id),
                "estimated_delivery": created.estimated_delivery.isoformat(),
            }
        )

        return ShipmentSchema.model_validate(created)

    async def create_shipment(self, shipment_data: CreateShipment) -> ShipmentSchema:
        """Create a shipment manually (admin/internal)."""
        method = await self.method_repository.get_by_id(shipment_data.method_id)
        if not method:
            raise ShippingMethodNotFoundError(method_id=shipment_data.method_id)

        existing = await self.shipment_repository.get_by_order_id(shipment_data.order_id)
        if existing:
            raise DuplicateShipmentError(order_id=shipment_data.order_id)

        estimated_delivery = self._now() + timedelta(days=method.estimated_days)
        shipment = Shipment(
            order_id=shipment_data.order_id,
            user_id=shipment_data.user_id,
            method_id=shipment_data.method_id,
            status="pending",
            estimated_delivery=estimated_delivery,
        )

        try:
            created = await self.shipment_repository.create(shipment)
        except IntegrityError:
            raise DuplicateShipmentError(order_id=shipment_data.order_id)

        return ShipmentSchema.model_validate(created)

    async def get_shipment_by_id(self, shipment_id: UUID) -> ShipmentSchema:
        """Get a shipment by ID."""
        shipment = await self.shipment_repository.get_by_id(shipment_id, load_relations=["method"])
        if not shipment:
            raise ShipmentNotFoundError(shipment_id=shipment_id)
        return ShipmentSchema.model_validate(shipment)

    async def get_shipment_by_order_id(self, order_id: UUID) -> ShipmentSchema:
        """Get a shipment by order ID."""
        shipment = await self.shipment_repository.get_by_order_id(order_id)
        if not shipment:
            raise ShipmentNotFoundError(order_id=order_id)
        return ShipmentSchema.model_validate(shipment)

    async def update_shipment(
        self,
        shipment_id: UUID,
        update_data: UpdateShipment,
        user_email: str | None = None,
    ) -> ShipmentSchema:
        """Update a shipment, validating status transitions and publishing events."""
        user_email = user_email or "shipping@example.com"
        shipment = await self.shipment_repository.get_by_id(shipment_id, load_relations=["method"])
        if not shipment:
            raise ShipmentNotFoundError(shipment_id=shipment_id)

        new_status = update_data.status
        if new_status is not None and new_status != shipment.status:
            if new_status not in VALID_STATUS_TRANSITIONS.get(shipment.status, set()):
                raise InvalidShipmentStatusError(new_status)

        update_dict = update_data.model_dump(exclude_unset=True)

        if new_status == "shipped":
            update_dict["shipped_at"] = update_data.shipped_at or self._now()
        elif new_status == "delivered":
            update_dict["delivered_at"] = update_data.delivered_at or self._now()

        updated = await self.shipment_repository.update_by_id(shipment_id, update_dict)

        if new_status == "shipped":
            await shipping_event_publisher.publish_shipment_shipped(
                event_data={
                    "shipment_id": str(updated.id),
                    "order_id": str(updated.order_id),
                    "user_id": str(updated.user_id),
                    "user_email": user_email,
                    "tracking_number": updated.tracking_number or "",
                    "shipped_at": (updated.shipped_at or self._now()).isoformat(),
                }
            )
        elif new_status == "delivered":
            await shipping_event_publisher.publish_shipment_delivered(
                event_data={
                    "shipment_id": str(updated.id),
                    "order_id": str(updated.order_id),
                    "user_id": str(updated.user_id),
                    "user_email": user_email,
                    "delivered_at": (updated.delivered_at or self._now()).isoformat(),
                }
            )

        return ShipmentSchema.model_validate(updated)

    async def cancel_shipment(
        self,
        shipment_id: UUID,
        reason: str = "Order cancelled",
        user_email: str | None = None,
    ) -> ShipmentSchema:
        """Cancel a shipment if it has not been delivered."""
        user_email = user_email or "shipping@example.com"
        shipment = await self.shipment_repository.get_by_id(shipment_id, load_relations=["method"])
        if not shipment:
            raise ShipmentNotFoundError(shipment_id=shipment_id)

        if shipment.status in {"delivered", "cancelled"}:
            raise ShipmentNotCancellableError(shipment.id, shipment.status)

        updated = await self.shipment_repository.update_by_id(
            shipment_id,
            {
                "status": "cancelled",
                "cancelled_at": self._now(),
                "cancellation_reason": reason,
            },
        )

        await shipping_event_publisher.publish_shipment_cancelled(
            event_data={
                "shipment_id": str(updated.id),
                "order_id": str(updated.order_id),
                "user_id": str(updated.user_id),
                "user_email": user_email,
                "reason": reason,
            }
        )

        return ShipmentSchema.model_validate(updated)

    async def cancel_shipment_by_order_id(
        self,
        order_id: UUID,
        reason: str = "Order cancelled",
        user_email: str | None = None,
    ) -> ShipmentSchema | None:
        """Cancel a shipment by order ID (used on order.cancelled event)."""
        user_email = user_email or "shipping@example.com"
        shipment = await self.shipment_repository.get_by_order_id(order_id)
        if not shipment:
            return None
        return await self.cancel_shipment(shipment.id, reason=reason, user_email=user_email)

    async def calculate_rate(self, request: ShippingRateRequest) -> dict:
        """Return shipping rates for active methods."""
        methods = await self.method_repository.get_active_methods()
        weight = request.weight_kg or Decimal("1.0")

        rates = []
        for method in methods:
            cost = method.base_cost + (weight * Decimal("0.5"))
            rates.append({
                "method_id": str(method.id),
                "name": method.name,
                "carrier": method.carrier,
                "estimated_days": method.estimated_days,
                "cost": str(cost.quantize(Decimal("0.01"))),
            })

        return {"destination": request.destination.model_dump(), "rates": rates}
