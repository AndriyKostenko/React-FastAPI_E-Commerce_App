"""Unit tests for OrderAddressService."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from service_layer.order_address_service import OrderAddressService
from shared.schemas.order_schemas import OrderAddressBase
from tests.constants import (
    TEST_USER_ID, TEST_ORDER_ADDRESS_ID, TEST_ORDER_ID
)


def _make_create_order_mock() -> MagicMock:
    order_mock = MagicMock()
    order_mock.user_id = TEST_USER_ID
    order_mock.address = MagicMock(
        street="123 Test St",
        city="Testville",
        province="TS",
        postal_code="T1T 1T1",
    )
    return order_mock


class TestCreateOrderAddress:
    async def test_create_order_address_success(
        self, mock_order_address_service: OrderAddressService, mock_order_address_orm: MagicMock
    ):
        """create_order_address calls repository.create and returns OrderAddressBase."""
        svc = mock_order_address_service
        svc.repository.create = AsyncMock(return_value=mock_order_address_orm)

        order_data = _make_create_order_mock()
        result = await svc.create_order_address(order_data)

        assert isinstance(result, OrderAddressBase)
        assert result.user_id == mock_order_address_orm.user_id
        assert result.street == mock_order_address_orm.street
        assert result.city == mock_order_address_orm.city
        svc.repository.create.assert_awaited_once()

    async def test_create_order_address_sets_correct_fields(
        self, mock_order_address_service: OrderAddressService, mock_order_address_orm: MagicMock
    ):
        """create_order_address maps address fields from order_data correctly."""
        svc = mock_order_address_service
        svc.repository.create = AsyncMock(return_value=mock_order_address_orm)

        order_data = _make_create_order_mock()
        result = await svc.create_order_address(order_data)

        assert result.street == "123 Test St"
        assert result.city == "Testville"
        assert result.province == "TS"
        assert result.postal_code == "T1T 1T1"
