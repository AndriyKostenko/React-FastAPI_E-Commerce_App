from decimal import Decimal, ROUND_HALF_UP
from types import TracebackType
from typing import Any, Self
from uuid import UUID, uuid4

from httpx import AsyncClient, HTTPStatusError, RequestError
from pydantic import BaseModel

from schemas.order_schemas import CreateOrder
from shared.contracts.order import CustomTshirtSpecification, FulfillmentType
from shared.contracts.artwork import verify_artwork_asset
from shared.settings import Settings
from shared.exceptions.base_exceptions import BaseAPIException


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
    currency: str = "CAD"
    items: list[QuotedOrderLine]
    total_amount: Decimal


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
            self._client = AsyncClient(timeout=10.0)

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

    def __init__(self, settings: Settings, catalog_client: CatalogQuoteClient):
        self.settings = settings
        self.catalog_client = catalog_client

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
        total = sum(
            (line.unit_price * line.quantity for line in quoted_items),
            start=Decimal("0.00"),
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return CanonicalOrderQuote(currency="CAD", items=quoted_items, total_amount=total)

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
