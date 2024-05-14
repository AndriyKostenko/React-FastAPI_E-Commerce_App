from fastapi import Depends, APIRouter, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.db_setup import get_db_session
from src.service.product_service import ProductCRUDService
from src.schemas.product_schemas import CreateProduct


product_routes = APIRouter(
    tags=["product"]
)


@product_routes.post("/new_product")
async def create_new_product(product: CreateProduct,
                             session: AsyncSession = Depends(get_db_session)):
    new_product = await ProductCRUDService(session).create_product(product)
    return new_product
