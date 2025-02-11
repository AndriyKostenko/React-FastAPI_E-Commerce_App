from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict

from src.errors.database_errors import DatabaseError
from src.models.product_models import Product, ProductImage
from src.models.review_models import ProductReview
from src.models.category_models import ProductCategory
from sqlalchemy import select, asc, desc
from src.schemas.product_schemas import CreateProduct
from src.schemas.product_schemas import ImageType
from src.errors.product_errors import ProductCreationError, ProductNotFoundError
from src.errors.category_errors import CategoryCreationError, CategoryNotFoundError


class ProductCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_product_item(self, product: CreateProduct):
        try:
            # Validate input data (example: ensure price and quantity are non-negative)
            if product.price <= 0 or product.quantity <= 0:
                raise ValueError("Price and quantity must be greater than 0")

            # Check if the category exists
            category = await self.get_product_category_by_id(category_id=product.category_id)

            if not category:
                raise CategoryNotFoundError(f"Category with ID {product.category_id} does not exist.")

            new_product = Product(name=product.name,
                                  description=product.description,
                                  category_id=product.category_id,
                                  brand=product.brand,
                                  quantity=product.quantity,
                                  price=product.price,
                                  in_stock=product.in_stock)
            self.session.add(new_product)
            await self.session.commit()
            await self.session.refresh(new_product)

            # creating and adding product images
            try:
                await self.create_product_image(product_id=new_product.id, image_data=product.images)
            except SQLAlchemyError as e:
                await self.session.rollback()
                raise ProductCreationError(f"Error creating product images: {str(e)}")

            return new_product

        except SQLAlchemyError as e:
            await self.session.rollback()
            raise ProductCreationError(f"Error creating the product: {str(e)}")

    async def get_all_products(self,
                               category: Optional[str] = None,
                               searchTerm: Optional[str] = None,
                               page: int = 1,
                               page_size: int = 10) -> List[Product]:

        try:
            # validating page and page_size
            page = max(1, page)
            page_size = min(max(1, page_size), 100) # limiting page size to 100

            query = select(Product).options(
                selectinload(Product.images),
                selectinload(Product.reviews).selectinload(ProductReview.user),  # product review is connected with user
                selectinload(Product.category)
            ).order_by(desc(Product.date_created))

            if category:
                query = query.filter(Product.category.has(name=category))

            if searchTerm:
                query = query.filter(Product.name.ilike(f"%{searchTerm}%"))

            # Apply pagination using offset and limit
            query = query.offset((page - 1) * page_size).limit(page_size)

            result = await self.session.execute(query)
            return result.scalars().all()

        except SQLAlchemyError as e:
            raise ProductNotFoundError(f"Error fetching products: {str(e)}")

    async def get_product_by_id(self, product_id: str) -> Optional[Product]:
        try:
            # Querying product with related images, reviews (including users), and category
            db_product = await self.session.execute(
                select(Product)
                .where(Product.id == product_id)
                .options(
                    selectinload(Product.images),
                    selectinload(Product.reviews).selectinload(ProductReview.user),
                    selectinload(Product.category)
                ))
            if db_product:
                return db_product.scalars().first()
            return None
        except SQLAlchemyError as e:
            raise DatabaseError(f"Error fetching product by id: {str(e)}")

    async def get_product_category_by_name(self, category_name: str) -> Optional[ProductCategory]:
        db_category = await self.session.execute(select(ProductCategory).where(ProductCategory.name == category_name))
        if db_category:
            return db_category.scalars().first()
        return None

    async def get_product_category_by_id(self, category_id: str):
        db_category = await self.session.execute(select(ProductCategory).where(ProductCategory.id == category_id))
        if db_category:
            return db_category.scalars().first()
        return None

    async def create_product_image(self, product_id: str, image_data: List[ImageType]):
        # Iterate over the images and save each one
        for data in image_data:
            new_product_image = ProductImage(product_id=product_id,
                                             image_url=data.image,
                                             image_color=data.color,
                                             image_color_code=data.color_code)
            self.session.add(new_product_image)

        await self.session.commit()
        # TODO: rewrite functionality to return single new_product_image
        return new_product_image

    async def update_product_availability(self, product_id: str, in_stock: bool):
        db_product = await self.session.execute(select(Product).where(Product.id == product_id))
        db_product = db_product.scalars().first()

        if db_product:
            db_product.in_stock = in_stock
            await self.session.commit()
            return db_product
        return None

    async def delete_product(self, product_id: str):
        db_product = await self.session.execute(select(Product).where(Product.id == product_id))
        db_product = db_product.scalars().first()

        if db_product:
            await self.session.delete(db_product)
            await self.session.commit()
            return True
        else:
            return False