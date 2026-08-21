from datetime import datetime, timezone
from logging import Logger
from typing import Any
from uuid import UUID

from database_layer.supplier_sync_state_repository import SupplierSyncStateRepository
from database_layer.cj_order_attempt_repository import CJOrderAttemptRepository
from models.cj_order_attempt_models import CJOrderAttempt
from models.outbox_models import OutboxEvent
from shared.database_layer.outbox_repository import OutboxRepository
from event_publisher.supplier_event_publisher import SupplierEventPublisher
from exceptions.cj_order_exceptions import (
    CJOrderCreationError,
    CJOrderAmbiguousError,
    CJOrderConfigurationError,
    CJProductMappingError,
)
from service_layer.cj_api_client import CJDropshippingAPIClient, CJDropshippingAPIError
from service_layer.cj_inventory_verifier import CJDropshippingInventoryVerifier
from service_layer.outbox_event_service import OutboxEventService
from service_layer.product_service_client import (
    ProductNotFoundError,
    ProductServiceClient,
    ProductServiceError,
)
from shared.enums.event_enums import OrderEvents, SupplierEvents
from shared.contracts.events import (
    CJOrderCreatedEvent,
    CJOrderFailedEvent,
    OrderCancelledEvent,
    OrderConfirmedEvent,
    SupplierProductImportFailedEvent,
    SupplierProductImportCompletedEvent,
)
from shared.contracts.order import ConfirmedOrderAddress, ConfirmedOrderItem
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings


