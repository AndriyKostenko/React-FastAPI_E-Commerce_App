from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, desc

from models.product_models import Product, ProductImage



class ProductRepository:
    """ Handles direct DB access for Product entity. No business logic. """
    
    def __init__(self, session: AsyncSession):
        self.session = session

    # CREATE
    async def add_product(self, product: Product) -> Product:
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        return product
    
    async def add_product_images(self, images: list[ProductImage]) -> list[ProductImage]:
        self.session.add_all(images)
        await self.session.commit()
        return images
        
    
    # READ
    async def get_all_products(self,
                               category: Optional[str] = None,
                               searchTerm: Optional[str] = None,
                               page: int = 1,
                               page_size: int = 10,
                               ) -> list[Product]:
        # validating page and page_size
        page = max(1, page)
        page_size = min(max(1, page_size), 50)  # limiting page size to 50
        
        query = select(Product).order_by(desc(Product.date_created))
        
        if category:
            query = query.filter(Product.category.has(name=category))
        if searchTerm:
            query = query.filter(Product.name.ilike(f"%{searchTerm}%"))
            
        # Apply pagination using offset and limit
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_all_products_with_relations(self,
                               category: Optional[str] = None,
                               searchTerm: Optional[str] = None,
                               page: int = 1,
                               page_size: int = 10,
                               ) -> list[Product]:
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
        return result.scalars().all()

    async def get_product_by_id(self, product_id: UUID) -> Optional[Product]:
        result = await self.session.execute(select(Product).where(Product.id == product_id))
        return result.scalars().first()
    
    async def get_product_by_name(self, name: str) -> Optional[Product]:
        result = await self.session.execute(select(Product).where(Product.name == name))
        return result.scalars().first()
    
    async def get_product_by_id_with_relations(self, product_id: UUID) -> Optional[Product]:
        result = await self.session.execute(
            select(Product)
            .where(Product.id == product_id)
            .options(
                selectinload(Product.images),
                selectinload(Product.reviews),
                selectinload(Product.category)
            )
        )
        return result.scalars().first()

    # UPDATE
    async def update_product(self, product: Product) -> Product:
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        return product

    # DELETE
    async def delete_product(self, product: Product) -> None:
        await self.session.delete(product)
        await self.session.commit()