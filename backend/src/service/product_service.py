from sqlalchemy.ext.asyncio import AsyncSession
from src.models.models import Product
from sqlalchemy import select, asc, desc
from src.schemas.product_schemas import CreateProduct


class ProductCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_product(self, product: CreateProduct):
        new_product = Product(id=product.id,
                              name=product.name,
                              description=product.description,
                              category=product.category,
                              brand=product.brand,
                              image_url=product.image_url,
                              quantity=product.quantity,
                              price=product.price)

        # not using await coz it's an in-memory operation and doesn't interact with db
        self.session.add(new_product)

        # the commit and refresh methods are an asynchronous operations because they involve writing the
        # changes to the database, which is an I/O operation
        await self.session.commit()
        await self.session.refresh(new_product)
        return new_product

    async def get_all_products(self):
        result = await self.session.execute(select(Product).order_by(asc(Product.id)))
        products = result.scalars().all()
        return products

    async def get_product_by_id(self, product_id: int):
        db_product = await self.session.execute(select(Product).where(Product.id == product_id))
        return db_product.scalars().first()