class SupplierEventConsumer:
    """Consumer for supplier_service events.

    Handles:
      - Import feedback events from product_service.
      - order.confirmed events that trigger CJ Dropshipping order creation.
    """

    def __init__(
        self,
        logger: Logger,
        settings: Settings,
        database: DatabaseSessionManager,
        idempotency_service: IdempotencyEventService,
        cj_api_client: CJDropshippingAPIClient,
        product_service_client: ProductServiceClient,
        publisher: SupplierEventPublisher,
    ) -> None:
        self.logger: Logger = logger
        self.settings = settings
        self.idempotency_service = idempotency_service
        self.database = database
        self.cj_api_client = cj_api_client
        self.product_service_client = product_service_client
        self.publisher = publisher
        self.inventory_verifier = CJDropshippingInventoryVerifier(
            cj_api_client, settings, logger
        )

    async def _get_sync_state_repository(self):
        async with self.database.transaction() as session:
            yield SupplierSyncStateRepository(session=session)

    async def handle_import_feedback_event(self, message: dict[str, Any]) -> None:
        event_type = message.get("event_type")
        if event_type == SupplierEvents.SUPPLIER_PRODUCT_IMPORT_COMPLETED:
            event = SupplierProductImportCompletedEvent(**message)
            if not await self.idempotency_service.try_claim_event(event.event_id, event.event_type):
                return
            try:
                self.logger.info(
                    f"Product import batch {event.batch_number}/{event.total_batches} completed "
                    f"for supplier {event.supplier_id}, fetch_id {event.fetch_id}: "
                    f"imported={event.imported}, updated={event.updated}, failed={event.failed}"
                )
                await self._update_sync_state_on_feedback(event=event)
                await self.idempotency_service.mark_event_as_processed(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    order_id=None,
                    result="recorded",
                )
            except Exception:
                await self.idempotency_service.release_claim(event.event_id, event.event_type)
                raise
        elif event_type == SupplierEvents.SUPPLIER_PRODUCT_IMPORT_FAILED:
            event = SupplierProductImportFailedEvent(**message)
            if not await self.idempotency_service.try_claim_event(event.event_id, event.event_type):
                return
            try:
                self.logger.error(
                    f"Product import failed for supplier {event.supplier_id}, "
                    f"fetch_id {event.fetch_id}, batch {event.batch_number}: {event.reason}"
                )
                await self._update_sync_state_on_failure(event)
                await self.idempotency_service.mark_event_as_processed(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    order_id=None,
                    result="recorded",
                )
            except Exception:
                await self.idempotency_service.release_claim(event.event_id, event.event_type)
                raise
        else:
            self.logger.warning(f"Unhandled supplier feedback event type: {event_type}")

    async def _update_sync_state_on_feedback(
        self,
        event: SupplierProductImportCompletedEvent,
    ) -> None:
        async with self.database.transaction() as session:
            repo = SupplierSyncStateRepository(session=session)
            sync_state = await repo.get_by_fetch_id_for_update(event.fetch_id)
            if not sync_state:
                self.logger.warning(f"No sync state found for fetch_id {event.fetch_id}")
                return

            batch_id = str(event.batch_id)
            if batch_id in (sync_state.acknowledged_batch_ids or []):
                return
            sync_state.acknowledged_batch_ids = [
                *(sync_state.acknowledged_batch_ids or []),
                batch_id,
            ]

            sync_state.processed_batches += 1
            sync_state.products_imported += event.imported
            sync_state.products_updated += event.updated
            sync_state.products_failed += event.failed
            if event.errors:
                details = "; ".join(event.errors[:10])
                sync_state.error_message = "; ".join(
                    part for part in [sync_state.error_message, details] if part
                )[:10000]

            if sync_state.processed_batches >= sync_state.total_batches:
                sync_state.status = (
                    "completed_with_errors"
                    if sync_state.products_failed or sync_state.error_message
                    else "completed"
                )
                sync_state.finished_at = datetime.now(timezone.utc)
            else:
                sync_state.status = "importing"
            await repo.update(sync_state)

    async def _update_sync_state_on_failure(
        self,
        event: SupplierProductImportFailedEvent,
    ) -> None:
        async with self.database.transaction() as session:
            repo = SupplierSyncStateRepository(session=session)
            sync_state = await repo.get_by_fetch_id_for_update(event.fetch_id)
            if not sync_state:
                return
            batch_id = str(event.batch_id)
            if batch_id in (sync_state.acknowledged_batch_ids or []):
                return
            sync_state.acknowledged_batch_ids = [
                *(sync_state.acknowledged_batch_ids or []),
                batch_id,
            ]
            sync_state.status = "import_failed"
            sync_state.finished_at = datetime.now(timezone.utc)
            sync_state.error_message = event.reason[:10000]
            await repo.update(sync_state)

    async def handle_order_event(self, message: dict[str, Any]) -> None:
        """Route order events to the appropriate handler."""
        event_type = message.get("event_type")
        match event_type:
            case OrderEvents.ORDER_CONFIRMED:
                await self.handle_order_confirmed(message)
            case OrderEvents.ORDER_CANCELLED:
                await self.handle_order_cancelled(message)
            case _:
                self.logger.warning(f"Unhandled order event type in supplier consumer: {event_type}")

    async def handle_order_cancelled(self, message: dict[str, Any]) -> None:
        """Cancel a previously created CJ order when the local Saga compensates."""
        event = OrderCancelledEvent(**message)
        if not await self.idempotency_service.try_claim_event(
            event.event_id, event.event_type
        ):
            return
        try:
            attempt = await self._get_attempt(event.order_id)
            if not attempt or not attempt.cj_order_number:
                result = "no_cj_order"
            elif attempt.status == "cancelled":
                result = "already_cancelled"
            else:
                response = await self.cj_api_client.delete_order(
                    attempt.cj_order_number
                )
                if response.get("code") != 200 or not response.get("result"):
                    reason = response.get("message") or "CJ rejected order deletion"
                    await self._mark_reconciliation(event.order_id, reason)
                    raise CJOrderAmbiguousError(reason)
                await self._set_attempt_status(event.order_id, "cancelled")
                result = "cj_order_cancelled"
            await self.idempotency_service.mark_event_as_processed(
                event.event_id, event.event_type, event.order_id, result
            )
        except Exception:
            await self.idempotency_service.release_claim(event.event_id, event.event_type)
            raise

    async def handle_order_confirmed(self, message: dict[str, Any]) -> None:
        """Create exactly the CJ portion of an order with a durable boundary."""
        event = OrderConfirmedEvent(**message)
        cj_items = [item for item in event.items if item.fulfillment_type == "cj"]
        if not cj_items:
            self.logger.info("Order %s has no CJ lines; supplier fulfillment skipped", event.order_id)
            return
        event = event.model_copy(update={"items": cj_items})
        claimed = await self.idempotency_service.try_claim_event(
            event_id=event.event_id,
            event_type=event.event_type,
        )
        if not claimed:
            self.logger.info(f"Skipping duplicate order.confirmed event for order: {event.order_id}")
            return

        try:
            existing = await self._get_attempt(event.order_id)
            if existing and existing.status == "created":
                result = "cj_order_already_created"
            else:
                if existing and existing.status in {"creating", "reconciliation_required"}:
                    cj_order_number = await self._query_existing_cj_order(event.order_id)
                    if not cj_order_number:
                        await self._mark_reconciliation(
                            event.order_id, "CJ creation outcome remains unknown"
                        )
                        raise CJOrderAmbiguousError("CJ creation outcome remains unknown")
                else:
                    payload = await self._build_cj_order_payload(event)
                    await self._record_creating(event, payload)
                    cj_order_number = await self._submit_cj_order(event, payload)
                await self._record_created(event, cj_order_number)
                result = "cj_order_created"
        except (CJOrderConfigurationError, CJProductMappingError, CJOrderCreationError) as exc:
            self.logger.error(f"CJ order creation failed for order {event.order_id}: {exc}")
            await self._record_failed(event, str(exc))
            result = f"cj_order_failed: {exc}"
        except CJOrderAmbiguousError as exc:
            self.logger.critical(
                "RECONCILIATION REQUIRED for local order %s: %s. Automatic refund is blocked.",
                event.order_id,
                exc,
            )
            await self.idempotency_service.release_claim(event.event_id, event.event_type)
            raise
        except Exception:
            await self.idempotency_service.release_claim(event.event_id, event.event_type)
            raise

        await self.idempotency_service.mark_event_as_processed(
            event_id=event.event_id,
            event_type=event.event_type,
            order_id=event.order_id,
            result=result,
        )

    async def _build_cj_order_payload(self, event: OrderConfirmedEvent) -> dict[str, Any]:
        address = event.address
        if not address:
            raise CJOrderConfigurationError(f"Order {event.order_id} has no shipping address")

        required_address_fields = [
            address.street,
            address.city,
            address.province,
            address.postal_code,
            address.country,
            address.country_code,
            address.name,
            address.phone,
        ]
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
        requested_by_vid: dict[str, int] = {}
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
            requested_by_vid[vid] = requested_by_vid.get(vid, 0) + item.quantity

        if not products:
            raise CJProductMappingError(f"Order {event.order_id} has no mappable products")

        if self.settings.CJ_DROPSHIPPING_VERIFY_INVENTORY:
            for vid, requested in requested_by_vid.items():
                try:
                    verification = await self.inventory_verifier.verify_variant_stock(
                        vid, requested
                    )
                except CJDropshippingAPIError as exc:
                    raise CJOrderCreationError(
                        f"Unable to verify live CJ stock for variant {vid}: {exc}"
                    ) from exc
                if not verification.sufficient:
                    raise CJOrderCreationError(
                        f"Insufficient live CJ stock for variant {vid}: requested "
                        f"{requested}, buffered available {verification.buffered_available}"
                    )

        return {
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

    async def _submit_cj_order(
        self, event: OrderConfirmedEvent, payload: dict[str, Any]
    ) -> str:
        try:
            response = await self.cj_api_client.create_order_v2(payload)
            return self._extract_cj_order_number(response)
        except CJOrderCreationError:
            raise
        except CJDropshippingAPIError as exc:
            # The POST may have reached CJ. Query by our stable orderNumber before
            # doing anything that could refund a real remote order.
            existing = await self._query_existing_cj_order(event.order_id)
            if existing:
                return existing
            raise CJOrderAmbiguousError(str(exc)) from exc

    async def _query_existing_cj_order(self, order_id: UUID) -> str | None:
        try:
            response = await self.cj_api_client.get_order_detail(str(order_id))
        except CJDropshippingAPIError as exc:
            raise CJOrderAmbiguousError(
                f"Unable to reconcile CJ order {order_id}: {exc}"
            ) from exc
        if response.get("code") != 200 or not response.get("result"):
            return None
        data = response.get("data") or {}
        value = data.get("cjOrderId") or data.get("orderId") or data.get("orderNum")
        return str(value) if value else None

    async def _get_attempt(self, order_id: UUID) -> CJOrderAttempt | None:
        async with self.database.transaction() as session:
            return await CJOrderAttemptRepository(session).get_by_field(
                "order_id", order_id
            )

    async def _record_creating(
        self, event: OrderConfirmedEvent, payload: dict[str, Any]
    ) -> None:
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(event.order_id)
            if attempt is None:
                await repository.create(
                    CJOrderAttempt(
                        order_id=event.order_id,
                        user_id=event.user_id,
                        status="creating",
                        request_payload=payload,
                    )
                )
            elif attempt.status != "created":
                attempt.status = "creating"
                attempt.request_payload = payload
                attempt.last_error = None
                await repository.update(attempt)

    async def _record_created(
        self, event: OrderConfirmedEvent, cj_order_number: str
    ) -> None:
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(event.order_id)
            if attempt is None:
                attempt = await repository.create(
                    CJOrderAttempt(
                        order_id=event.order_id,
                        user_id=event.user_id,
                        status="created",
                        cj_order_number=cj_order_number,
                    )
                )
            else:
                attempt.status = "created"
                attempt.cj_order_number = cj_order_number
                attempt.last_error = None
                await repository.update(attempt)
            outbox_service = OutboxEventService(
                OutboxRepository(session=session, model=OutboxEvent)
            )
            await outbox_service.add_outbox_event(
                event_type=OrderEvents.CJ_ORDER_CREATED,
                payload=CJOrderCreatedEvent(
                    service="supplier-service",
                    event_type=OrderEvents.CJ_ORDER_CREATED,
                    order_id=event.order_id,
                    user_id=event.user_id,
                    user_email=event.user_email,
                    cj_order_number=cj_order_number,
                ),
            )

    async def _record_failed(self, event: OrderConfirmedEvent, reason: str) -> None:
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(event.order_id)
            if attempt is None:
                attempt = await repository.create(
                    CJOrderAttempt(
                        order_id=event.order_id,
                        user_id=event.user_id,
                        status="failed",
                        last_error=reason[:2000],
                    )
                )
            else:
                attempt.status = "failed"
                attempt.last_error = reason[:2000]
                await repository.update(attempt)
            outbox_service = OutboxEventService(
                OutboxRepository(session=session, model=OutboxEvent)
            )
            await outbox_service.add_outbox_event(
                event_type=OrderEvents.CJ_ORDER_FAILED,
                payload=CJOrderFailedEvent(
                    service="supplier-service",
                    event_type=OrderEvents.CJ_ORDER_FAILED,
                    order_id=event.order_id,
                    user_id=event.user_id,
                    user_email=event.user_email,
                    reason=reason,
                ),
            )

    async def _mark_reconciliation(self, order_id: UUID, reason: str) -> None:
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(order_id)
            if attempt:
                attempt.status = "reconciliation_required"
                attempt.last_error = reason[:2000]
                await repository.update(attempt)

    async def _set_attempt_status(self, order_id: UUID, status: str) -> None:
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(order_id)
            if attempt:
                attempt.status = status
                attempt.last_error = None
                await repository.update(attempt)

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
