from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from exceptions.shipping_exceptions import (
    DuplicateShipmentError,
    InvalidShipmentStatusError,
    ShipmentNotFoundError,
    ShippingMethodNotFoundError,
)
from models.shipping_models import ShippingMethod, Shipment
from service_layer.shipping_method_service import ShippingMethodService
from service_layer.shipment_service import ShipmentService
from shared.schemas.shipping_schemas import CreateShipment, CreateShippingMethod, UpdateShipment
from shared.shared_instances import test_settings
from unittest.mock import patch


class TestShippingMethodService:
    async def test_create_method(self, shipping_method_service_unit, mock_method_repository):
        create_data = CreateShippingMethod(
            name="Express",
            carrier="UPS",
            base_cost=Decimal("12.99"),
            estimated_days=2,
            is_active=True,
        )
        mock_method = MagicMock(spec=ShippingMethod)
        mock_method.id = test_settings.TEST_SHIPPING_METHOD_ID
        mock_method.name = "Express"
        mock_method.carrier = "UPS"
        mock_method.base_cost = Decimal("12.99")
        mock_method.estimated_days = 2
        mock_method.is_active = True
        mock_method.date_created = test_settings.TEST_DATETIME
        mock_method.date_updated = None
        mock_method_repository.create.return_value = mock_method

        result = await shipping_method_service_unit.create_method(create_data)

        assert result.name == "Express"
        assert result.carrier == "UPS"
        mock_method_repository.create.assert_awaited_once()

    async def test_get_method_by_id_not_found(self, shipping_method_service_unit, mock_method_repository):
        mock_method_repository.get_by_id.return_value = None

        with pytest.raises(ShippingMethodNotFoundError):
            await shipping_method_service_unit.get_method_by_id(test_settings.TEST_SHIPPING_METHOD_ID)

    async def test_list_active_methods(self, shipping_method_service_unit, mock_method_repository, mock_shipping_method_orm):
        mock_method_repository.get_active_methods.return_value = [mock_shipping_method_orm]

        result = await shipping_method_service_unit.list_active_methods()

        assert len(result) == 1
        assert result[0].name == "Standard Shipping"


class TestShipmentService:
    async def test_create_shipment_success(self, shipment_service_unit, mock_shipment_repository, mock_method_repository, mock_shipping_method_orm):
        mock_method_repository.get_by_id.return_value = mock_shipping_method_orm
        mock_shipment_repository.get_by_order_id.return_value = None
        mock_shipment = MagicMock(spec=Shipment)
        mock_shipment.id = test_settings.TEST_SHIPMENT_ID
        mock_shipment.order_id = test_settings.TEST_ORDER_ID
        mock_shipment.user_id = test_settings.TEST_USER_ID
        mock_shipment.method_id = test_settings.TEST_SHIPPING_METHOD_ID
        mock_shipment.status = "pending"
        mock_shipment.tracking_number = None
        mock_shipment.estimated_delivery = test_settings.TEST_DATETIME
        mock_shipment.shipped_at = None
        mock_shipment.delivered_at = None
        mock_shipment.cancelled_at = None
        mock_shipment.cancellation_reason = None
        mock_shipment.date_created = test_settings.TEST_DATETIME
        mock_shipment.date_updated = None
        mock_shipment_repository.create.return_value = mock_shipment

        create_data = CreateShipment(
            order_id=test_settings.TEST_ORDER_ID,
            user_id=test_settings.TEST_USER_ID,
            method_id=test_settings.TEST_SHIPPING_METHOD_ID,
            destination={"street": "123 Main St", "city": "Toronto", "province": "ON", "postal_code": "M5V 1K4"},
        )

        result = await shipment_service_unit.create_shipment(create_data)

        assert result.status == "pending"
        assert result.order_id == test_settings.TEST_ORDER_ID

    async def test_create_shipment_duplicate(self, shipment_service_unit, mock_method_repository, mock_shipment_repository, mock_shipment_orm):
        mock_method_repository.get_by_id.return_value = mock_shipment_orm.method
        mock_shipment_repository.get_by_order_id.return_value = mock_shipment_orm

        create_data = CreateShipment(
            order_id=test_settings.TEST_ORDER_ID,
            user_id=test_settings.TEST_USER_ID,
            method_id=test_settings.TEST_SHIPPING_METHOD_ID,
            destination={"street": "123 Main St", "city": "Toronto", "province": "ON", "postal_code": "M5V 1K4"},
        )

        with pytest.raises(DuplicateShipmentError):
            await shipment_service_unit.create_shipment(create_data)

    async def test_get_shipment_by_id_not_found(self, shipment_service_unit, mock_shipment_repository):
        mock_shipment_repository.get_by_id.return_value = None

        with pytest.raises(ShipmentNotFoundError):
            await shipment_service_unit.get_shipment_by_id(test_settings.TEST_SHIPMENT_ID)

    async def test_update_shipment_status_to_shipped(self, shipment_service_unit, mock_shipment_repository, mock_method_repository, mock_shipment_orm):
        mock_shipment_repository.get_by_id.return_value = mock_shipment_orm
        updated_orm = MagicMock(spec=Shipment)
        updated_orm.id = test_settings.TEST_SHIPMENT_ID
        updated_orm.order_id = test_settings.TEST_ORDER_ID
        updated_orm.user_id = test_settings.TEST_USER_ID
        updated_orm.method_id = test_settings.TEST_SHIPPING_METHOD_ID
        updated_orm.status = "shipped"
        updated_orm.tracking_number = "TRACK123"
        updated_orm.estimated_delivery = None
        updated_orm.shipped_at = test_settings.TEST_DATETIME
        updated_orm.delivered_at = None
        updated_orm.cancelled_at = None
        updated_orm.cancellation_reason = None
        updated_orm.date_created = test_settings.TEST_DATETIME
        updated_orm.date_updated = test_settings.TEST_DATETIME
        mock_shipment_repository.update_by_id.return_value = updated_orm

        update_data = UpdateShipment(status="shipped", tracking_number="TRACK123")
        with patch("service_layer.shipment_service.shipping_event_publisher.publish_shipment_shipped") as mock_publish:
            result = await shipment_service_unit.update_shipment(test_settings.TEST_SHIPMENT_ID, update_data)

        assert result.status == "shipped"
        assert result.tracking_number == "TRACK123"
        mock_publish.assert_awaited_once()

    async def test_update_shipment_invalid_transition(self, shipment_service_unit, mock_shipment_repository, mock_method_repository, mock_shipment_orm):
        mock_shipment_orm.status = "delivered"
        mock_shipment_repository.get_by_id.return_value = mock_shipment_orm

        update_data = UpdateShipment(status="shipped")

        with pytest.raises(InvalidShipmentStatusError):
            await shipment_service_unit.update_shipment(test_settings.TEST_SHIPMENT_ID, update_data)
