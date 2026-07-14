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
        match event_type:
            case SupplierEvents.SUPPLIER_PRODUCT_IMPORT_SUCCEEDED:
                self.logger.info(
                    f"Product import succeeded for supplier {message.get('supplier_id')}, "
                    f"fetch_id {message.get('fetch_id')}: "
                    f"imported={message.get('imported')}, updated={message.get('updated')}, failed={message.get('failed')}"
                )
            case SupplierEvents.SUPPLIER_PRODUCT_IMPORT_FAILED:
                self.logger.error(
                    f"Product import failed for supplier {message.get('supplier_id')}, "
                    f"fetch_id {message.get('fetch_id')}: {message.get('reason')}"
                )
            case _:
                self.logger.warning(f"Unhandled supplier feedback event type: {event_type}")

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
        """
        event = OrderConfirmedEvent(**message)
        claimed = await self.idempotency_service.try_claim_event(
            event_id=event.event_id,
            event_type=event.event_type,
        )
        if not claimed:
            self.logger.info(f"Skipping duplicate order.confirmed event for order: {event.order_id}")
            return

        result = "cj_order_created"
        try:
            cj_order_number = await self._create_cj_order(event)
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
        except CJOrderConfigurationError as exc:
            self.logger.error(f"CJ order configuration error for order {event.order_id}: {exc}")
            await self._compensate_order(event, reason=f"CJ order configuration error: {exc}")
            result = f"cj_configuration_error: {exc}"
        except CJProductMappingError as exc:
            self.logger.error(f"CJ product mapping error for order {event.order_id}: {exc}")
            await self._compensate_order(event, reason=f"CJ product mapping error: {exc}")
            result = f"cj_mapping_error: {exc}"
        except CJOrderCreationError as exc:
            self.logger.error(f"CJ order creation failed for order {event.order_id}: {exc}")
            await self._compensate_order(event, reason=f"CJ order creation failed: {exc}")
            result = f"cj_creation_failed: {exc}"
        except Exception as exc:
            self.logger.error(f"Unexpected error creating CJ order for order {event.order_id}: {exc}")
            await self._compensate_order(event, reason=f"Unexpected CJ order error: {exc}")
            result = f"cj_unexpected_error: {exc}"
        finally:
            await self.idempotency_service.mark_event_as_processed(
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=event.order_id,
                result=result,
            )

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
