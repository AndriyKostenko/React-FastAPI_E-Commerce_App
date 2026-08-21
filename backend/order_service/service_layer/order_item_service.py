from uuid import UUID

from database_layer.order_item_repository import OrderItemRepository
from database_layer.order_fulfillment_repository import OrderLineFulfillmentRepository
from models.order_item_models import OrderItem
from models.order_fulfillment_models import OrderLineFulfillment
from schemas.order_schemas import OrderItemBase
from service_layer.order_pricing_service import CanonicalOrderQuote


class OrderItemService:
    def __init__(
        self,
        repository: OrderItemRepository,
        fulfillment_repository: OrderLineFulfillmentRepository | None = None,
    ) -> None:
        self.repository: OrderItemRepository = repository
        self.fulfillment_repository = fulfillment_repository or OrderLineFulfillmentRepository(
            repository.session
        )

    async def create_order_items(
        self,
        db_order_id: UUID,
        quote: CanonicalOrderQuote,
    ) -> list[OrderItemBase]:
        new_order_items = [
            OrderItem(
                order_id=db_order_id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                quantity=item.quantity,
                price=float(item.unit_price),
            )
            for item in quote.items
        ]
        new_db_order_items = await self.repository.create_many(new_order_items)
        fulfillments = [
            OrderLineFulfillment(
                order_item_id=order_item.id,
                fulfillment_type=line.fulfillment_type,
                product_name=line.product_name,
                supplier_id=line.supplier_id,
                customization=(
                    line.customization.model_dump(mode="json")
                    if line.customization
                    else None
                ),
                variant_snapshot=line.variant_snapshot,
                status="pending",
            )
            for order_item, line in zip(new_db_order_items, quote.items, strict=True)
        ]
        await self.fulfillment_repository.create_many(fulfillments)
        return [
            self._to_schema(order_item, fulfillment)
            for order_item, fulfillment in zip(
                new_db_order_items, fulfillments, strict=True
            )
        ]

    async def get_items_by_order_id(self, order_id: UUID) -> list[OrderItemBase]:
        items = await self.repository.get_by_order_id_with_fulfillment(order_id)
        return [self._to_schema(item, item.fulfillment) for item in items]

    @staticmethod
    def _to_schema(order_item: OrderItem, fulfillment: OrderLineFulfillment) -> OrderItemBase:
        return OrderItemBase(
            order_id=order_item.order_id,
            product_id=order_item.product_id,
            variant_id=order_item.variant_id,
            quantity=order_item.quantity,
            price=order_item.price,
            fulfillment_type=fulfillment.fulfillment_type,
            product_name=fulfillment.product_name,
            customization=fulfillment.customization,
            variant_snapshot=fulfillment.variant_snapshot,
        )
