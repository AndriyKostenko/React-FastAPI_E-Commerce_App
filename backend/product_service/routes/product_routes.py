from decimal import Decimal
from typing import Annotated, Any, Optional
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Request, UploadFile, status

from dependencies.dependencies import (
    product_service_dependency,
)
from models.product_models import Product
from shared.shared_instances import settings
from shared.schemas.product_schemas import (
    CustomTshirtPricingResponse,
    CreateProduct,
    ProductBase,
    ProductSchema,
    ProductsFilterParams,
    UpdateProduct,
)

product_routes = APIRouter(tags=["products"])




@product_routes.get(
    "/customization/pricing",
    response_model=CustomTshirtPricingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get custom T-shirt base pricing",
)
async def get_custom_tshirt_pricing(request: Request) -> CustomTshirtPricingResponse:
    return CustomTshirtPricingResponse(
        base_price=settings.CUSTOM_TSHIRT_BASE_PRICE,
        currency="USD",
    )


@product_routes.post(
    "/products",
    response_model=ProductBase,
    status_code=status.HTTP_201_CREATED,
    summary="Create product (JSON)",
    response_description="New product created",
)
async def create_product_json(
    request: Request,
    product_service: product_service_dependency,
    product_data: CreateProduct) -> ProductBase:
    """
    Create a new product using JSON payload.
    Used by AdminJS and API clients. (without images uploads for now)
    """
    created_product = await product_service.create_product_item(
        product_data=product_data
    )
    return created_product


@product_routes.post(
    "/products/upload",
    response_model=ProductBase,
    status_code=status.HTTP_201_CREATED,
    summary="Create product with FormData",
)
async def create_product_with_images(
    request: Request,
    product_service: product_service_dependency,
    name: str = Form(...),
    description: str = Form(...),
    category_id: UUID = Form(...),
    brand: str = Form(...),
    quantity: int = Form(...),
    price: Decimal = Form(...),
    in_stock: bool = Form(...),
    images: list[UploadFile] = File(...),
    image_colors: list[str] = Form(...),
    image_color_codes: list[str] = Form(...),
) -> ProductBase:
    """
    Create a new product with optional image uploads.
    Used by frontend forms that need to upload files.
    """
    product_data = CreateProduct(
        name=name,
        description=description,
        category_id=category_id,
        brand=brand,
        quantity=quantity,
        price=price,
        in_stock=in_stock,
    )
    created_product = await product_service.create_product_with_images(
        product_data=product_data,
        images=images,
        image_colors=image_colors,
        image_color_codes=image_color_codes,
    )
    return created_product


@product_routes.get(
    "/products",
    response_model=list[ProductBase],
    response_description="All products",
    status_code=status.HTTP_200_OK,
)
async def get_all_products(
    request: Request,
    product_service: product_service_dependency,
    filters_query: Annotated[ProductsFilterParams, Query()],
) -> list[ProductBase]:
    products = await product_service.get_all_products_without_relations(
        filters_query=filters_query
    )
    return products


@product_routes.get(
    "/products/detailed",
    response_model=list[ProductSchema],
    response_description="All products with relations",
    status_code=status.HTTP_200_OK
)
async def get_all_products_detailed(
    request: Request,
    product_service: product_service_dependency,
    filters_query: Annotated[ProductsFilterParams, Query()],
) -> list[ProductSchema]:
    return await product_service.get_all_products_with_relations(
        filters_query=filters_query
    )


@product_routes.get(
    "/products/{product_id}",
    response_model=ProductBase,
    response_description="Product by ID",
    status_code=status.HTTP_200_OK,
)
async def get_product_by_id(
    request: Request, product_id: UUID, product_service: product_service_dependency
) -> ProductBase:
    product = await product_service.get_product_by_id_without_relations(
        product_id=product_id
    )
    return product


@product_routes.get(
    "/products/{product_id}/detailed",
    response_model=ProductBase,
    response_description="Product by ID",
    status_code=status.HTTP_200_OK,
)
async def get_product_by_id_detailed(
    request: Request, product_id: UUID, product_service: product_service_dependency
) -> ProductBase:
    product = await product_service.get_product_by_id_with_relations(
        product_id=product_id
    )
    return product


@product_routes.patch(
    "/products/{product_id}",
    response_model=ProductBase,
    status_code=status.HTTP_200_OK,
    summary="Update product (JSON)",
    response_description="Product updated",
)
async def update_product_json(
    request: Request,
    product_id: UUID,
    product_service: product_service_dependency,
    product_data: UpdateProduct,
) -> ProductBase:
    """
    Update a product using JSON payload.
    Used by AdminJS and API clients. (without images uploads for now)
    """
    product = await product_service.update_product(
        product_id=product_id, product_data=product_data
    )
    return product


@product_routes.delete(
    "/products/{product_id}",
    response_description="Product deleted",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_product_by_id(
    request: Request, product_id: UUID, product_service: product_service_dependency
):
    await product_service.delete_product_by_id(product_id=product_id)
    return


@product_routes.patch(
    "/products/{product_id}/upload",
    response_model=ProductBase,
    status_code=status.HTTP_200_OK,
    summary="Update product with images (FormData)",
    response_description="Product updated with images",
)
async def update_product_with_images(
    request: Request,
    product_id: UUID,
    product_service: product_service_dependency,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category_id: Optional[UUID] = Form(None),
    brand: Optional[str] = Form(None),
    quantity: Optional[int] = Form(None),
    price: Optional[Decimal] = Form(None),
    in_stock: Optional[bool] = Form(None),
    images: Optional[list[UploadFile]] = File(None),
) -> ProductBase:
    """
    Update a product with optional image uploads.
    Used by frontend forms that need to upload files.
    """
    product_data = UpdateProduct(
        name=name,
        description=description,
        category_id=category_id,
        brand=brand,
        quantity=quantity,
        price=price,
        in_stock=in_stock,
    )
    product = await product_service.update_product(
        product_id=product_id,
        product_data=product_data,
    )
    return product


@product_routes.get(
    "/admin/schema/products",
    summary="Schema for AdminJS",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
)
async def get_product_schema_for_admin_js(request: Request):
    return {"fields": Product.get_admin_schema()}
