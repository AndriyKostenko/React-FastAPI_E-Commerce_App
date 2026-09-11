"""Translation of a confirmed local order into a CJ createOrderV2 body.

Everything here runs *before* the non-transactional CJ boundary is crossed, so
every failure raised from this module is definitive and safe to compensate.
"""

from logging import Logger
from typing import Any

from exceptions.cj_order_exceptions import (
    CJOrderConfigurationError,
    CJOrderCreationError,
    CJProductMappingError,
)
from service_layer.cj_address_validator import (
    CJShippingAddressValidator,
    ValidatedShippingAddress,
)
from service_layer.cj_api_client import CJDropshippingAPIError
from service_layer.cj_inventory_verifier import CJDropshippingInventoryVerifier
from service_layer.product_service_client import (
    ProductNotFoundError,
    ProductServiceClient,
    ProductServiceError,
)
from shared.contracts.events import OrderConfirmedEvent
from shared.settings import Settings


class CJOrderPayloadBuilder:
    """Builds and pre-validates the createOrderV2 request for one order.

    Responsibilities, in the order they run:
      1. validate the shipping address (`CJShippingAddressValidator`),
      2. map local product/variant ids to CJ pid/vid,
      3. re-check live CJ stock so a stock-out fails before submission.
    """

    def __init__(
        self,
        settings: Settings,
        product_service_client: ProductServiceClient,
        inventory_verifier: CJDropshippingInventoryVerifier,
        address_validator: CJShippingAddressValidator,
        logger: Logger | None = None,
    ) -> None:
        self.settings: Settings = settings
        self.product_service_client: ProductServiceClient = product_service_client
        self.inventory_verifier: CJDropshippingInventoryVerifier = inventory_verifier
        self.address_validator: CJShippingAddressValidator = address_validator
        self.logger: Logger | None = logger

    async def build(self, event: OrderConfirmedEvent) -> dict[str, Any]:
        """Return a submission-ready createOrderV2 body for ``event``.

        Raises:
            CJAddressValidationError: The shipping address cannot be shipped.
            CJOrderConfigurationError: A required CJ setting is missing.
            CJProductMappingError: A line item has no CJ pid/vid.
            CJOrderCreationError: Live CJ stock is insufficient or unverifiable.
        """
        address = self.address_validator.validate(event.address)
        # Ship with the option the customer chose and paid for at checkout.
        logistic_name = event.shipping_logistic_name or self._require_setting(
            self.settings.CJ_DROPSHIPPING_DEFAULT_LOGISTIC_NAME,
            "CJ_DROPSHIPPING_DEFAULT_LOGISTIC_NAME",
        )
        from_country_code = self._require_setting(
            self.settings.CJ_DROPSHIPPING_DEFAULT_FROM_COUNTRY_CODE,
            "CJ_DROPSHIPPING_DEFAULT_FROM_COUNTRY_CODE",
        )

        products, requested_by_vid = await self.resolve_products(event)
        if self.settings.CJ_DROPSHIPPING_VERIFY_INVENTORY:
            await self.verify_stock(requested_by_vid)

        return {
            "orderNumber": str(event.order_id),
            **address.as_cj_fields(),
            "email": event.user_email,
            "payType": self.settings.CJ_DROPSHIPPING_PAY_TYPE,
            "platform": self.settings.CJ_DROPSHIPPING_PLATFORM,
            "logisticName": logistic_name,
            "fromCountryCode": from_country_code,
            "products": products,
        }

    async def resolve_products(
        self, event: OrderConfirmedEvent
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        """Map every order line to a CJ vid, collapsing duplicate variants."""
        products: list[dict[str, Any]] = []
        requested_by_vid: dict[str, int] = {}
        for item in event.items:
            _, vid = await self.resolve_variant(item.product_id, item.variant_id)
            products.append({"vid": vid, "quantity": item.quantity})
            requested_by_vid[vid] = requested_by_vid.get(vid, 0) + item.quantity

        if not products:
            raise CJProductMappingError(f"Order {event.order_id} has no mappable products")
        return products, requested_by_vid

    async def resolve_variant(self, product_id, variant_id) -> tuple[str, str]:
        """Resolve one local product/variant pair to its CJ (pid, vid)."""
        try:
            return await self.product_service_client.resolve_cj_ids(
                product_id=product_id,
                variant_id=variant_id,
            )
        except ProductNotFoundError as exc:
            raise CJProductMappingError(
                f"Product/variant not found for item {product_id}: {exc}"
            ) from exc
        except ProductServiceError as exc:
            raise CJProductMappingError(f"Unable to map item {product_id}: {exc}") from exc

    async def verify_stock(self, requested_by_vid: dict[str, int]) -> None:
        """Fail the order when CJ's live stock cannot cover the requested units."""
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

    def _require_setting(self, value: str | None, name: str) -> str:
        if not value:
            raise CJOrderConfigurationError(f"Missing required CJ setting: {name}")
        return value
