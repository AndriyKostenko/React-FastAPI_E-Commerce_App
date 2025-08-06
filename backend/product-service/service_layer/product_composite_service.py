from sqlalchemy.ext.asyncio import AsyncSession
from .product_service import ProductService
from .product_image_service import ProductImageService


# TODO: Implement a composite service for product operations
# that involves both product and image services.

# class ProductCompositeService:
#     """Handles complex product operations involving multiple services"""
    
#     def __init__(self, session: AsyncSession):
#         self.product_service = ProductService(session)
#         self.image_service = ProductImageService(session)
#         self.session = session
    
#     async def create_complete_product(self, product_data: CreateProduct) -> ProductSchema:
#         """Create product with images in a single transaction"""
#         async with self.session.begin():  # Transaction
#             # Create product
#             product = await self.product_service.create_product_item(product_data)
            
#             # Add images
#             if product_data.images:
#                 await self.image_service.create_product_images(product.id, product_data.images)
            
#             # Return complete product with relations
#             return await self.product_service.get_product_by_id_with_relations(product.id)