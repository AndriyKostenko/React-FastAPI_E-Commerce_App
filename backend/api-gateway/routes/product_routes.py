from uuid import UUID

from fastapi import APIRouter, Request, Depends

from apigateway import api_gateway_manager
from dependencies.auth_dependencies import (get_current_user,
                                            require_admin,
                                            require_user_or_admin)
from schemas.schemas import CurrentUserInfo

product_proxy = APIRouter(tags=["Product Service Proxy"])


# ==================== PUBLIC ENDPOINTS ====================

# Products
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
    
@product_proxy.get("/products/{product_id}/detailed", summary="Get detailed product by ID")
async def get_detailed_product_by_id(request: Request,
                                      product_id: UUID):
    """PUBLIC - Anyone can view detailed product information"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )
    
    
# Categories
@product_proxy.get("/categories", summary="Get all categories")
async def get_all_categories(request: Request):
    """PUBLIC - Anyone can browse categories"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )

@product_proxy.get("/categories/{category_id}", summary="Get category by ID")
async def get_category_by_id(request: Request,
                             category_id: UUID):
    """PUBLIC - Anyone can view category details"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )


# Product Images
@product_proxy.get("/{product_id}/images", summary="Get all product images")
async def get_product_images(request: Request,
                             product_id: UUID):
    """PUBLIC - Anyone can view product images"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )

@product_proxy.get("/images/{image_id}", summary="Get image by ID")
async def get_image_by_id(request: Request,
                         image_id: UUID):
    """PUBLIC - Anyone can view image details"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )


# Reviews
@product_proxy.get("/reviews", summary="Get all reviews")
async def get_all_reviews(request: Request):
    """PUBLIC - Anyone can view all reviews"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )

@product_proxy.get("/products/{product_id}/reviews", summary="Get product reviews")
async def get_product_reviews(request: Request,
                              product_id: UUID):
    """PUBLIC - Anyone can view product reviews"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )

@product_proxy.get("/reviews/{review_id}", summary="Get review by ID")
async def get_review_by_id(request: Request,
                          review_id: UUID):
    """PUBLIC - Anyone can view review details"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )



# ==================== ADMIN ONLY ENDPOINTS ====================

# Products
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


# Categories
@product_proxy.post("/categories", summary="Create new category")
async def create_category(request: Request,
                         current_user: CurrentUserInfo = Depends(require_admin)):
    """ADMIN ONLY - Create categories"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )

@product_proxy.patch("/categories/{category_id}", summary="Update category")
async def update_category(request: Request,
                         category_id: UUID,
                         current_user: CurrentUserInfo = Depends(require_admin)):
    """ADMIN ONLY - Update categories"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )

@product_proxy.delete("/categories/{category_id}", summary="Delete category")
async def delete_category(request: Request,
                         category_id: UUID,
                         current_user: CurrentUserInfo = Depends(require_admin)):
    """ADMIN ONLY - Delete categories"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )


# Product Images
@product_proxy.post("/{product_id}/images", summary="Add product images")
async def add_product_images(request: Request,
                            product_id: UUID,
                            current_user: CurrentUserInfo = Depends(require_admin)):
    """ADMIN ONLY - Add product images"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )

@product_proxy.put("/{product_id}/images", summary="Replace product images")
async def replace_product_images(request: Request,
                                product_id: UUID,
                                current_user: CurrentUserInfo = Depends(require_admin)):
    """ADMIN ONLY - Replace all product images"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )

@product_proxy.patch("/images/{image_id}", summary="Update product image")
async def update_product_image(request: Request,
                              image_id: UUID,
                              current_user: CurrentUserInfo = Depends(require_admin)):
    """ADMIN ONLY - Update product image"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )

@product_proxy.delete("/images/{image_id}", summary="Delete product image")
async def delete_product_image(request: Request,
                              image_id: UUID,
                              current_user: CurrentUserInfo = Depends(require_admin)):
    """ADMIN ONLY - Delete product image"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )


# ==================== AUTHENTICATED USER ENDPOINTS ====================

# Reviews
@product_proxy.post("/products/{product_id}/users/{user_id}/reviews", summary="Create product review")
async def create_product_review(request: Request,
                                product_id: UUID,
                                user_id: UUID,
                                current_user: CurrentUserInfo = Depends(get_current_user)):
    """PROTECTED - Authenticated users can create reviews"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )

@product_proxy.patch("/reviews/{review_id}", summary="Update review")
async def update_review(request: Request,
                       review_id: UUID,
                       current_user: CurrentUserInfo = Depends(require_user_or_admin)):
    """PROTECTED - Users can update their own reviews, admins can update any"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request,
    )

@product_proxy.delete("/reviews/{review_id}", summary="Delete review")
async def delete_review(request: Request,
                       review_id: UUID,
                       current_user: CurrentUserInfo = Depends(require_user_or_admin)):
    """PROTECTED - Users can delete their own reviews, admins can delete any"""
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

@product_proxy.get("/admin/schema/products", summary="Get product schema for AdminJS")
async def get_product_schema_for_admin_js(request: Request):
    """Get product schema for AdminJS"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request
    )

@product_proxy.get("/admin/schema/categories", summary="Get category schema for AdminJS")
async def get_category_schema_for_admin_js(request: Request):
    """Get category schema for AdminJS"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request
    )
    
    
@product_proxy.get("/admin/schema/product_images", summary="Get product_images schema for AdminJS")
async def get_category_schema_for_admin_js(request: Request):
    """Get category schema for AdminJS"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request
    )
    
    
@product_proxy.get("/admin/schema/product_reviews", summary="Get product_reviews schema for AdminJS")
async def get_category_schema_for_admin_js(request: Request):
    """Get category schema for AdminJS"""
    return await api_gateway_manager.forward_request(
        service_name="product-service",
        request=request
    )