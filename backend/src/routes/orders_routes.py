from typing import List, Annotated, Dict, Optional

from fastapi import Depends, APIRouter, status, HTTPException, Form, UploadFile, File, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
import os
from src.db.db_setup import get_db_session
from src.security.authentication import get_current_user
from src.service.product_service import ProductCRUDService
from src.schemas.product_schemas import CreateProduct, GetAllProducts
from src.utils.image_metadata import create_image_metadata
from src.utils.image_pathes import create_image_paths

order_routes = APIRouter(
    tags=["orders"]
)

@order_routes.post("/get_all_orders", status_code=status.HTTP_201_CREATED)
async def get_all_orders(current_user: Annotated[dict, Depends(get_current_user)],
                         session: AsyncSession = Depends(get_db_session)):
    if current_user["user_role"] != "admin" or current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    orders = await OrderCRUDService(session=session).get_all_orders()
    return orders
