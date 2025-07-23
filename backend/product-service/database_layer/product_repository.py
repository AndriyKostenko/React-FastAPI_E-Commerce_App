from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, desc

from models.product_models import Product, ProductImage
from shared.database_layer import BaseRepository



class ProductRepository(BaseRepository):
    """
    Product-specific repository with additional methods.
    Inherits from BaseRepository to manage database CRUD operations for Product entities.
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Product)
        self.session = session

    
    async def add_product_images(self, images: list[ProductImage]) -> list[ProductImage]:
        self.session.add_all(images)
        await self.session.commit()
        return images
        
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

    async def get_by_name(self, name: str) -> Optional[Product]:
        """Get product by name"""
        return await self.get_by_field("name", name)

    async def get_by_category(self, category_id: UUID) -> list[Product]:
        """Get products by category"""
        return await self.filter_by(category_id=category_id)

    async def get_in_stock(self) -> list[Product]:
        """Get products that are in stock"""
        return await self.filter_by(in_stock=True)
    
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

