from typing import List, Annotated, Dict, Optional

from fastapi import Depends, APIRouter, status, HTTPException, Form, UploadFile, File, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
import os
from src.db.db_setup import get_db_session
from src.security.authentication import get_current_user
from src.service.order_service import OrderCRUDService
from src.schemas.product_schemas import CreateProduct, GetAllProducts
from src.utils.image_metadata import create_image_metadata
from src.utils.image_pathes import create_image_paths
from src.schemas.order_schemas import UpdateOrder

order_routes = APIRouter(
    tags=["orders"]
)


@order_routes.get("/orders", status_code=status.HTTP_200_OK)
async def get_all_orders(current_user: Annotated[dict, Depends(get_current_user)],
                         session: AsyncSession = Depends(get_db_session)):
    if current_user["user_role"] != "admin" or current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    orders = await OrderCRUDService(session=session).get_all_orders()
    return orders

@order_routes.get("/orders/{id}", status_code=status.HTTP_200_OK)
async def get_order_by_order_id(id: str,
                    session: AsyncSession = Depends(get_db_session)):
    order = await OrderCRUDService(session=session).get_order_with_items_by_id(order_id=id)
    return order

@order_routes.get("/orders/user/{id}", status_code=status.HTTP_200_OK)
async def get_orders_by_user_id(id: str,
                    session: AsyncSession = Depends(get_db_session)):
    orders = await OrderCRUDService(session=session).get_orders_with_items_by_user_id(user_id=id)
    return orders

@order_routes.put("/orders/{id}", status_code=status.HTTP_200_OK)
async def update_order(id: str,
                    order_updates: UpdateOrder,  # Fetch updated fields from body
                    current_user: Annotated[dict, Depends(get_current_user)],
                    session: AsyncSession = Depends(get_db_session)):
    order = await OrderCRUDService(session=session).update_order_by_id(order_id=id, order_updates=order_updates)
    return order

