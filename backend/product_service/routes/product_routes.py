from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Request, UploadFile, status, Depends

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
    ProductUploadForm,
    ProductsFilterParams,
    UpdateProduct,
)


product_routes = APIRouter(tags=["products"])


@product_routes.get("/customization/pricing",
                    response_model=CustomTshirtPricingResponse,
                    status_code=status.HTTP_200_OK,
                    summary="Get custom T-shirt base pricing")
async def get_custom_tshirt_pricing() -> CustomTshirtPricingResponse:
    return CustomTshirtPricingResponse(base_price=settings.CUSTOM_TSHIRT_BASE_PRICE, currency="CAD")


@product_routes.post("/products",
                    response_model=ProductBase,
                    status_code=status.HTTP_201_CREATED,
                    summary="Create product (JSON)",
                    response_description="New product created")
async def create_product_json(product_service: product_service_dependency, product_data: CreateProduct) -> ProductBase:
    """
    Create a new product using JSON payload.
    Used by AdminJS and API clients. (without images uploads for now)
    """
    created_product = await product_service.create_product_item(product_data=product_data)
    return created_product


@product_routes.post("/products/upload",
                    response_model=ProductSchema,
                    status_code=status.HTTP_201_CREATED,
                    summary="Create product with FormData")
async def create_product_with_images(product_service: product_service_dependency,
                                     form_data: ProductUploadForm = Depends(ProductUploadForm.return_as_form)) -> ProductBase:
    """
    Create a new product with optional image uploads.
    Used by frontend forms that need to upload files.
    """
    return await product_service.create_product_with_images(product_data=form_data)


@product_routes.get(
    "/products",
    response_model=list[ProductBase],
    response_description="All products",
    status_code=status.HTTP_200_OK,
)
async def get_all_products(product_service: product_service_dependency,
                           filters_query: Annotated[ProductsFilterParams, Query()]) -> list[ProductBase]:
    return await product_service.get_all_products_without_relations(filters_query=filters_query)


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
    response_model=ProductSchema,
    response_description="Product by ID with relations",
    status_code=status.HTTP_200_OK,
)
async def get_product_by_id_detailed(product_id: UUID, product_service: product_service_dependency) -> ProductSchema:
    return await product_service.get_product_by_id_with_relations(product_id=product_id)


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
