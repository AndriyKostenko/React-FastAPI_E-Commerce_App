from typing import Annotated, Any
from uuid import UUID

from fastapi import Query, UploadFile
from shared.utils.filter_parser import FilterParser
from sqlalchemy.exc import IntegrityError

from database_layer.product_repository import ProductRepository
from exceptions.product_exceptions import (
    ProductCreationError,
    ProductNotFoundError,
    ProductReleaseError,
    ProductUpdateError
)
from models.product_models import Product
from shared.schemas.order_schemas import OrderItemBase
from shared.schemas.product_schemas import (
    CreateProduct,
    ProductBase,
    ProductSchema,
    ProductsFilterParams,
    UpdateProduct,
)
from service_layer.product_image_service import ProductImageService
from utils.image_processing import image_processing_manager


class ProductService:
    """Service layer for product management operations, business logic and data validation."""
    def __init__(self, repository: ProductRepository, product_image_service: ProductImageService):
        self.repository: ProductRepository = repository
        self.product_image_service:ProductImageService = product_image_service
        self.product_relations: list[str] = Product.get_relations()
        self.product_search_fileds: list[str] = Product.get_search_fields()
        self.filter_parser: FilterParser = FilterParser()

    async def create_product_item(self, product_data: CreateProduct) -> ProductBase:
        existing_product = await self.repository.get_by_field(
            "name", value=product_data.name.lower()
        )
        if existing_product:
            raise ProductCreationError(
                f'Product with name: "{product_data.name}" already exists.'
            )

        new_product = Product(
            name=product_data.name.lower(),
            description=product_data.description,
            category_id=product_data.category_id,
            brand=product_data.brand.lower(),
            quantity=product_data.quantity,
            price=product_data.price,
            in_stock=product_data.in_stock,
        )
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

        return ProductBase.model_validate(new_db_product)

    async def create_product_with_images(self,
                                         product_data: CreateProduct,
                                         images: list[UploadFile],
                                         image_colors: list[str],
                                         image_color_codes: list[str]) -> ProductSchema:
        image_urls = await image_processing_manager.save_images(images)
        image_metadata = image_processing_manager.create_metadata_list(
            image_urls=image_urls,
            image_colors=image_colors,
            image_color_codes=image_color_codes,
        )
        new_product = await self.create_product_item(product_data)
        await self.product_image_service.create_product_images(
            product_id=new_product.id,
            images=image_metadata
        )
        full_product = await self.repository.get_by_id(
            item_id=new_product.id,
            load_relations=Product.get_relations(),  # category, images, reviews
        )
        return ProductSchema.model_validate(full_product)

    async def get_product_by_id_without_relations(self, product_id: UUID) -> ProductBase:
        db_product = await self.repository.get_by_id(item_id=product_id)
        if not db_product:
            raise ProductNotFoundError(f"Product with id: {product_id} not found")
        return ProductBase.model_validate(db_product)

    async def get_product_by_id_with_relations(self, product_id: UUID) -> ProductSchema:
        product = await self.repository.get_by_id(
            item_id=product_id,
            load_relations=self.product_relations
        )
        if not product:
            raise ProductNotFoundError(f"Product with id: {product_id} not found.")
        return ProductSchema.model_validate(product)

    async def get_all_products_without_relations(self,
                                                filters_query: Annotated[ProductsFilterParams, Query()]) -> list[ProductBase]:
        params = self.filter_parser.parse_filter_params(filter_query=filters_query)
        products = await self.repository.get_all(**params)
        if not products:
            raise ProductNotFoundError("No products found with the given criteria.")
        return [ProductBase.model_validate(product) for product in products]

    async def get_all_products_with_relations(self,
                                              filters_query: Annotated[ProductsFilterParams, Query()]) -> list[ProductSchema]:
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

    async def get_products_by_ids(self, products_ids: list[UUID]) -> list[ProductBase]:
        products = await self.repository.get_many_by_field(field_name='id', value=products_ids, limit=50)
        if not products:
            raise ProductNotFoundError("No products found with the given IDs.")
        return [ProductBase.model_validate(product) for product in products]

    async def update_product(self,
                            product_id: UUID,
                            product_data: UpdateProduct) -> ProductBase:
        update_dict = product_data.model_dump(exclude_unset=True)
        if not update_dict:
            raise ProductUpdateError("Failed to update product: no data to update is provided")
        try:
            updated_product = await self.repository.update_by_id(product_id, data=update_dict)
            if not updated_product:
                raise ProductNotFoundError(f"Product with id: {product_id} not found")
            return ProductBase.model_validate(updated_product)
        except IntegrityError as e:
            if "products_category_id_fkey" in str(e):
                raise ProductCreationError(
                    f'Category with id "{update_dict.get("category_id")}" does not exist.'
                )
            raise

    async def delete_product_by_id(self, product_id: UUID) -> None:
        success = await self.repository.delete_by_id(product_id)
        if not success:
            raise ProductNotFoundError(f"Product with id: {product_id} not found")

    async def reserve_inventory(self, items: list[OrderItemBase]) -> dict[str, Any]:
        """
        Reserve inventory via atomic per-row decrements.

        Each item is decremented with a single ``UPDATE … WHERE quantity >= requested``
        statement, eliminating the TOCTOU race condition that would arise from the
        classic read-check-write pattern.  Two concurrent reservation requests for
        the same product cannot both succeed unless there is genuinely enough stock
        for both — the database enforces this atomically.
        """
        failed_items: list[OrderItemBase] = []
        reasons: set[str] = set()
        reserved_items: list[OrderItemBase] = []

        for item in items:
            updated = await self.repository.atomic_decrement_quantity(
                item_id=item.product_id,
                requested=item.quantity,
            )

            if updated is None:
                # Row not found OR insufficient stock / out of stock — distinguish for UX
                product = await self.repository.get_by_id(item.product_id)
                if product is None:
                    reasons.add(f"Product with ID: {item.product_id} not found")
                elif not product.in_stock:
                    reasons.add(f"Product: {product.name}, ID: {product.id} is out of stock")
                else:
                    reasons.add(
                        f"Insufficient quantity for product: {product.name}, ID: {product.id}, "
                        f"requested: {item.quantity}, available: {product.quantity}"
                    )
                failed_items.append(item)
                continue

            reserved_items.append(item)

        if failed_items:
            return {
                "success": False,
                "reasons": "; ".join(reasons),
                "failed_products": failed_items,
            }
        return {
            "success": True,
            "products": reserved_items,
        }

    async def release_inventory(self, products: list[OrderItemBase]):
        """
        Release inventory via atomic per-row increments (SAGA compensation).

        Each item is incremented with a single ``UPDATE … SET quantity = quantity + amount``
        statement so concurrent release events cannot double-add stock.
        """
        for item in products:
            updated = await self.repository.atomic_increment_quantity(
                item_id=item.product_id,
                amount=item.quantity,
            )
            if updated is None:
                raise ProductReleaseError(
                    f"Cannot release inventory for product: {item.product_id} — product not found"
                )
