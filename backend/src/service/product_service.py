from requests import session
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
from src.errors.product_errors import ProductCreationError, ProductNotFoundError, ProductImageCreationError
from src.errors.category_errors import CategoryCreationError, CategoryNotFoundError
from src.service.category_service import CategoryCRUDService



class ProductCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_product_item(self, product_data: CreateProduct) -> dict:
        try:
            # Validate input data (example: ensure price and quantity are non-negative)
            if product_data.price <= 0 or product_data.quantity <= 0:
                raise ProductCreationError("Price and quantity must be greater than 0")

            # Check if the category exists
            category = await CategoryCRUDService(session=self.session).get_category_by_id(category_id=product_data.category_id)
            if not category:
                raise CategoryNotFoundError(f"Category with ID: {product_data.category_id} does not exist.")

            # Extract images from product_data before creating product
            images = product_data.images
            product_dict = product_data.model_dump(exclude={'images'})
            
            new_product = Product(**product_dict)
            self.session.add(new_product)
            await self.session.commit()
            await self.session.refresh(new_product)

            # creating and adding product images
            try:
                await self.create_product_image(product_id=new_product.id, image_data=images)
            except SQLAlchemyError as e:
                await self.session.rollback()
                raise ProductCreationError(f"Error creating product images: {str(e)}")
            except DatabaseError as e:
                await self.session.rollback()
                raise ProductImageCreationError(f"Error creating product images: {str(e)}")

            # Refresh product to get the related images
            await self.session.refresh(new_product)
            
            return new_product

        except SQLAlchemyError as e:
            await self.session.rollback()
            raise DatabaseError(f"Error creating the product: {str(e)}")

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
            
            products = result.scalars().all()
            
            if not products:
                return None
            return products

        except SQLAlchemyError as e:
            raise DatabaseError(f"Error fetching products: {str(e)}")

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

    async def get_product_by_name(self, name: str) -> Optional[Product]:
        try:
            # Querying product with related images, reviews (including users), and category
            db_product = await self.session.execute(
                select(Product)
                .where(Product.name == name)
                .options(
                    selectinload(Product.images),
                    selectinload(Product.reviews).selectinload(ProductReview.user),
                    selectinload(Product.category)
                ))
            if db_product:
                return db_product.scalars().first()
            return None
        except SQLAlchemyError as e:
            raise DatabaseError(f"Error fetching product by name: {str(e)}")

    async def create_product_image(self, product_id: str, image_data: List[ImageType]):
        try:
            # Iterate over the images and save each one
            for data in image_data:
                new_product_image = ProductImage(product_id=product_id,
                                                 image_url=data.image,
                                                 image_color=data.color,
                                                 image_color_code=data.color_code)
                self.session.add(new_product_image)

            await self.session.commit()
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise DatabaseError(f"Error creating product images: {str(e)}")

    async def update_product_availability(self, product_id: str, in_stock: bool):
        try:
            product = await self.get_product_by_id(product_id)
            if product:
                product.in_stock = in_stock
                await self.session.commit()
                await self.session.refresh(product)
                return product
            return None
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise DatabaseError(f"Error updating product availability: {str(e)}")

    async def delete_product(self, product_id: str) -> Optional[Product]:
        try:
            product = await self.get_product_by_id(product_id)
            if product:
                await self.session.delete(product)
                await self.session.commit()
                return product
            return None
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise DatabaseError(f"Error deleting product: {str(e)}")