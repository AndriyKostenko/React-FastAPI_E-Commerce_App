from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from models.product_models import Product
from shared.database_layer import BaseRepository 



class ProductRepository(BaseRepository[Product]):
    """
    This class extends BaseRepository to provide specific methods
    for managing products in the database.
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Product)
        
    
    async def get_product_with_relations(self, product_id: UUID) -> Optional[Product]:
        query = (
            select(Product)
            .options(
                selectinload(Product.images),
                selectinload(Product.reviews),
                selectinload(Product.category)
            )
            .where(Product.id == product_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
 
    async def search_products(self, search_term: str, filters: dict, limit: int, offset: int) -> List[Product]:
        query = select(Product)

        # Add search conditions
        if search_term:
            search_conditions = or_(
                Product.name.ilike(f"%{search_term}%"),
                Product.description.ilike(f"%{search_term}%"),
                Product.brand.ilike(f"%{search_term}%")
            )
            query = query.where(search_conditions)
        
        # Add other filters
        for field, value in filters.items():
            if hasattr(Product, field):
                query = query.where(getattr(Product, field) == value)
        
        query = query.offset(offset).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()


    async def search_products_with_relations(self, search_term: Optional[str], category: Optional[str], 
                                            limit: int, offset: int) -> List[Product]:
        query = (
            select(Product)
            .options(
                selectinload(Product.images),
                selectinload(Product.reviews),
                selectinload(Product.category)
            )
        )
        
        # Add search conditions
        if search_term:
            search_conditions = or_(
                Product.name.ilike(f"%{search_term}%"),
                Product.description.ilike(f"%{search_term}%"),
                Product.brand.ilike(f"%{search_term}%")
            )
            query = query.where(search_conditions)
        
        # Add category filter
        if category:
            query = query.where(Product.category_id == category)
        
        query = query.offset(offset).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()