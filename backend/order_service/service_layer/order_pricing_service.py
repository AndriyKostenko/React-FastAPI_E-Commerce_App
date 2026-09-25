from logging import getLogger

from shared.auth.service_assertion import ServiceAssertionAuth
from decimal import Decimal, ROUND_HALF_UP
from types import TracebackType
from typing import Any, Self
from uuid import UUID, uuid4

from httpx import AsyncClient, HTTPStatusError, RequestError
from pydantic import BaseModel

from schemas.order_schemas import CreateOrder, ShippingOption
from shared.contracts.order import CustomTshirtSpecification, FulfillmentType
from shared.contracts.artwork import verify_artwork_asset
from shared.settings import Settings
from shared.exceptions.base_exceptions import BaseAPIException
from shared.utils.money import CENT, to_cents
from shared.utils.supplier_pricing import SupplierRetailPricing

_logger = getLogger("order-service.pricing")


class OrderQuoteError(BaseAPIException):
    def __init__(self, detail: str):
        super().__init__(status_code=422, detail=detail)


class QuotedOrderLine(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    product_name: str
    quantity: int
    unit_price: Decimal
    fulfillment_type: FulfillmentType
    supplier_id: str | None = None
    customization: CustomTshirtSpecification | None = None
    variant_snapshot: dict[str, Any] | None = None


class CanonicalOrderQuote(BaseModel):
    """The server's price for a cart delivered to one address.

    ``total_amount`` is what the customer pays: the item subtotal plus the
    selected shipping plus tax. Tax is a fixed zero until tax collection is
    enabled, but it is carried now so the total never needs a new meaning.
    """

    currency: str = "CAD"
    items: list[QuotedOrderLine]
    subtotal_amount: Decimal
    shipping_amount: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")
    total_amount: Decimal
    shipping_options: list[ShippingOption] = []
    shipping_logistic_name: str | None = None

    @property
    def amount_cents(self) -> int:
        return to_cents(self.total_amount)


class CatalogQuoteClient:
    """Internal product-service client used only for canonical order quotes."""

    def __init__(self, settings: Settings, http_client: AsyncClient | None = None):
        self.settings = settings
        self._client = http_client
        self._owns_client = http_client is None

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def start(self) -> None:
        if self._client is None:
            # Signed as order-service: product-service accepts this route from it alone.
            self._client = AsyncClient(
                timeout=10.0,
                auth=ServiceAssertionAuth.for_service(self.settings, "order-service"),
            )

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def quote(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        await self.start()
        assert self._client is not None
        try:
            response = await self._client.post(
                f"{self.settings.FULL_PRODUCT_SERVICE_URL}/products/order-quote",
                json={"items": items},
            )
            response.raise_for_status()
            return response.json()
        except (RequestError, HTTPStatusError) as exc:
            raise OrderQuoteError(f"Unable to build catalog quote: {exc}") from exc


class FreightQuoteClient:
    """Internal supplier-service client for CJ shipping options."""

    def __init__(self, settings: Settings, http_client: AsyncClient | None = None):
        self.settings = settings
        self._client = http_client
        self._owns_client = http_client is None

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def start(self) -> None:
        if self._client is None:
            # CJ itself can take up to its own freight timeout to answer.
            self._client = AsyncClient(
                timeout=self.settings.CJ_DROPSHIPPING_FREIGHT_TIMEOUT_SECONDS + 5,
                auth=ServiceAssertionAuth.for_service(self.settings, "order-service"),
            )

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def quote(
        self,
        country_code: str,
        postal_code: str | None,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return CJ's USD shipping options for ``items``, cheapest first."""
        await self.start()
        assert self._client is not None
        try:
            response = await self._client.post(
                f"{self.settings.FULL_SUPPLIER_SERVICE_URL}/cjdropshipping/freight/quote",
                json={
                    "country_code": country_code,
                    "postal_code": postal_code,
                    "items": items,
                },
            )
        except RequestError as exc:
            raise OrderQuoteError(f"Unable to quote shipping: {exc}") from exc
        if response.status_code == 422:
            detail = response.json().get("detail") or "CJ cannot ship this cart"
            raise OrderQuoteError(f"Shipping unavailable: {detail}")
        try:
            response.raise_for_status()
        except HTTPStatusError as exc:
            raise OrderQuoteError(f"Unable to quote shipping: {exc}") from exc
        return response.json().get("options") or []


class OrderPricingService:
    SIZE_MULTIPLIERS = {
        "S": Decimal("1.00"),
        "M": Decimal("1.12"),
        "L": Decimal("1.25"),
    }
    PLACEMENT_SURCHARGES = {
        "Center Chest": Decimal("0.00"),
        "Left Top Chest": Decimal("0.00"),
        "Right Top Chest": Decimal("0.00"),
        "Left Bottom": Decimal("0.00"),
        "Right Bottom": Decimal("0.00"),
        "Center Bottom": Decimal("0.00"),
        "Oversized Center": Decimal("2.00"),
        "Full Back": Decimal("3.00"),
        "Back Upper": Decimal("2.00"),
        "Back Lower": Decimal("2.00"),
    }
    # Conservative maximum physical areas for the preview placements. Exact
    # fulfillment templates can make these smaller without losing quality.
    PRINT_AREAS_INCHES = {
        "Center Chest": (12.0, 10.0),
        "Left Top Chest": (5.0, 5.0),
        "Right Top Chest": (5.0, 5.0),
        "Left Bottom": (8.0, 10.0),
        "Right Bottom": (8.0, 10.0),
        "Center Bottom": (11.0, 10.0),
        "Oversized Center": (15.0, 18.0),
        "Full Back": (15.0, 18.0),
        "Back Upper": (15.0, 8.0),
        "Back Lower": (15.0, 9.5),
    }

    def __init__(
        self,
        settings: Settings,
        catalog_client: CatalogQuoteClient,
        freight_client: FreightQuoteClient | None = None,
    ):
        self.settings = settings
        self.catalog_client = catalog_client
        self.freight_client = freight_client

    async def build_quote(self, order_data: CreateOrder) -> CanonicalOrderQuote:
        catalog_requests: list[dict[str, Any]] = []
        catalog_positions: list[int] = []
        quoted_by_position: dict[int, QuotedOrderLine] = {}

        for position, item in enumerate(order_data.products):
            if item.fulfillment_type == "custom":
                specification = item.customization
                assert specification is not None
                specification = self._validate_and_finalize_customization(
                    specification
                )
                unit_price = self._custom_unit_price(specification)
                quoted_by_position[position] = QuotedOrderLine(
                    product_id=item.id or uuid4(),
                    product_name=f"Custom T-Shirt ({specification.size})",
                    quantity=item.quantity,
                    unit_price=unit_price,
                    fulfillment_type="custom",
                    customization=specification,
                )
            else:
                if item.id is None:
                    raise OrderQuoteError("Catalog product id is required")
                catalog_positions.append(position)
                catalog_requests.append(
                    {
                        "product_id": str(item.id),
                        "variant_id": str(item.variant_id) if item.variant_id else None,
                        "quantity": item.quantity,
                    }
                )

        if catalog_requests:
            catalog_quote = await self.catalog_client.quote(catalog_requests)
            catalog_lines = catalog_quote.get("items") or []
            if len(catalog_lines) != len(catalog_positions):
                raise OrderQuoteError("Product service returned an incomplete quote")
            for position, line in zip(catalog_positions, catalog_lines, strict=True):
                quoted_by_position[position] = QuotedOrderLine(**line)

        quoted_items = [quoted_by_position[index] for index in range(len(order_data.products))]
        subtotal = sum(
            (line.unit_price * line.quantity for line in quoted_items),
            start=Decimal("0.00"),
        ).quantize(CENT, rounding=ROUND_HALF_UP)
        shipping_options, selected = await self._quote_cj_shipping(order_data, quoted_items)
        shipping = self._domestic_shipping(quoted_items)
        if selected is not None:
            shipping += selected.amount
        tax = Decimal("0.00")
        return CanonicalOrderQuote(
            currency="CAD",
            items=quoted_items,
            subtotal_amount=subtotal,
            shipping_amount=shipping,
            tax_amount=tax,
            total_amount=subtotal + shipping + tax,
            shipping_options=shipping_options,
            shipping_logistic_name=selected.logistic_name if selected else None,
        )

    def _domestic_shipping(self, lines: list[QuotedOrderLine]) -> Decimal:
        """One flat charge covers every line that ships from here rather than CJ."""
        if any(line.fulfillment_type != "cj" for line in lines):
            return Decimal(str(self.settings.DOMESTIC_FLAT_SHIPPING_CAD)).quantize(CENT)
        return Decimal("0.00")

    async def _quote_cj_shipping(
        self,
        order_data: CreateOrder,
        lines: list[QuotedOrderLine],
    ) -> tuple[list[ShippingOption], ShippingOption | None]:
        """Price CJ shipping to the order address and pick the requested option.

        With no option requested the cheapest one is selected, so a quote can
        be shown before the customer chooses. A requested option that CJ no
        longer offers is refused rather than silently swapped for another.
        """
        cj_lines = [line for line in lines if line.fulfillment_type == "cj"]
        if not cj_lines:
            return [], None
        if self.freight_client is None:
            raise RuntimeError("FreightQuoteClient is required to price CJ orders")

        address = order_data.address
        # CJ refuses an order without these, so refuse before pricing it.
        required = {
            "country": address.country,
            "country_code": address.country_code,
            "name": address.name,
            "phone": address.phone,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise OrderQuoteError(
                f"CJ fulfillment requires address fields: {', '.join(missing)}"
            )
        country_code = (address.country_code or "").strip().upper()
        if len(country_code) != 2 or not country_code.isalpha():
            raise OrderQuoteError("country_code must be a 2-letter ISO code")
        missing_variant = [line.product_id for line in cj_lines if line.variant_id is None]
        if missing_variant:
            raise OrderQuoteError(f"CJ products require a variant: {missing_variant}")

        raw_options = await self.freight_client.quote(
            country_code=country_code,
            postal_code=address.postal_code or None,
            items=[
                {
                    "product_id": str(line.product_id),
                    "variant_id": str(line.variant_id),
                    "quantity": line.quantity,
                }
                for line in cj_lines
            ],
        )
        pricing = await SupplierRetailPricing.live(self.settings, _logger)
        options = [self._to_shipping_option(option, pricing) for option in raw_options]
        if not options:
            raise OrderQuoteError(f"No shipping option to {country_code} for this cart")

        requested = order_data.shipping_logistic_name
        if requested is None:
            return options, options[0]
        selected = next((o for o in options if o.logistic_name == requested), None)
        if selected is None:
            raise OrderQuoteError(
                f"Shipping option '{requested}' is no longer available; please choose again"
            )
        return options, selected

    def _to_shipping_option(
        self, option: dict[str, Any], pricing: SupplierRetailPricing
    ) -> ShippingOption:
        """Convert one CJ USD option to the padded CAD price the customer pays."""
        padded_usd = Decimal(str(option["price"])) * (
            1 + Decimal(str(self.settings.CJ_FREIGHT_PRICE_BUFFER))
        )
        return ShippingOption(
            logistic_name=option["logistic_name"],
            amount=pricing.usd_to_cad(padded_usd),
            cost_usd=Decimal(str(option["price"])),
            delivery_time=option.get("delivery_time"),
        )

    def _custom_unit_price(self, specification: CustomTshirtSpecification) -> Decimal:
        base = Decimal(str(self.settings.CUSTOM_TSHIRT_BASE_PRICE))
        return (
            base * self.SIZE_MULTIPLIERS[specification.size]
            + self.PLACEMENT_SURCHARGES[specification.placement]
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _validate_and_finalize_customization(
        self, specification: CustomTshirtSpecification
    ) -> CustomTshirtSpecification:
        asset = specification.design_asset
        if not verify_artwork_asset(asset, self.settings.ARTWORK_SIGNING_KEY):
            raise OrderQuoteError(
                "Custom design metadata is invalid or was not issued by the image service"
            )

        print_width, print_height = self.PRINT_AREAS_INCHES[
            specification.placement
        ]
        effective_dpi = min(
            asset.width_px / print_width,
            asset.height_px / print_height,
        )
        minimum_dpi = self.settings.PRINT_IMAGE_MIN_EFFECTIVE_DPI
        if effective_dpi < minimum_dpi:
            raise OrderQuoteError(
                "Custom design resolution is too low for the selected print area "
                f"({effective_dpi:.0f} DPI; minimum {minimum_dpi} DPI)"
            )

        # Client-supplied calculated fields are never trusted. Persist the
        # server's canonical production measurements with the order snapshot.
        return specification.model_copy(
            update={
                "print_width_in": print_width,
                "print_height_in": print_height,
                "effective_dpi": round(effective_dpi, 2),
            }
        )
