from models.order_address_models import OrderAddress
from shared.schemas.order_schemas import OrderAddressBase, CreateOrder
from database_layer.order_address_repository import OrderAddressRepository


class OrderAddressService:
    def __init__(self, repository: OrderAddressRepository) -> None:
        self.repository: OrderAddressRepository = repository

    async def create_order_address(self, order_data: CreateOrder) -> OrderAddressBase:
        db_new_order_adress: OrderAddress = await self.repository.create(
            OrderAddress(
                user_id=order_data.user_id,
                street=order_data.address.street,
                city=order_data.address.city,
                province=order_data.address.province,
                postal_code=order_data.address.postal_code
            )
        )
        return OrderAddressBase.model_validate(db_new_order_adress)
