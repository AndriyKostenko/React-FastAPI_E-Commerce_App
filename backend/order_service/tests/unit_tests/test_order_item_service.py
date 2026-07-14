"""Unit tests for OrderItemService."""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from service_layer.order_item_service import OrderItemService
from shared.schemas.order_schemas import OrderItemBase, CreateOrder
from tests.constants import TEST_ORDER_ID, TEST_PRODUCT_ID, TEST_USER_ID, TEST_EMAIL


def _make_create_order_mock(num_products: int = 2) -> MagicMock:
    products = [
        MagicMock(id=uuid4(), name=f"Product {i}", price=9.99 * (i + 1), quantity=i + 1)
        for i in range(num_products)
    ]
    order_mock = MagicMock()
    order_mock.products = products
    return order_mock


class TestCreateOrderItems:
    async def test_create_order_items_returns_list(
        self, mock_order_item_service: OrderItemService, mock_order_item_orm: MagicMock
    ):
        """create_order_items calls repository.create_many and returns OrderItemBase list."""
        svc = mock_order_item_service
        item_orm = mock_order_item_orm
        item_orm.order_id = TEST_ORDER_ID
        item_orm.product_id = TEST_PRODUCT_ID
        item_orm.quantity = 2
        item_orm.price = 49.99

        svc.repository.create_many = AsyncMock(return_value=[item_orm])

        order_data = _make_create_order_mock(num_products=1)
        order_data.products[0].id = TEST_PRODUCT_ID
        order_data.products[0].quantity = 2
        order_data.products[0].price = 49.99

        result = await svc.create_order_items(TEST_ORDER_ID, order_data)

        assert len(result) == 1
        assert isinstance(result[0], OrderItemBase)
        assert result[0].order_id == TEST_ORDER_ID
        svc.repository.create_many.assert_awaited_once()

    async def test_create_order_items_multiple_products(
        self, mock_order_item_service: OrderItemService, mock_order_item_orm: MagicMock
    ):
        """create_order_items handles multiple products correctly."""
        svc = mock_order_item_service
        product_a_id = uuid4()
        product_b_id = uuid4()

        orm_a = MagicMock()
        orm_a.order_id = TEST_ORDER_ID
        orm_a.product_id = product_a_id
        orm_a.variant_id = None
        orm_a.quantity = 1
        orm_a.price = 10.0

        orm_b = MagicMock()
        orm_b.order_id = TEST_ORDER_ID
        orm_b.product_id = product_b_id
        orm_b.variant_id = None
        orm_b.quantity = 3
        orm_b.price = 20.0

        svc.repository.create_many = AsyncMock(return_value=[orm_a, orm_b])

        order_data = _make_create_order_mock(num_products=2)
        result = await svc.create_order_items(TEST_ORDER_ID, order_data)

        assert len(result) == 2

    async def test_create_order_items_empty_list(
        self, mock_order_item_service: OrderItemService
    ):
        """create_order_items with no products returns empty list."""
        svc = mock_order_item_service
        svc.repository.create_many = AsyncMock(return_value=[])

        order_data = _make_create_order_mock(num_products=0)
        result = await svc.create_order_items(TEST_ORDER_ID, order_data)

        assert result == []


class TestGetItemsByOrderId:
    async def test_get_items_by_order_id_returns_list(
        self, mock_order_item_service: OrderItemService, mock_order_item_orm: MagicMock
    ):
        svc = mock_order_item_service
        mock_order_item_orm.order_id = TEST_ORDER_ID
        mock_order_item_orm.product_id = TEST_PRODUCT_ID
        mock_order_item_orm.quantity = 2
        mock_order_item_orm.price = 49.99

        svc.repository.get_many_by_field = AsyncMock(return_value=[mock_order_item_orm])

        result = await svc.get_items_by_order_id(TEST_ORDER_ID)

        assert len(result) == 1
        assert isinstance(result[0], OrderItemBase)
        svc.repository.get_many_by_field.assert_awaited_once_with(
            field_name="order_id", value=TEST_ORDER_ID
        )

    async def test_get_items_by_order_id_returns_empty_when_none(
        self, mock_order_item_service: OrderItemService
    ):
        """get_items_by_order_id returns [] when repository returns None."""
        svc = mock_order_item_service
        svc.repository.get_many_by_field = AsyncMock(return_value=None)

        result = await svc.get_items_by_order_id(TEST_ORDER_ID)

        assert result == []
