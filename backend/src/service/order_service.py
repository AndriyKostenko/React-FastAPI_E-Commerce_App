from sqlalchemy.ext.asyncio import AsyncSession
from src.models.order_models import Order, OrderItem, OrderAddress
from sqlalchemy import select, asc, desc

from src.schemas.order_schemas import CreateOrder, UpdateOrder
from src.schemas.payment import AddressToUpdate


class OrderCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_order(self, order: CreateOrder):

        # first creating an order address to get address_id as a foreign key for 'orders' table (connecting 2 tables)
        new_address = OrderAddress(user_id=order.user_id)
        self.session.add(new_address)
        await self.session.commit()

        # creating an order with the new address_id
        new_order = Order(user_id=order.user_id,
                          amount=order.amount,
                          currency=order.currency,
                          status=order.status,
                          delivery_status=order.delivery_status,
                          create_date=order.create_date,
                          payment_intent_id=order.payment_intent_id,
                          address_id=new_address.id, )
        self.session.add(new_order)
        await self.session.commit()

        # Adding the products to the order_item table according to new_order_id and product_id
        for product in order.products:
            order_item = OrderItem(order_id=new_order.id,
                                   product_id=product.id,
                                   quantity=product.quantity,
                                   price=product.price)
            self.session.add(order_item)

        await self.session.commit()
        await self.session.refresh(new_order)
        return new_order

    async def get_all_orders(self):
        result = await self.session.execute(select(Order).order_by(desc(Order.create_date)))
        orders = result.scalars().all()
        return orders

    async def get_order_by_id(self, order_id: int):
        db_order = await self.session.execute(select(Order).where(Order.id == order_id))
        return db_order.scalars().first()

    async def get_order_by_payment_intent_id(self, payment_intent_id: str):
        db_order = await self.session.execute(select(Order).where(Order.payment_intent_id == payment_intent_id))
        db_order_res = db_order.scalars().first()
        return db_order_res

    async def update_order_by_id(self, order_id: int, order_updates: UpdateOrder):
        db_order = await self.get_order_by_id(order_id)

        if not db_order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        # Dynamically update the fields that are provided
        for field, value in order_updates.dict(exclude_unset=True).items():
            print(f'fidl and value in update>>>>>> {field}, {value}')
            setattr(db_order, field, value)

        # Commit the change
        await self.session.commit()
        await self.session.refresh(db_order)

        return db_order

    async def update_status_by_payment_intent_id(self, payment_intent_id: str, status: str):
        db_order = await self.get_order_by_payment_intent_id(payment_intent_id=payment_intent_id)
        db_order.status = status
        await self.session.commit()
        await self.session.refresh(db_order)
        return db_order

    async def update_address_by_payment_intent_id(self, payment_intent_id: str, address: AddressToUpdate):
        db_order = await self.get_order_by_payment_intent_id(payment_intent_id=payment_intent_id)
        if db_order:
            db_address = await self.session.execute(select(OrderAddress).where(OrderAddress.id == db_order.address_id))
            db_address = db_address.scalars().first()
            if db_address:
                # TODO: state and country to be added to databale and street divided into 2 sections line1, line2
                db_address.street = address.line1
                db_address.city = address.city
                db_address.province = address.country
                db_address.postal_code = address.postal_code

                await self.session.commit()
                await self.session.refresh(db_address)
                return db_address
            return None
        return None

    async def update_order_by_payment_intent_id(self, payment_intent_id: str, order: UpdateOrder):

        db_order = await self.get_order_by_payment_intent_id(payment_intent_id=payment_intent_id)

        if db_order:
            db_order.amount = order.amount
            db_order.payment_intent_id = order.payment_intent_id

            # updating items
            for item_data in order.items:
                order_items = await self.session.execute(select(OrderItem).where((OrderItem.order_id == db_order.id) & (
                        item_data.id == OrderItem.product_id)))

                order_items_res = order_items.scalars().first()

                if order_items_res:
                    # updating an existing item
                    order_items_res.quantity = item_data.quantity
                    await self.session.commit()
                    await self.session.refresh(order_items_res)
                else:
                    # adding new order_item
                    new_order_item = OrderItem(order_id=db_order.id,
                                               product_id=item_data.id,
                                               quantity=item_data.quantity,
                                               price=item_data.price)
                    self.session.add(new_order_item)
                    await self.session.commit()

            await self.session.commit()
            await self.session.refresh(db_order)
            return db_order
        return None
