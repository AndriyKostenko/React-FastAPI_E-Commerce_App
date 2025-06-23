from hmac import new
from itertools import product
from typing import List, Optional
from uuid import UUID


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, asc, desc


from errors.product_errors import (ProductNotFoundError,
                                  ProductCreationError)
from models.product_models import Product, ProductImage
from models.review_models import ProductReview
from schemas.product_schemas import AllProducts, CreateProduct, ImageType, ProductSchema


class ProductCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_product_item(self, product_data: CreateProduct) -> ProductSchema:
        # 1. creating product
        product_dict = product_data.dict(exclude={"images"})
        new_product = Product(**product_dict)
        self.session.add(new_product)
        await self.session.commit()
        await self.session.refresh(new_product)
        
        # 2. creating images
        for img in product_data.images:
            new_product_image = ProductImage(
                product_id=new_product.id,
                image_url=img.image,
                image_color=img.color,
                image_color_code=img.color_code
            )
            self.session.add(new_product_image)
        await self.session.commit()
        await self.session.refresh(new_product)
        return ProductSchema.model_validate(new_product)


    async def get_all_products(self,
                               category: Optional[str] = None,
                               searchTerm: Optional[str] = None,
                               page: int = 1,
                               page_size: int = 10) -> AllProducts | None:
        # validating page and page_size
        page = max(1, page)
        page_size = min(max(1, page_size), 50) # limiting page size to 50

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
        return AllProducts(products=[ProductSchema.model_validate(product) for product in products])


    async def get_product_by_id(self, product_id: UUID) -> ProductSchema | None:
        # Querying product with related images, reviews (including users), and category
        db_product = await self.session.execute(
            select(Product)
            .where(Product.id == product_id)
            .options(
                selectinload(Product.images),
                selectinload(Product.reviews).selectinload(ProductReview.user),
                selectinload(Product.category)
            ))
        if not db_product:
            raise ProductNotFoundError(f"Product with id: {product_id} not found")
        product = db_product.scalars().first()
        return ProductSchema.model_validate(product)


    async def get_product_by_name(self, name: str) -> ProductSchema | None:
        # Querying product with related images, reviews (including users), and category
        db_product = await self.session.execute(
            select(Product)
            .where(Product.name == name)
            .options(
                selectinload(Product.images),
                selectinload(Product.reviews).selectinload(ProductReview.user),
                selectinload(Product.category)
            ))
        if not db_product:
            raise ProductNotFoundError(f"Product with name: {name} not found")
        product = db_product.scalars().first()
        return ProductSchema.model_validate(product)
            
 
    async def update_product_availability(self, product_id: UUID, in_stock: bool) -> ProductSchema:
        product = await self.get_product_by_id(product_id)
        product.in_stock = in_stock
        await self.session.commit()
        await self.session.refresh(product)
        return ProductSchema.model_validate(product)
  

    async def delete_product(self, product_id: UUID) -> None:
        product = await self.get_product_by_id(product_id)
        await self.session.delete(product)
        await self.session.commit()
   
 
