from typing import List, Optional
from uuid import UUID






from errors.product_errors import (ProductNotFoundError,
                                  ProductCreationError)
from models.product_models import Product, ProductImage
from models.review_models import ProductReview
from schemas.product_schemas import CreateProduct, ProductBase, ProductSchema
from repositories.product_repository import ProductRepository

class ProductService:
    """Service layer for product management operations, business logic and data validation."""
    def __init__(self, repo: ProductRepository):
        self.repo = repo

    async def create_product_item(self, product_data: CreateProduct) -> ProductSchema:
        db_product = await self.repo.get_product_by_name(name=product_data.name.lower())
        if db_product:
            raise ProductCreationError(f'Product with name: "{product_data.name}" already exists.')
        # 1. creating product
        new_product = Product(name=product_data.name,
                              description=product_data.description,
                              category_id=product_data.category_id,
                              brand=product_data.brand,
                              quantity=product_data.quantity,
                              price=product_data.price,
                              in_stock=product_data.in_stock)
        
        new_db_product = await self.repo.add_product(new_product)
        
        # 2. adding product images
        product_images = [
            ProductImage(
                product_id=new_db_product.id,
                image_url=image.image_url,
                image_color=image.image_color,
                image_color_code=image.image_color_code
            ) 
            for image in product_data.images
        ]
        await self.repo.add_product_images(images=product_images)
        
        # 3. Now re-query with relationships loaded
        product_with_relations = await self.repo.get_product_by_id_with_relations(product_id=new_db_product.id)
        return ProductSchema.model_validate(product_with_relations)


    async def get_all_products(self,
                               category: Optional[str] = None,
                               searchTerm: Optional[str] = None,
                               page: int = 1,
                               page_size: int = 10) -> List[ProductBase]:
        db_products = await self.repo.get_all_products(category=category,
                                                       searchTerm=searchTerm,
                                                       page=page,
                                                       page_size=page_size)
        if not db_products or len(db_products) == 0:
            raise ProductNotFoundError(f'Products with category: {category} and/or search term.: {searchTerm} not found.')
        return [ProductBase.model_validate(product) for product in db_products]
    
    
    async def get_all_products_with_relations(self,
                                               category: Optional[str] = None,
                                               searchTerm: Optional[str] = None,
                                               page: int = 1,
                                               page_size: int = 10) -> List[ProductSchema]:
        db_products = await self.repo.get_all_products_with_relations(category=category,
                                                                      searchTerm=searchTerm,
                                                                      page=page,
                                                                      page_size=page_size)
        if not db_products or len(db_products) == 0:
            raise ProductNotFoundError(f'Products with category: {category} and/or search term.: {searchTerm} not found.')
        return [ProductSchema.model_validate(product) for product in db_products]


    async def get_product_by_id(self, product_id: UUID) -> ProductBase:
        db_product = await self.repo.get_product_by_id(product_id)
        if not db_product:
            raise ProductNotFoundError(f"Product with id: {product_id} not found")
        return ProductBase.model_validate(db_product)


    async def get_product_by_name(self, name: str) -> ProductBase:
        db_product = await self.repo.get_product_by_name(name=name)
        if not db_product:
            raise ProductNotFoundError(f"Product with name: {name} not found")
        return ProductBase.model_validate(db_product)
 
 
    async def update_product_availability(self, product_id: UUID, in_stock: bool) -> ProductBase:
        db_product = await self.repo.get_product_by_id(product_id)
        if not db_product:
            raise ProductNotFoundError(f"Product with id: {product_id} not found")
        db_product.in_stock = in_stock
        updated_product = await self.repo.update_product(db_product)
        return ProductBase.model_validate(updated_product)

  
    async def delete_product(self, product_id: UUID) -> None:
        db_product = await self.repo.get_product_by_id(product_id)
        if not db_product:
            raise ProductNotFoundError(f"Product with id: {product_id} not found")
        await self.repo.delete_product(db_product)
        return None
   
 
