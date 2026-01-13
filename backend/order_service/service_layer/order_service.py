from database_layer.order_repository import OrderRepository
from product_service.service_layer.product_service import ProductRepository
from shared.schemas.order_schemas import CreateOrder, OrderSchema


class OrderService:
    """Service layer for order management operations, business logic and data validation."""
    def __init__(self, order_repository: OrderRepository, product_repository: ProductRepository):
        self.order_repository = order_repository
        self.product_repository = product_repository

    async def create_order(self, order_data: CreateOrder) -> OrderSchema:
        products = self.product_repository.get_products_by_ids(order_data.products)
        print(products)
        for i in range(len(products)):
            if products[i].quantity < order_data.products[i].quantity:
                raise Exception(f"Not enough stock for product id {products[i].id}")
            products[i].quantity -= order_data.products[i].quantity
            await self.product_repository.update(products[i])
        new_order = await self.order_repository.create(order_data)
        return OrderSchema.model_validate(new_order)
