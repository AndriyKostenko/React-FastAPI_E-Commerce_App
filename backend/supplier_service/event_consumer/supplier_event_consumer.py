from datetime import datetime, timezone
from logging import Logger
from typing import Any
from uuid import UUID

from database_layer.supplier_sync_state_repository import SupplierSyncStateRepository
from database_layer.cj_order_attempt_repository import CJOrderAttemptRepository
from enums.cj_order_enums import CJOrderAttemptStatus
from models.cj_order_attempt_models import CJOrderAttempt
from models.outbox_models import OutboxEvent
from shared.database_layer.outbox_repository import OutboxRepository
from event_publisher.supplier_event_publisher import SupplierEventPublisher
from exceptions.cj_order_exceptions import (
    CJOrderCancelledError,
    CJOrderCreationError,
    CJOrderAmbiguousError,
    CJOrderConfigurationError,
    CJProductMappingError,
)
from service_layer.cj_address_validator import CJShippingAddressValidator
from service_layer.cj_api_client import (
    CJDropshippingAPIClient,
    CJDropshippingAPIError,
    CJDropshippingNetworkError,
    CJDropshippingNotFoundError,
)
from service_layer.cj_order_payment_service import CJOrderPaymentService, CJPaymentPending
from service_layer.cj_inventory_verifier import CJDropshippingInventoryVerifier
from service_layer.cj_order_payload_builder import CJOrderPayloadBuilder
from service_layer.outbox_event_service import OutboxEventService
from service_layer.product_service_client import ProductServiceClient
from shared.enums.event_enums import OrderEvents, SupplierEvents
from shared.contracts.events import (
    CJOrderCreatedEvent,
    CJOrderFailedEvent,
    OrderCancelledEvent,
    OrderConfirmedEvent,
    SupplierProductImportFailedEvent,
    SupplierProductImportCompletedEvent,
)
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings
from shared.utils.supplier_pricing import SupplierRetailPricing


