from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Request, UploadFile, status
from shared.customized_json_response import JSONResponse
from shared.shared_instances import product_service_redis_manager

from dependencies.dependencies import (
    product_service_dependency,
)
from models.product_models import Product
from shared.schemas.product_schemas import (
    CreateProduct,
    ProductBase,
    ProductSchema,
    ProductsFilterParams,
    UpdateProduct,
)

product_routes = APIRouter(tags=["products"])


@product_routes.post(
    "/products",
    response_model=ProductBase,
    summary="Create product (JSON)",
    response_description="New product created",
)
@product_service_redis_manager.ratelimiter(times=10, seconds=60)
async def create_product_json(
    request: Request,
    product_service: product_service_dependency,
    product_data: CreateProduct) -> JSONResponse:
    """
    Create a new product using JSON payload.
    Used by AdminJS and API clients. (without images uploads for now)
    """
    created_product = await product_service.create_product_item(
        product_data=product_data
    )
    await product_service_redis_manager.clear_cache_namespace(
        namespace="products", request=request
    )
    return JSONResponse(content=created_product, status_code=status.HTTP_201_CREATED)


@product_routes.post(
    "/products/upload",
    response_model=ProductBase,
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
) -> JSONResponse:
    """
    Create a new product with optional image uploads.
    Used by frontend forms that need to upload files.
    """
    # Validate and prepare product data
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
    await product_service_redis_manager.clear_cache_namespace(
        namespace="products", request=request
    )
    return JSONResponse(content=created_product, status_code=status.HTTP_201_CREATED)


@product_routes.get(
    "/products", response_model=list[ProductBase], response_description="All products"
)
@product_service_redis_manager.cached(ttl=300)
@product_service_redis_manager.ratelimiter(times=100, seconds=60)
async def get_all_products(
    request: Request,
    product_service: product_service_dependency,
    filters_query: Annotated[ProductsFilterParams, Query()],
) -> JSONResponse:
    products = await product_service.get_all_products_without_relations(
        filters_query=filters_query
    )
    return JSONResponse(content=products, status_code=status.HTTP_200_OK)


@product_routes.get(
    "/products/detailed",
    response_model=list[ProductSchema],
    response_description="All products with relations",
)
@product_service_redis_manager.cached(ttl=600)
@product_service_redis_manager.ratelimiter(times=50, seconds=60)
async def get_all_products_detailed(
    request: Request,
    product_service: product_service_dependency,
    filters_query: Annotated[ProductsFilterParams, Query()],
) -> JSONResponse:
    product_with_relations = await product_service.get_all_products_with_relations(
        filters_query=filters_query
    )
    return JSONResponse(content=product_with_relations, status_code=status.HTTP_200_OK)


@product_routes.get(
    "/products/{product_id}",
    response_model=ProductBase,
    response_description="Product by ID",
)
@product_service_redis_manager.cached(ttl=180)
@product_service_redis_manager.ratelimiter(times=200, seconds=60)
async def get_product_by_id(
    request: Request, product_id: UUID, product_service: product_service_dependency
) -> JSONResponse:
    product = await product_service.get_product_by_id_without_relations(
        product_id=product_id
    )
    return JSONResponse(content=product, status_code=status.HTTP_200_OK)


@product_routes.get(
    "/products/{product_id}/detailed",
    response_model=ProductBase,
    response_description="Product by ID",
)
@product_service_redis_manager.cached(ttl=180)
@product_service_redis_manager.ratelimiter(times=200, seconds=60)
async def get_product_by_id_detailed(
    request: Request, product_id: UUID, product_service: product_service_dependency
) -> JSONResponse:
    product = await product_service.get_product_by_id_with_relations(
        product_id=product_id
    )
    return JSONResponse(content=product, status_code=status.HTTP_200_OK)


# JSON endpoint for updating product
@product_routes.patch(
    "/products/{product_id}",
    response_model=ProductBase,
    summary="Update product (JSON)",
    response_description="Product updated",
)
@product_service_redis_manager.ratelimiter(times=30, seconds=60)
async def update_product_json(
    request: Request,
    product_id: UUID,
    product_service: product_service_dependency,
    product_data: UpdateProduct,
) -> JSONResponse:
    """
    Update a product using JSON payload.
    Used by AdminJS and API clients. (without images uploads for now)
    """
    product = await product_service.update_product(
        product_id=product_id, product_data=product_data
    )
    await product_service_redis_manager.clear_cache_namespace(
        namespace="products", request=request
    )
    return JSONResponse(content=product, status_code=status.HTTP_200_OK)


@product_routes.delete(
    "/products/{product_id}",
    response_description="Product deleted",
    status_code=status.HTTP_204_NO_CONTENT,
)
@product_service_redis_manager.ratelimiter(times=10, seconds=60)
async def delete_product_by_id(
    request: Request, product_id: UUID, product_service: product_service_dependency
):
    await product_service.delete_product_by_id(product_id=product_id)
    # Clear ALL product-related cache
    await product_service_redis_manager.clear_cache_namespace(
        namespace="products", request=request
    )
    return


# FormData endpoint for updating product with images
@product_routes.patch(
    "/products/{product_id}/upload",
    response_model=ProductBase,
    summary="Update product with images (FormData)",
    response_description="Product updated with images",
)
@product_service_redis_manager.ratelimiter(times=30, seconds=60)
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
) -> JSONResponse:
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
    await product_service_redis_manager.clear_cache_namespace(
        namespace="products", request=request
    )
    return JSONResponse(content=product, status_code=status.HTTP_200_OK)


@product_routes.get("/admin/schema/products", summary="Schema for AdminJS")
async def get_product_schema_for_admin_js(request: Request):
    return JSONResponse(
        content={"fields": Product.get_admin_schema()}, status_code=status.HTTP_200_OK
    )
