from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from models.product_models import Product, ProductImage

class IProductRepository(ABC):
    """Interface for Product repository operations"""
    
    @abstractmethod
    async def add_product(self, product: Product) -> Product:
        """Add a new product to the database"""
        pass
    
    @abstractmethod
    async def add_product_images(self, images: list[ProductImage]) -> list[ProductImage]:
        """Add product images to the database"""
        pass
    
    @abstractmethod
    async def get_all_products(self,
                             category: Optional[str] = None,
                             searchTerm: Optional[str] = None,
                             page: int = 1,
                             page_size: int = 10) -> list[Product]:
        """Get all products with optional filtering and pagination"""
        pass
    
    @abstractmethod
    async def get_all_products_with_relations(self,
                                            category: Optional[str] = None,
                                            searchTerm: Optional[str] = None,
                                            page: int = 1,
                                            page_size: int = 10) -> list[Product]:
        """Get all products with their relations"""
        pass
    
    @abstractmethod
    async def get_product_by_id(self, product_id: UUID) -> Optional[Product]:
        """Get product by ID"""
        pass
    
    @abstractmethod
    async def get_product_by_name(self, name: str) -> Optional[Product]:
        """Get product by name"""
        pass
    
    @abstractmethod
    async def get_product_by_id_with_relations(self, product_id: UUID) -> Optional[Product]:
        """Get product by ID with all relations loaded"""
        pass
    
    @abstractmethod
    async def update_product(self, product: Product) -> Product:
        """Update an existing product"""
        pass
    
    @abstractmethod
    async def delete_product(self, product: Product) -> None:
        """Delete a product"""
        pass