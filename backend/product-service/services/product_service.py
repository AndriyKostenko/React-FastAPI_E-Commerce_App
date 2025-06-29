from typing import List, Optional
from uuid import UUID


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, asc, desc


from errors.product_errors import (ProductNotFoundError,
                                  ProductCreationError)
from models.product_models import Product, ProductImage
from models.review_models import ProductReview
from schemas.product_schemas import CreateProduct, ProductBase, ProductSchema


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
        
        # 3. Now re-query with relationships loaded
        result = await self.session.execute(
            select(Product)
            .where(Product.id == new_product.id)
            .options(
                selectinload(Product.images),
                selectinload(Product.reviews),
                selectinload(Product.category)
            )
        )
        product = result.scalars().first()
        return ProductSchema.model_validate(product)


    async def get_all_products(self,
                               category: Optional[str] = None,
                               searchTerm: Optional[str] = None,
                               page: int = 1,
                               page_size: int = 10) -> List[ProductSchema]:
        # validating page and page_size
        page = max(1, page)
        page_size = min(max(1, page_size), 50) # limiting page size to 50

        query = select(Product).options(
            selectinload(Product.images),
            selectinload(Product.reviews),
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
            raise ProductNotFoundError(f'Products with category: {category} and/or search term.: {searchTerm} not found.')
        return [ProductSchema.model_validate(product) for product in products]


    async def get_product_by_id(self, product_id: UUID) -> ProductSchema:
        db_product = await self.session.execute(
            select(Product)
            .where(Product.id == product_id)
            .options(
                selectinload(Product.images),
                selectinload(Product.reviews),
                selectinload(Product.category)
            ))
        product = db_product.scalars().first()
        if not db_product:
            raise ProductNotFoundError(f"Product with id: {product_id} not found")
        return ProductSchema.model_validate(product)


    async def get_product_by_name(self, name: str) -> ProductSchema:
        db_product = await self.session.execute(
            select(Product)
            .where(Product.name == name)
            .options(
                selectinload(Product.images),
                selectinload(Product.reviews),
                selectinload(Product.category)
            ))
        product = db_product.scalars().first()
        if not product:
            raise ProductNotFoundError(f"Product with name: {name} not found")
        return ProductSchema.model_validate(product)
            
 
    async def update_product_availability(self, product_id: UUID, in_stock: bool) -> ProductBase:
        result = await self.session.execute(select(Product).where(Product.id == product_id))
        product = result.scalars().first()
        product.in_stock = in_stock
        await self.session.commit()
        await self.session.refresh(product)
        return ProductBase.model_validate(product)
  

    async def delete_product(self, product_id: UUID) -> None:
        product = await self.get_product_by_id(product_id)
        await self.session.delete(product)
        await self.session.commit()
   
 
