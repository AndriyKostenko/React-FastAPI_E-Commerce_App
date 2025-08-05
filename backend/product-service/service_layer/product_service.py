from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from models.product_models import Product
from schemas.product_schemas import CreateProduct, ProductBase, ProductSchema
from shared.database_layer import BaseRepository 
from errors.product_errors import (ProductNotFoundError,
                                  ProductCreationError)
from database_layer.product_repository import ProductRepository


class ProductService:
    """Service layer for product management operations, business logic and data validation."""
    
    def __init__(self, repository: ProductRepository):
        self.repository = repository


    async def create_product_item(self, product_data: CreateProduct) -> ProductSchema:
        existing_product = await self.repository.get_by_field("name", value=product_data.name.lower())
        if existing_product:
            raise ProductCreationError(f'Product with name: "{product_data.name}" already exists.')
        
        new_product = Product(name=product_data.name.lower(),
                              description=product_data.description,
                              category_id=product_data.category_id,
                              brand=product_data.brand.lower(),
                              quantity=product_data.quantity,
                              price=product_data.price,
                              in_stock=product_data.in_stock)
        new_db_product = await self.repository.create(new_product)

        return ProductSchema.model_validate(new_db_product)


    async def get_all_products(self,
                               category: Optional[str] = None,
                               search_term: Optional[str] = None,
                               page: int = 1,
                               page_size: int = 10) -> List[ProductBase]:
        offset = (page - 1) * page_size
        
        # building filters
        filters = {}
        if category:
            filters['category_id'] = category
            
        if search_term:
            products = await self.repository.search_products(search_term, filters, page_size, offset)
        else:
            products = await self.repository.filter_by(**filters)
            # applying pagination
            products = products[offset:offset + page_size] if offset < len(products) else []
        
        if not products:
            ProductNotFoundError(f"Products with category: {category} and/or search term: {search_term} not found")
            
        
        return [ProductBase.model_validate(product) for product in products]
    
    
    async def get_product_by_id(self, product_id: UUID) -> ProductBase:
        db_product = await self.repository.get_by_id(product_id)
        if not db_product:
            raise ProductNotFoundError(f"Product with id: {product_id} not found")
        return ProductBase.model_validate(db_product)


    async def get_product_by_name(self, name: str) -> ProductBase:
        db_product = await self.repository.get_by_field("name", name.lower())
        if not db_product:
            raise ProductNotFoundError(f"Product with name: {name} not found")
        return ProductBase.model_validate(db_product)
    
    
    async def get_all_products_with_relations(self,
                                               category: Optional[str] = None,
                                               search_term: Optional[str] = None,
                                               page: int = 1,
                                               page_size: int = 10) -> List[ProductSchema]:
        offset = (page - 1) * page_size
        products = await self.repository.search_products_with_relations(
            search_term=search_term,
            category=category,
            limit=page_size,
            offset=offset
        )
        
        if not products:
            raise ProductNotFoundError(f'Products with category: {category} and/or search term: {search_term} not found.')
        
        return [ProductSchema.model_validate(product) for product in products]

 
    async def update_product_availability(self, product_id: UUID, in_stock: bool) -> ProductBase:
        updated_product = await self.repository.update_by_id(product_id, in_stock=in_stock)
        if not updated_product:
            raise ProductNotFoundError(f"Product with id: {product_id} not found.")
        return ProductBase.model_validate(updated_product)

  
    async def delete_product(self, product_id: UUID) -> None:
        success = await self.repository.delete_by_id(product_id)
        if not success:
            raise ProductNotFoundError(f"Product with id: {product_id} not found")


