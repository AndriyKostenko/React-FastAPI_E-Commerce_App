from datetime import datetime, timezone
import asyncio
from logging import Logger
from typing import Any
from uuid import UUID

from database_layer.supplier_sync_state_repository import SupplierSyncStateRepository
from event_publisher.supplier_event_publisher import SupplierEventPublisher
from exceptions.cj_order_exceptions import (
    CJOrderCreationError,
    CJOrderConfigurationError,
    CJProductMappingError,
)
from service_layer.cj_api_client import CJDropshippingAPIClient, CJDropshippingAPIError
from service_layer.product_service_client import (
    ProductNotFoundError,
    ProductServiceClient,
    ProductServiceError,
)
from shared.enums.event_enums import InventoryEvents, OrderEvents, SupplierEvents
from shared.schemas.event_schemas import (
    CJOrderCreatedEvent,
    InventoryReleaseRequested,
    OrderCancelledEvent,
    OrderConfirmedEvent,
    OrderItemBase,
)
from shared.schemas.order_schemas import ConfirmedOrderAddress, ConfirmedOrderItem
from shared.shared_instances import (
    logger,
    settings,
    supplier_event_idempotency_service,
    supplier_service_database_session_manager,
)


class SupplierEventConsumer:
    """Consumer for supplier_service events.

    Handles:
      - Import feedback events from product_service.
      - order.confirmed events that trigger CJ Dropshipping order creation.
    """

    def __init__(
        self,
        logger: Logger,
        idempotency_service=supplier_event_idempotency_service,
        cj_api_client: CJDropshippingAPIClient | None = None,
        product_service_client: ProductServiceClient | None = None,
        publisher: SupplierEventPublisher | None = None,
    ) -> None:
        self.logger: Logger = logger
        self.settings = settings
        self.idempotency_service = idempotency_service
        self.cj_api_client: CJDropshippingAPIClient = cj_api_client or CJDropshippingAPIClient(settings)
        self.product_service_client: ProductServiceClient = product_service_client or ProductServiceClient(settings)
        self.publisher: SupplierEventPublisher = publisher or SupplierEventPublisher(logger=logger, settings=settings)

    async def _get_sync_state_repository(self):
        async with supplier_service_database_session_manager.transaction() as session:
            yield SupplierSyncStateRepository(session=session)

    async def handle_import_feedback_event(self, message: dict[str, Any]) -> None:
        event_type = message.get("event_type")
        raw_fetch_id = message.get("fetch_id")
        fetch_id: UUID | None = None
        if raw_fetch_id:
            try:
                fetch_id = UUID(str(raw_fetch_id))
            except (ValueError, TypeError):
                fetch_id = None

        match event_type:
            case SupplierEvents.SUPPLIER_PRODUCT_IMPORT_SUCCEEDED:
                self.logger.info(
                    f"Product import succeeded for supplier {message.get('supplier_id')}, "
                    f"fetch_id {fetch_id}: "
                    f"imported={message.get('imported')}, updated={message.get('updated')}, failed={message.get('failed')}"
                )
                if fetch_id:
                    await self._update_sync_state_on_feedback(
                        fetch_id=fetch_id,
                        status="completed",
                    )
            case SupplierEvents.SUPPLIER_PRODUCT_IMPORT_FAILED:
                self.logger.error(
                    f"Product import failed for supplier {message.get('supplier_id')}, "
                    f"fetch_id {fetch_id}: {message.get('reason')}"
                )
                if fetch_id:
                    await self._update_sync_state_on_feedback(
                        fetch_id=fetch_id,
                        status="import_failed",
                        error_message=str(message.get("reason") or "Import failed"),
                    )
            case _:
                self.logger.warning(f"Unhandled supplier feedback event type: {event_type}")

    async def _update_sync_state_on_feedback(
        self,
        fetch_id: UUID,
        status: str,
        error_message: str | None = None,
    ) -> None:
        try:
            async with supplier_service_database_session_manager.transaction() as session:
                repo = SupplierSyncStateRepository(session=session)
                sync_state = await repo.get_by_fetch_id(fetch_id)
                if sync_state:
                    sync_state.status = status
                    sync_state.finished_at = datetime.now(timezone.utc)
                    if error_message:
                        sync_state.error_message = error_message
                    await repo.update(sync_state)
        except Exception as exc:
            self.logger.error(f"Failed to update sync_state for fetch_id {fetch_id}: {exc}")

    async def handle_order_event(self, message: dict[str, Any]) -> None:
        """Route order events to the appropriate handler."""
        event_type = message.get("event_type")
        match event_type:
            case OrderEvents.ORDER_CONFIRMED:
                await self.handle_order_confirmed(message)
            case _:
                self.logger.warning(f"Unhandled order event type in supplier consumer: {event_type}")

    async def handle_order_confirmed(self, message: dict[str, Any]) -> None:
        """Create a CJ Dropshipping order when an order is confirmed.

        On success publishes cj.order.created.
        On failure publishes order.cancelled + inventory.release.requested so the
        SAGA can be compensated.

        Safety properties guaranteed:
        - CJ creation failed -> compensate and mark processed.
        - CJ succeeded but cj.order.created publish failed -> release_claim so
          the message is redelivered; a CRITICAL alert is logged for manual
          reconciliation. Compensation is intentionally skipped (CJ has the order).
        - Compensation itself raises -> release_claim so the broker redelivers;
          the event is never permanently stamped processed in a broken state.
        """
        event = OrderConfirmedEvent(**message)
        claimed = await self.idempotency_service.try_claim_event(
            event_id=event.event_id,
            event_type=event.event_type,
        )
        if not claimed:
            self.logger.info(f"Skipping duplicate order.confirmed event for order: {event.order_id}")
            return

        result: str = "cj_order_created"
        # Track whether the CJ order was placed so we can distinguish between
        # "creation failed - safe to compensate" and "creation succeeded but
        # publish failed - must NOT compensate" (Bug 5 fix).
        cj_order_number: str | None = None
        # Track whether compensation completed so the finally block knows
        # whether to mark processed or release for retry (Bug 4 fix).
        compensation_succeeded: bool = False
        try:
            cj_order_number = await self._create_cj_order(event)

            # --- Bug 5 boundary ---
            # CJ accepted the order. Any exception from here on must NOT trigger
            # compensation (the order exists at CJ and may ship).
            await self.publisher.publish_cj_order_created(
                event_data={
                    "service": event.service,
                    "event_type": OrderEvents.CJ_ORDER_CREATED,
                    "order_id": str(event.order_id),
                    "user_id": str(event.user_id),
                    "user_email": event.user_email,
                    "cj_order_number": cj_order_number,
                }
            )
            self.logger.info(f"Published CJOrderCreatedEvent for order: {event.order_id}, CJ order: {cj_order_number}")

        except (CJOrderConfigurationError, CJProductMappingError, CJOrderCreationError) as exc:
            # _create_cj_order failed - CJ was never called (or all retries failed
            # before any order was placed). Safe to compensate.
            self.logger.error(f"CJ order creation failed for order {event.order_id}: {exc}")
            await self._compensate_order(event, reason=str(exc))
            compensation_succeeded = True
            result = f"compensated: {exc}"

        except Exception as exc:
            if cj_order_number is not None:
                # Bug 5: CJ accepted the order but publishing cj.order.created
                # failed. Compensating here would refund + restock an order that
                # CJ may fulfil. Instead: log for manual reconciliation, release
                # the idempotency claim, and re-raise so the broker redelivers.
                self.logger.critical(
                    f"RECONCILIATION REQUIRED: CJ order {cj_order_number!r} was "
                    f"placed for local order {event.order_id} but "
                    f"cj.order.created publish failed: {exc}. "
                    f"Do NOT compensate - verify CJ order status manually."
                )
                await self.idempotency_service.release_claim(
                    event_id=event.event_id,
                    event_type=event.event_type,
                )
                raise

            # cj_order_number is None - _create_cj_order raised an unexpected
            # error before placing anything; compensate normally.
            self.logger.error(f"Unexpected error creating CJ order for order {event.order_id}: {exc}")
            await self._compensate_order(event, reason=f"Unexpected CJ order error: {exc}")
            compensation_succeeded = True
            result = f"cj_unexpected_error: {exc}"

        finally:
            # Bug 4: only stamp "processed" when we have a definitive outcome
            # (success or a completed compensation). If compensation itself raised,
            # release the claim so the broker redelivers and retries - the event
            # must never be permanently marked processed in an unresolved state.
            if cj_order_number is not None and not compensation_succeeded:
                # We are inside the publish-failed re-raise path; release_claim
                # was already called above - nothing more to do here.
                pass
            elif compensation_succeeded or cj_order_number is not None:
                await self.idempotency_service.mark_event_as_processed(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    order_id=event.order_id,
                    result=result,
                )
            else:
                # Compensation was attempted but raised (cj_order_number is None
                # and compensation_succeeded is False) - release so retry is possible.
                try:
                    await self.idempotency_service.release_claim(
                        event_id=event.event_id,
                        event_type=event.event_type,
                    )
                except Exception:
                    pass  # never mask the original exception

    async def _create_cj_order(self, event: OrderConfirmedEvent) -> str:
        """Build and send a createOrderV2 request to CJ Dropshipping.

        Returns the CJ order id from the response.
        """
        address = event.address
        if not address:
            raise CJOrderConfigurationError(f"Order {event.order_id} has no shipping address")

        required_address_fields = [address.street, address.city, address.province, address.postal_code]
        if not all(required_address_fields):
            raise CJOrderConfigurationError(f"Order {event.order_id} has incomplete shipping address")

        logistic_name = self._require_setting(
            self.settings.CJ_DROPSHIPPING_DEFAULT_LOGISTIC_NAME,
            "CJ_DROPSHIPPING_DEFAULT_LOGISTIC_NAME",
        )
        from_country_code = self._require_setting(
            self.settings.CJ_DROPSHIPPING_DEFAULT_FROM_COUNTRY_CODE,
            "CJ_DROPSHIPPING_DEFAULT_FROM_COUNTRY_CODE",
        )

        products = []
        for item in event.items:
            try:
                pid, vid = await self.product_service_client.resolve_cj_ids(
                    product_id=item.product_id,
                    variant_id=item.variant_id,
                )
            except ProductNotFoundError as exc:
                raise CJProductMappingError(f"Product/variant not found for item {item.product_id}: {exc}") from exc
            except ProductServiceError as exc:
                raise CJProductMappingError(f"Unable to map item {item.product_id}: {exc}") from exc

            products.append({
                "vid": vid,
                "quantity": item.quantity,
            })

        if not products:
            raise CJProductMappingError(f"Order {event.order_id} has no mappable products")

        payload = {
            "orderNumber": str(event.order_id),
            "shippingZip": address.postal_code,
            "shippingCountryCode": address.country_code or "",
            "shippingCountry": address.country or "",
            "shippingProvince": address.province,
            "shippingCity": address.city,
            "shippingCustomerName": address.name or "",
            "shippingAddress": address.street,
            "shippingAddress2": "",
            "shippingPhone": address.phone or "",
            "email": event.user_email,
            "payType": self.settings.CJ_DROPSHIPPING_PAY_TYPE,
            "platform": self.settings.CJ_DROPSHIPPING_PLATFORM,
            "logisticName": logistic_name,
            "fromCountryCode": from_country_code,
            "products": products,
        }

        last_error: Exception | None = None
        max_retries = max(0, self.settings.CJ_DROPSHIPPING_ORDER_CREATE_RETRIES)
        for attempt in range(max_retries + 1):
            try:
                response = await self.cj_api_client.create_order_v2(payload)
                return self._extract_cj_order_number(response)
            except CJDropshippingAPIError as exc:
                last_error = exc
                self.logger.warning(f"CJ createOrderV2 attempt {attempt + 1} failed for order {event.order_id}: {exc}")
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (2 ** attempt))

        raise CJOrderCreationError(f"Failed after {max_retries + 1} attempts: {last_error}") from last_error

    def _extract_cj_order_number(self, response: dict[str, Any]) -> str:
        """Pull the CJ order id out of a createOrderV2 response."""
        if not response.get("result") and response.get("code") != 200:
            message = response.get("message") or "unknown CJ error"
            raise CJOrderCreationError(f"CJ API business error: {message}")

        data = response.get("data") or {}
        order_number = data.get("orderId") or data.get("orderNumber")
        if not order_number:
            raise CJOrderCreationError(f"CJ response missing order id/number: {response}")
        return str(order_number)

    def _require_setting(self, value: str | None, name: str) -> str:
        if not value:
            raise CJOrderConfigurationError(f"Missing required CJ setting: {name}")
        return value

    async def _compensate_order(self, event: OrderConfirmedEvent, reason: str) -> None:
        """Publish compensation events when CJ order creation fails."""
        await self.publisher.publish_order_cancelled(
            event_data={
                "service": event.service,
                "event_type": OrderEvents.ORDER_CANCELLED,
                "order_id": str(event.order_id),
                "user_id": str(event.user_id),
                "user_email": event.user_email,
                "reason": reason,
            }
        )
        self.logger.info(f"Published OrderCancelledEvent for order: {event.order_id}")

        release_items = [
            OrderItemBase(
                order_id=event.order_id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                quantity=item.quantity,
                price=item.price,
            )
            for item in event.items
        ]
        await self.publisher.publish_inventory_release_requested(
            event_data={
                "service": event.service,
                "event_type": InventoryEvents.INVENTORY_RELEASE_REQUESTED,
                "order_id": str(event.order_id),
                "user_id": str(event.user_id),
                "user_email": event.user_email,
                "items": [item.model_dump() for item in release_items],
                "reason": reason,
            }
        )
        self.logger.info(f"Published InventoryReleaseRequested for order: {event.order_id}")


supplier_event_consumer = SupplierEventConsumer(logger=logger)
