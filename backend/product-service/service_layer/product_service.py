from datetime import datetime
from typing import Annotated, List, Optional, Union, Any
from uuid import UUID

from fastapi import Query

from models.product_models import Product
from schemas.product_schemas import CreateProduct, ProductBase, ProductSchema, ProductsFilterParams
from exceptions.product_exceptions import ProductNotFoundError, ProductCreationError
from database_layer.product_repository import ProductRepository


class ProductService:
    """Service layer for product management operations, business logic and data validation."""
    
    def __init__(self, repository: ProductRepository):
        self.repository = repository
        self.product_relations = Product.get_relations()
        self.product_search_fileds = Product.get_search_fields()
        
    def _parse_filter_params(self, filters_query: ProductsFilterParams) -> dict[str, Any]:
        """
        Helper method to parse ProductsFilterParams into repository-compatible parameters.
        
        Returns a dictionary with:
        - filters: dict of field filters
        - sort_by: sorting field
        - sort_order: asc/desc
        - offset: pagination offset
        - limit: pagination limit
        - search_term: search string
        - date_filters: dict of date range filters
        """
        filters_dict = filters_query.model_dump()
        
        # Extract pagination and sorting params
        offset = filters_dict.pop("offset", None)
        limit = filters_dict.pop("limit", None)
        sort_by = filters_dict.pop("sort_by", None)
        sort_order = filters_dict.pop("sort_order", "asc")
        search_term = filters_dict.pop("search_term", None)
        
        # Extract date range filters
        date_filters = {
            "date_created_from": filters_dict.pop("date_created_from", None),
            "date_created_to": filters_dict.pop("date_created_to", None),
            "date_updated_from": filters_dict.pop("date_updated_from", None),
            "date_updated_to": filters_dict.pop("date_updated_to", None)
        }
        
        # Clean remaining filters (remove None values)
        cleaned_filters = {key: value for key, value in filters_dict.items() if value is not None}
    
        return {
            "filters": cleaned_filters,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "offset": offset,
            "limit": limit,
            "search_term": search_term,
            "date_filters": date_filters,
            "search_fields": self.product_search_fileds
        }

    async def create_product_item(self, product_data: CreateProduct) -> ProductBase:
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

        return ProductBase.model_validate(new_db_product)
    
    async def get_product_by_id_without_relations(self, product_id: UUID) -> ProductBase:
        db_product = await self.repository.get_by_id(item_id=product_id)
        if not db_product:
            raise ProductNotFoundError(f"Product with id: {product_id} not found")
        return ProductBase.model_validate(db_product)

    async def get_product_by_id_with_relations(self, product_id: UUID) -> ProductSchema:
        product = await self.repository.get_by_id(item_id=product_id, load_relations=self.product_relations)
        if not product:
            raise ProductNotFoundError(f"Product with id: {product_id} not found.")
        return ProductSchema.model_validate(product)
    
    async def get_all_products_without_relations(self, 
                                                 filters_query: Annotated[ProductsFilterParams, Query()]) -> List[ProductBase]:
        params = self._parse_filter_params(filters_query)
        products = await self.repository.get_all(**params)
        if not products:
            raise ProductNotFoundError("No products found with the given criteria.")
        return [ProductBase.model_validate(product) for product in products]
    
    async def get_all_products_with_relations(self, filters_query: Annotated[ProductsFilterParams, Query()]) -> List[ProductSchema]:
        # Parse filters using helper method and add relations
        params = self._parse_filter_params(filters_query)
        params["load_relations"] = self.product_relations
        
        products = await self.repository.get_all(**params)
        if not products:
            raise ProductNotFoundError("No products found with the given criteria.")
        return [ProductSchema.model_validate(product) for product in products]

    async def get_product_by_name(self, name: str) -> ProductBase:
        db_product = await self.repository.get_by_field("name", name.lower())
        if not db_product:
            raise ProductNotFoundError(f"Product with name: {name} not found")
        return ProductBase.model_validate(db_product)
    
    async def update_product_availability(self, product_id: UUID, in_stock: bool) -> ProductBase:
        updated_product = await self.repository.update_by_id(product_id, in_stock=in_stock)
        if not updated_product:
            raise ProductNotFoundError(f"Product with id: {product_id} not found.")
        return ProductBase.model_validate(updated_product)

    async def delete_product_by_id(self, product_id: UUID) -> None:
        success = await self.repository.delete_by_id(product_id)
        if not success:
            raise ProductNotFoundError(f"Product with id: {product_id} not found")
        return None


