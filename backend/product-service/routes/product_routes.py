from decimal import Decimal
from typing import Optional, Annotated
from uuid import UUID

from fastapi import APIRouter, status, Form, Request, Query # type: ignore

from dependencies.dependencies import product_service_dependency
from schemas.product_schemas import ProductBase, ProductSchema, CreateProduct, ProductsFilterParams
from shared.customized_json_response import JSONResponse
from shared.shared_instances import product_service_redis_manager
from models.product_models import Product


product_routes = APIRouter(
    tags=["products"]
)


@product_routes.post("/products",  
                     response_model=ProductBase,
                     response_description="New product created")
@product_service_redis_manager.ratelimiter(times=10, seconds=60)
async def create_new_product(request: Request,
                             product_service: product_service_dependency,
                             product_data: CreateProduct) -> JSONResponse:
    product_data = CreateProduct(name=product_data.name.lower(),
                                description=product_data.description,
                                category_id=product_data.category_id,
                                brand=product_data.brand.lower(),
                                quantity=product_data.quantity,
                                price=product_data.price,
                                in_stock=product_data.in_stock)

    created_product = await product_service.create_product_item(product_data=product_data)
    
    # Clear ALL product-related cache
    await product_service_redis_manager.clear_cache_namespace(namespace="products", request=request)
    
    return JSONResponse(
        content=created_product,
        status_code=status.HTTP_201_CREATED
    )


@product_routes.get("/products", 
                    response_model=list[ProductBase],
                    response_description="All products")
@product_service_redis_manager.cached(ttl=300)
@product_service_redis_manager.ratelimiter(times=100, seconds=60)
async def get_all_products(request: Request,
                           product_service: product_service_dependency,
                           filters_query: Annotated[ProductsFilterParams, Query()]) -> JSONResponse:
    products = await product_service.get_all_products_without_relations(filters_query=filters_query)
    return JSONResponse(
        content=products,
        status_code=status.HTTP_200_OK
    )
        

@product_routes.get("/products/detailed", 
                    response_model=list[ProductSchema],
                    response_description="All products with relations")
@product_service_redis_manager.cached(ttl=600)
@product_service_redis_manager.ratelimiter(times=50, seconds=60)
async def get_all_products_detailed(request: Request,
                                    product_service: product_service_dependency,
                                    filters_query: Annotated[ProductsFilterParams, Query()]
                                    ) -> JSONResponse:
    product_with_relations = await product_service.get_all_products_with_relations(filters_query=filters_query)
    return JSONResponse(
        content=product_with_relations,
        status_code=status.HTTP_200_OK
    )


@product_routes.get("/products/id/{product_id}", 
                    response_model=ProductBase,
                    response_description="Product by ID")
@product_service_redis_manager.cached(ttl=180)
@product_service_redis_manager.ratelimiter(times=200, seconds=60)
async def get_product_by_id(request: Request,
                            product_id: UUID,
                            product_service: product_service_dependency) -> JSONResponse:
    product = await product_service.get_product_by_id_without_relations(product_id=product_id)
    return JSONResponse(
        content=product,
        status_code=status.HTTP_200_OK
    )
  
    
@product_routes.get("/products/id/{product_id}/detailed", 
                    response_model=ProductBase,
                    response_description="Product by ID")
@product_service_redis_manager.cached(ttl=180)
@product_service_redis_manager.ratelimiter(times=200, seconds=60)
async def get_product_by_id_detailed(request: Request,
                                    product_id: UUID,
                                    product_service: product_service_dependency) -> JSONResponse:
    product = await product_service.get_product_by_id_with_relations(product_id=product_id)
    return JSONResponse(
        content=product,
        status_code=status.HTTP_200_OK
    )


@product_routes.get("/products/name/{product_name}", 
                    response_model=ProductBase,
                    response_description="Product by name")
@product_service_redis_manager.cached(ttl=180)
@product_service_redis_manager.ratelimiter(times=200, seconds=60)
async def get_product_by_name(request: Request,
                              product_name: str,
                              product_service: product_service_dependency) -> JSONResponse:
    product = await product_service.get_product_by_name(name=product_name.lower())
    return JSONResponse(
        content=product,
        status_code=status.HTTP_200_OK
    )


@product_routes.patch("/products/{product_id}/availability", 
                      response_model=ProductBase,
                      response_description="Product availability updated")
@product_service_redis_manager.ratelimiter(times=30, seconds=60)
async def update_product_availability(request: Request,
                                      product_id: UUID,
                                      in_stock: bool,
                                      product_service: product_service_dependency) -> JSONResponse:
    product = await product_service.update_product_availability(product_id=product_id, in_stock=in_stock)
    # Clear ALL product-related cache
    await product_service_redis_manager.clear_cache_namespace(namespace="products", request=request)
    return JSONResponse(
        content=product,
        status_code=status.HTTP_200_OK
    )
        
    
@product_routes.delete("/products/{product_id}", 
                       response_description="Product deleted")
@product_service_redis_manager.ratelimiter(times=10, seconds=60)
async def delete_product(request: Request,
                         product_id: UUID,
                         product_service: product_service_dependency) -> JSONResponse:
    await product_service.delete_product_by_id(product_id=product_id)
    # Clear ALL product-related cache
    await product_service_redis_manager.clear_cache_namespace(namespace="products", request=request)
    return JSONResponse(
        content=None,
        status_code=status.HTTP_204_NO_CONTENT
    )


@product_routes.get("/admin/schema/products", summary="Schema for AdminJS")
async def get_product_schema_for_admin_js(request: Request):
    return JSONResponse(content={"fields": Product.get_admin_schema()},
                        status_code=status.HTTP_200_OK)