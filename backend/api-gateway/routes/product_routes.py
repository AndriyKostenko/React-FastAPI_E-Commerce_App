from uuid import UUID

from fastapi import APIRouter, Request, Depends

from apigateway import api_gateway_manager
from dependencies.auth_dependencies import (get_current_user,
                                            require_admin,
                                            require_user_or_admin)
from schemas.schemas import CurrentUserInfo

product_proxy = APIRouter(tags=["Product Service Proxy"])


# ==================== PUBLIC ENDPOINTS ====================

@product_proxy.get("/products", summary="Get all products")
async def get_all_products(request: Request):
    """PUBLIC - Anyone can browse products"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )
    
@product_proxy.get("/products/detailed", summary="Get all products with details")
async def get_all_products_detailed(request: Request):
    """PUBLIC - Anyone can browse products with details"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )

@product_proxy.get("/products/{product_id}", summary="Get product by ID")
async def get_product_by_id(request: Request,
                            product_id: UUID):
    """PUBLIC - Anyone can view product details"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )
    
    
# Categories



# ==================== ADMIN ONLY ENDPOINTS ====================

@product_proxy.post("/products", summary="Create new product")
async def create_product(request: Request,
                        current_user: CurrentUserInfo = Depends(require_admin)):
    """ADMIN ONLY - Create products"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )

@product_proxy.patch("/products/{product_id}", summary="Update product")
async def update_product(request: Request,
                        product_id: UUID,
                        current_user: CurrentUserInfo = Depends(require_admin)):
    """ADMIN ONLY - Update products"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )

@product_proxy.delete("/products/{product_id}", summary="Delete product")
async def delete_product(request: Request,
                        product_id: UUID,
                        current_user: CurrentUserInfo = Depends(require_admin)):
    """ADMIN ONLY - Delete products"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )
    
@product_proxy.get("/products/{product_id}/detailed", summary="Get detailed product by ID")
async def get_detailed_product_by_id(request: Request,
                                      product_id: UUID):
    """PUBLIC - Anyone can view detailed product information"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )


# ==================== AUTHENTICATED USER ENDPOINTS ====================

@product_proxy.post("/products/{product_id}/reviews", summary="Add product review")
async def add_product_review(request: Request,
                             product_id: UUID,
                             current_user: CurrentUserInfo = Depends(get_current_user)):
    """PROTECTED - Authenticated users can review products"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )

@product_proxy.post("/products/{product_id}/favorite", summary="Add to favorites")
async def add_to_favorites(request: Request,
                           product_id: UUID,
                           current_user: CurrentUserInfo = Depends(get_current_user)):
    """PROTECTED - Authenticated users can favorite products"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )


# ==================== ADMINJS ENDPOINTS ====================

@product_proxy.get("/admin/schema/products")
async def get_product_schema_for_admin_js(request: Request):
    # for now no admin restriction on this endpoint
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request
    )

