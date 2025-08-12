from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, status, Form, Request

from dependencies.dependencies import product_service_dependency
from schemas.product_schemas import ProductBase, ProductSchema, CreateProduct
from shared.customized_json_response import JSONResponse
from shared.shared_instances import product_service_redis_manager, settings


product_routes = APIRouter(
    tags=["products"]
)


@product_routes.post("/products",  
                     response_model=ProductBase,
                     response_description="New product created")
@product_service_redis_manager.cached(ttl=30)
@product_service_redis_manager.ratelimiter(times=10, seconds=60)
async def create_new_product(request: Request,
                             product_service: product_service_dependency,
                             name: str = Form(..., min_length=3, max_length=50),
                             description: str = Form(..., min_length=10, max_length=500),
                             category_id: UUID = Form(...),
                             brand: str = Form(...),
                             quantity: int = Form(..., ge=0, le=100),
                             price: Decimal = Form(..., ge=0, le=100),
                             in_stock: bool = Form(...),
                             ) -> JSONResponse:

    # convert in_stock to boolean coz it will be passed as a string from client
    if isinstance(in_stock, str):
        if in_stock.lower() == "true":
            in_stock = True
        else:
            in_stock = False
    
    product_data = CreateProduct(name=name.lower(),
                                description=description,
                                category_id=category_id,
                                brand=brand.lower(),
                                quantity=quantity,
                                price=price,
                                in_stock=in_stock)

    created_product = await product_service.create_product_item(product_data=product_data)
    
    # Clear ALL product-related cache
    await product_service_redis_manager.clear_cache_namespace(
        namespace=f"{settings.PRODUCT_SERVICE_URL_API_VERSION}/products*"
    )
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
                           categoryId: Optional[UUID] = None,
                           searchTerm: Optional[str] = None,
                           page: int = 1,
                           pageSize: int = 10,
                           ) -> JSONResponse:
    products = await product_service.get_all_products(category_id=categoryId,
                                                      search_term=searchTerm,
                                                      page_size=pageSize,
                                                      page=page)
    return JSONResponse(
        content=products,
        status_code=status.HTTP_200_OK
    )
        

@product_routes.get("/products/with_relations", 
                    response_model=list[ProductSchema],
                    response_description="All products with relations")
@product_service_redis_manager.cached(ttl=600)
@product_service_redis_manager.ratelimiter(times=50, seconds=60)
async def get_all_products_with_relations(request: Request,product_service: product_service_dependency,
                                          categoryId: Optional[UUID] = None,
                                          searchTerm: Optional[str] = None,
                                          page: int = 1,
                                          page_size: int = 10,
                                          ) -> JSONResponse:
    product_with_relations =  await product_service.get_all_products_with_relations(category_id=categoryId,
                                                                  search_term=searchTerm,
                                                                  page_size=page_size,
                                                                  page=page)
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
    product = await product_service.get_product_by_id(product_id=product_id)
    return JSONResponse(
        content=product,
        status_code=status.HTTP_200_OK
    )


@product_routes.get("/products/name/{product_name}", 
                    response_model=ProductBase,
                    response_description="Product by name")
@product_service_redis_manager.cached(ttl=180)
@product_service_redis_manager.ratelimiter(times=200, seconds=60)
async def get_product_by_name(request: Request,product_name: str,
                              product_service: product_service_dependency) -> JSONResponse:
    product = await product_service.get_product_by_name(name=product_name.lower())
    return JSONResponse(
        content=product,
        status_code=status.HTTP_200_OK
    )


@product_routes.patch("/products/{product_id}", 
                      response_model=ProductBase,
                      response_description="Product availability updated")
@product_service_redis_manager.ratelimiter(times=30, seconds=60)
async def update_product_availability(request: Request,
                                      product_id: UUID,
                                      in_stock: bool,
                                      product_service: product_service_dependency) -> JSONResponse:
    product = await product_service.update_product_availability(product_id=product_id, in_stock=in_stock)
    
    # Clear ALL product-related cache
    await product_service_redis_manager.clear_cache_namespace(
        namespace=f"{settings.PRODUCT_SERVICE_URL_API_VERSION}/products*"
    )
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
    await product_service.delete_product(product_id=product_id)
    
    # Clear ALL product-related cache
    await product_service_redis_manager.clear_cache_namespace(
        namespace=f"{settings.PRODUCT_SERVICE_URL_API_VERSION}/products*"
    )
    return JSONResponse(
        content=None,
        status_code=status.HTTP_204_NO_CONTENT
    )