class SupplierEventConsumer:
    """Consumer for supplier_service events.

    Handles:
      - Import feedback events from product_service.
      - order.confirmed events that trigger CJ Dropshipping order creation
        and payment.
      - order.cancelled events that withdraw an unpaid CJ order.
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
        self.address_validator = CJShippingAddressValidator(settings, logger)
        self.payment_service = CJOrderPaymentService(
            settings=settings,
            database=database,
            api_client=cj_api_client,
            logger=logger,
        )
        self.payload_builder = CJOrderPayloadBuilder(
            settings=settings,
            product_service_client=product_service_client,
            inventory_verifier=self.inventory_verifier,
            address_validator=self.address_validator,
            logger=logger,
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
        """Withdraw the CJ order when the local Saga compensates.

        CJ only deletes orders that are still CREATED or IN_CART. An order CJ
        has been paid for, or has shipped, cannot be undone from here: that
        needs a human (a CJ refund or a return), so it is flagged and the
        event acknowledged rather than retried into the dead-letter queue.
        """
        event = OrderCancelledEvent(**message)
        if not await self.idempotency_service.try_claim_event(
            event.event_id, event.event_type
        ):
            return
        try:
            # Recorded first, whatever happens next: order.confirmed arrives on
            # its own queue and may be handled after this, or while the CJ
            # order is being created, and must find the order gone.
            attempt = await self._record_cancellation(event)
            if not attempt.cj_order_number:
                result = await self._cancel_before_cj_order(event.order_id, attempt)
            elif attempt.status == CJOrderAttemptStatus.CANCELLED:
                result = "already_cancelled"
            elif attempt.status in {
                CJOrderAttemptStatus.PAID,
                CJOrderAttemptStatus.SHIPPED,
                CJOrderAttemptStatus.DELIVERED,
            }:
                reason = (
                    f"CJ order {attempt.cj_order_number} was already "
                    f"{attempt.status} when the local order was cancelled; "
                    "a CJ refund or a return is required"
                )
                self.logger.critical(
                    "RECONCILIATION REQUIRED for local order %s: %s",
                    event.order_id,
                    reason,
                )
                await self._mark_reconciliation(event.order_id, reason)
                result = f"cj_order_already_{attempt.status}"
            else:
                result = await self._withdraw_unpaid_cj_order(event.order_id, attempt.cj_order_number)
            await self.idempotency_service.mark_event_as_processed(
                event.event_id, event.event_type, event.order_id, result
            )
        except Exception:
            await self.idempotency_service.release_claim(event.event_id, event.event_type)
            raise

    async def _cancel_before_cj_order(self, order_id: UUID, attempt: CJOrderAttempt) -> str:
        """
        No CJ order number is recorded: make sure no CJ order is left behind.

        A ``creating`` (or unresolved) attempt means a POST may have reached CJ
        without its answer being recorded, so CJ is asked. A POST still in
        flight is caught by the confirm handler instead: it sees
        ``cancelled_at`` when it records the number, and withdraws the order.
        """
        if attempt.status in {
            CJOrderAttemptStatus.CREATING,
            CJOrderAttemptStatus.RECONCILIATION_REQUIRED,
        }:
            cj_order_number = await self._query_existing_cj_order(order_id)
            if cj_order_number:
                await self._record_cj_order_number(order_id, cj_order_number)
                return await self._withdraw_unpaid_cj_order(order_id, cj_order_number)
        await self._set_attempt_status(order_id, CJOrderAttemptStatus.CANCELLED)
        return "cancelled_before_cj_order"

    async def _withdraw_unpaid_cj_order(self, order_id: UUID, cj_order_number: str) -> str:
        """Delete an unpaid CJ order, or leave a confirmed one to lapse unpaid.

        Network errors propagate so the event is retried; a business rejection
        is final and never retried.
        """
        try:
            await self.cj_api_client.delete_order(cj_order_number)
        except CJDropshippingNetworkError:
            raise
        except CJDropshippingAPIError as exc:
            # A confirmed (UNPAID) order cannot be deleted, but it is never
            # charged or shipped either, so nothing is owed on either side.
            detail = await self.cj_api_client.get_order_detail(cj_order_number)
            status = str((detail.get("data") or {}).get("orderStatus") or "").upper()
            if status in {"UNPAID", "CANCELLED"}:
                await self._set_attempt_status(order_id, CJOrderAttemptStatus.CANCELLED)
                return f"cj_order_left_{status.lower()}"
            reason = f"CJ refused to delete order {cj_order_number} ({status or 'unknown'}): {exc}"
            self.logger.critical("RECONCILIATION REQUIRED for local order %s: %s", order_id, reason)
            await self._mark_reconciliation(order_id, reason)
            return "cj_order_delete_refused"
        await self._set_attempt_status(order_id, CJOrderAttemptStatus.CANCELLED)
        return "cj_order_cancelled"

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

        # Only an order that has, or may have, a live CJ order goes on to payment.
        pay = False
        try:
            existing = await self._get_attempt(event.order_id)
            if existing and existing.cancelled_at is not None:
                if existing.cj_order_number and existing.status == CJOrderAttemptStatus.CREATED:
                    # Created at CJ after the cancellation, and an earlier
                    # withdrawal did not finish (e.g. a network error).
                    result = await self._withdraw_unpaid_cj_order(
                        event.order_id, existing.cj_order_number
                    )
                else:
                    result = "cancelled_before_cj_order"
            elif existing and existing.status not in {
                CJOrderAttemptStatus.CREATING,
                CJOrderAttemptStatus.RECONCILIATION_REQUIRED,
                CJOrderAttemptStatus.FAILED,
            }:
                result = f"cj_order_already_{existing.status}"
                pay = True
            else:
                cj_order_number: str | None = None
                if existing and existing.status in {
                    CJOrderAttemptStatus.CREATING,
                    CJOrderAttemptStatus.RECONCILIATION_REQUIRED,
                }:
                    # An earlier try may have reached CJ: never submit twice.
                    # None means CJ says it has no such order, so submitting
                    # again is safe (an unknown answer raises instead).
                    cj_order_number = await self._query_existing_cj_order(event.order_id)
                if cj_order_number is None:
                    payload = await self._build_cj_order_payload(event)
                    if not await self._record_creating(event, payload):
                        raise CJOrderCancelledError(f"Order {event.order_id} was cancelled")
                    cj_order_number = await self._submit_cj_order(event, payload)
                if await self._record_created(event, cj_order_number):
                    result = "cj_order_created"
                    pay = True
                else:
                    # Cancelled while CJ was creating it: take it back unpaid.
                    result = await self._withdraw_unpaid_cj_order(event.order_id, cj_order_number)
        except CJOrderCancelledError:
            result = "cancelled_before_cj_order"
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
            await self._mark_reconciliation(event.order_id, str(exc))
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
        if pay:
            await self._advance_payment(event.order_id)

    async def _advance_payment(self, order_id: UUID) -> None:
        """Try to confirm and pay the CJ order straight away.

        The order already exists at CJ and is recorded locally, so a failure
        here is not the event's failure: the payment retry task picks the
        order up again.
        """
        try:
            status = await self.payment_service.advance(order_id)
            self.logger.info("CJ payment for order %s is now %s", order_id, status)
        except CJPaymentPending as exc:
            self.logger.warning("CJ payment for order %s deferred: %s", order_id, exc)
        except Exception:
            self.logger.exception("CJ payment for order %s failed; the retry task will resume it", order_id)

    async def _build_cj_order_payload(self, event: OrderConfirmedEvent) -> dict[str, Any]:
        """Validate the address, map products, and check live CJ stock.

        Every failure raised here happens before the CJ POST, so the caller can
        compensate the order without risking an orphaned remote order.
        """
        return await self.payload_builder.build(event)

    async def _submit_cj_order(
        self, event: OrderConfirmedEvent, payload: dict[str, Any]
    ) -> str:
        try:
            response = await self.cj_api_client.create_order_v2(payload)
            return self._extract_cj_order_number(response)
        except CJOrderCreationError:
            raise
        except CJDropshippingAPIError:
            # The POST may have reached CJ. Query by our stable orderNumber before
            # doing anything that could refund a real remote order.
            existing = await self._query_existing_cj_order(event.order_id)
            if existing:
                return existing
            # CJ has no such order: the POST never created one (a 429, say).
            # Raised as it was, so the message is retried and submits again.
            raise

    async def _query_existing_cj_order(self, order_id: UUID) -> str | None:
        """
        The CJ order created for ``order_id``, or None when CJ says there is none.

        Anything short of an authoritative answer raises CJOrderAmbiguousError:
        the order may exist at CJ, so nothing may be submitted or compensated.
        """
        try:
            response = await self.cj_api_client.get_order_detail(str(order_id))
        except CJDropshippingNotFoundError:
            return None
        except CJDropshippingAPIError as exc:
            raise CJOrderAmbiguousError(
                f"Unable to reconcile CJ order {order_id}: {exc}"
            ) from exc
        if response.get("code") == CJDropshippingNotFoundError.CODE:
            return None
        data = response.get("data") or {}
        value = data.get("cjOrderId") or data.get("orderId") or data.get("orderNum")
        if response.get("code") != 200 or not response.get("result") or not value:
            raise CJOrderAmbiguousError(f"CJ gave no usable answer about order {order_id}: {response}")
        return str(value)

    async def _get_attempt(self, order_id: UUID) -> CJOrderAttempt | None:
        async with self.database.transaction() as session:
            return await CJOrderAttemptRepository(session).get_by_field(
                "order_id", order_id
            )

    async def _record_creating(
        self, event: OrderConfirmedEvent, payload: dict[str, Any]
    ) -> bool:
        """Mark the attempt as being sent to CJ; False when the order was cancelled."""
        rate = (await SupplierRetailPricing.live(self.settings, self.logger)).usd_to_cad_rate
        expected_max = CJOrderPaymentService.expected_max_amount_usd(event, self.settings, rate)
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(event.order_id)
            if attempt is None:
                await repository.create(
                    CJOrderAttempt(
                        order_id=event.order_id,
                        user_id=event.user_id,
                        user_email=event.user_email,
                        status=CJOrderAttemptStatus.CREATING,
                        request_payload=payload,
                        expected_max_amount_usd=expected_max,
                        # What was actually sent decides how it is paid.
                        is_sandbox=payload.get("isSandbox") == 1,
                    )
                )
            elif attempt.cancelled_at is not None:
                # Checked under the row lock, right before the POST: a
                # cancellation recorded since the attempt was first read wins.
                return False
            elif attempt.status != CJOrderAttemptStatus.CREATED:
                attempt.status = CJOrderAttemptStatus.CREATING
                attempt.user_email = event.user_email
                attempt.request_payload = payload
                attempt.expected_max_amount_usd = expected_max
                attempt.is_sandbox = payload.get("isSandbox") == 1
                attempt.last_error = None
                await repository.update(attempt)
        return True

    async def _record_created(
        self, event: OrderConfirmedEvent, cj_order_number: str
    ) -> bool:
        """
        Record the CJ order and announce it; False when the local order was
        cancelled meanwhile, so the caller withdraws it instead.
        """
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(event.order_id)
            if attempt is not None and attempt.cancelled_at is not None:
                # Recorded as created (never paid: cancelled_at stops payment)
                # until the withdrawal succeeds and marks it cancelled.
                attempt.status = CJOrderAttemptStatus.CREATED
                attempt.cj_order_number = cj_order_number
                attempt.last_error = "Created at CJ after the local order was cancelled"
                await repository.update(attempt)
                return False
            if attempt is None:
                attempt = await repository.create(
                    CJOrderAttempt(
                        order_id=event.order_id,
                        user_id=event.user_id,
                        user_email=event.user_email,
                        status=CJOrderAttemptStatus.CREATED,
                        cj_order_number=cj_order_number,
                        # No "creating" row was recorded first, so the payload
                        # is unknown: it was built under the current setting.
                        is_sandbox=self.settings.CJ_DROPSHIPPING_SANDBOX,
                        expected_max_amount_usd=CJOrderPaymentService.expected_max_amount_usd(
                            event,
                            self.settings,
                            (await SupplierRetailPricing.live(self.settings, self.logger)).usd_to_cad_rate,
                        ),
                    )
                )
            else:
                attempt.status = CJOrderAttemptStatus.CREATED
                attempt.user_email = event.user_email
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
        return True

    async def _record_failed(self, event: OrderConfirmedEvent, reason: str) -> None:
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(event.order_id)
            if attempt is None:
                attempt = await repository.create(
                    CJOrderAttempt(
                        order_id=event.order_id,
                        user_id=event.user_id,
                        user_email=event.user_email,
                        status=CJOrderAttemptStatus.FAILED,
                        last_error=reason[:2000],
                    )
                )
            else:
                attempt.status = CJOrderAttemptStatus.FAILED
                attempt.user_email = event.user_email
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

    async def _record_cancellation(self, event: OrderCancelledEvent) -> CJOrderAttempt:
        """Stamp ``cancelled_at``; an order with no attempt yet gets a cancelled one."""
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(event.order_id)
            if attempt is None:
                return await repository.create(
                    CJOrderAttempt(
                        order_id=event.order_id,
                        user_id=event.user_id,
                        user_email=event.user_email,
                        status=CJOrderAttemptStatus.CANCELLED,
                        cancelled_at=datetime.now(timezone.utc),
                    )
                )
            if attempt.cancelled_at is None:
                attempt.cancelled_at = datetime.now(timezone.utc)
                attempt = await repository.update(attempt)
            return attempt

    async def _record_cj_order_number(self, order_id: UUID, cj_order_number: str) -> None:
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(order_id)
            if attempt:
                attempt.cj_order_number = cj_order_number
                await repository.update(attempt)

    async def _mark_reconciliation(self, order_id: UUID, reason: str) -> None:
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(order_id)
            if attempt:
                attempt.status = CJOrderAttemptStatus.RECONCILIATION_REQUIRED
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
