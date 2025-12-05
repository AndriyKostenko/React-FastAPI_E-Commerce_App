from typing import Annotated, List, Any
from uuid import UUID

from fastapi import Query, UploadFile
from sqlalchemy.exc import IntegrityError

from models.product_models import Product
from models.product_image_models import ProductImage
from schemas.product_image_schema import ProductImageSchema
from schemas.product_schemas import CreateProduct, ProductBase, ProductSchema, ProductsFilterParams, UpdateProduct
from exceptions.product_exceptions import ProductNotFoundError, ProductCreationError
from database_layer.product_repository import ProductRepository
from shared.filter_parser import FilterParser
from service_layer.product_image_service import ProductImageService
from utils.image_pathes import create_image_paths


class ProductService:
    """Service layer for product management operations, business logic and data validation."""
    
    def __init__(self, repository: ProductRepository, image_repository: ProductImageRepository):
        self.repository = repository
        self.image_repository = image_repository
        self.product_relations = Product.get_relations()
        self.product_search_fileds = Product.get_search_fields()
        self.filter_parser = FilterParser()
        

    async def create_product_item(self, product_data: CreateProduct, images: Optional[list[UploadFile]] = None) -> ProductBase:
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
        try: 
            new_db_product = await self.repository.create(new_product)
        except IntegrityError as e:
            # Check if it's a foreign key violation for category_id (the category_id does not exist)
            if "products_category_id_fkey" in str(e):
                raise ProductCreationError(
                    f'Category with id "{product_data.category_id}" does not exist.'
                )
            # Re-raise other integrity errors
            raise ProductCreationError(f"Failed to create product: {str(e)}")
        
        # Handle images if provided
        if images:
            await self._create_product_images(
                product_id=new_db_product.id,
                images=images
            )

        return ProductBase.model_validate(new_db_product)


    # TODO: check if its correct implementation
    async def _create_product_images(self, 
                                     product_id: UUID, 
                                     images: List[UploadFile]) -> List[ProductImage]:
        """Helper method to create product images."""
        image_paths = create_image_paths(images=images)
        
        product_images = [
            ProductImage(
                product_id=product_id,
                image_url=image.image_url,
                image_color=image.image_color,
                image_color_code=image.image_color_code
            ) 
            for image in images
        ]
        
        created_images = await self.image_repository.create_many(product_images)
        return [ProductImageSchema.model_validate(img) for img in created_images]
    
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
        params = self.filter_parser.parse_filter_params(filter_query=filters_query)
        products = await self.repository.get_all(**params)
        if not products:
            raise ProductNotFoundError("No products found with the given criteria.")
        return [ProductBase.model_validate(product) for product in products]
    
    async def get_all_products_with_relations(self, filters_query: Annotated[ProductsFilterParams, Query()]) -> List[ProductSchema]:
        # Parse filters using helper method and add relations
        params = self.filter_parser.parse_filter_params(filter_query=filters_query)
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

    # TODO: check for correct implementstion
    async def update_product(self, 
                             product_id: UUID, 
                             product_data: UpdateProduct,
                             images: Optional[List[UploadFile]] = None) -> ProductBase:
        update_dict = product_data.model_dump(exclude_unset=True)
        if "name" in update_dict and update_dict["name"]:
            update_dict["name"] = update_dict["name"].lower()
        if "brand" in update_dict and update_dict["brand"]:
            update_dict["brand"] = update_dict["brand"].lower()

        # Remove None values
        update_dict = {k: v for k, v in update_dict.items() if v is not None}

        updated_product = None
        
        if update_dict:
            try:
                updated_product = await self.repository.update_by_id(product_id, **update_dict)
            except IntegrityError as e:
                if "products_category_id_fkey" in str(e):
                    raise ProductCreationError(
                        f'Category with id "{update_dict.get("category_id")}" does not exist.'
                    )
                raise ProductCreationError(f"Failed to update product: {str(e)}")
            
            if not updated_product:
                raise ProductNotFoundError(f"Product with id: {product_id} not found.")
        
        # Handle new images if provided
        if images:
            await self._create_product_images(product_id=product_id, images=images)

        return ProductBase.model_validate(updated_product)

    async def delete_product_by_id(self, product_id: UUID) -> None:
        success = await self.repository.delete_by_id(product_id)
        if not success:
            raise ProductNotFoundError(f"Product with id: {product_id} not found")


