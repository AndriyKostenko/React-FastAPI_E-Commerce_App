from decimal import Decimal

import pytest

from shared.shared_instances import test_settings


@pytest.mark.asyncio
class TestShippingMethodRoutes:
    async def test_list_active_methods(self, client_for_unit_testing, mock_route_shipping_method_service):
        response = await client_for_unit_testing.get("/api/v1/shipping/methods")

        assert response.status_code == 200
        mock_route_shipping_method_service.list_active_methods.assert_awaited_once()

    async def test_get_method(self, client_for_unit_testing, mock_route_shipping_method_service):
        response = await client_for_unit_testing.get(f"/api/v1/shipping/methods/{test_settings.TEST_SHIPPING_METHOD_ID}")

        assert response.status_code == 200
        mock_route_shipping_method_service.get_method_by_id.assert_awaited_once()

    async def test_create_method(self, client_for_unit_testing, mock_route_shipping_method_service):
        payload = {
            "name": "Express",
            "carrier": "UPS",
            "base_cost": "12.99",
            "estimated_days": 2,
            "is_active": True,
        }
        response = await client_for_unit_testing.post("/api/v1/shipping/methods", json=payload)

        assert response.status_code == 200
        mock_route_shipping_method_service.create_method.assert_awaited_once()

    async def test_update_method(self, client_for_unit_testing, mock_route_shipping_method_service):
        payload = {"name": "Updated Name"}
        response = await client_for_unit_testing.patch(f"/api/v1/shipping/methods/{test_settings.TEST_SHIPPING_METHOD_ID}", json=payload)

        assert response.status_code == 200
        mock_route_shipping_method_service.update_method.assert_awaited_once()

    async def test_delete_method(self, client_for_unit_testing, mock_route_shipping_method_service):
        response = await client_for_unit_testing.delete(f"/api/v1/shipping/methods/{test_settings.TEST_SHIPPING_METHOD_ID}")

        assert response.status_code == 200
        mock_route_shipping_method_service.delete_method.assert_awaited_once()


@pytest.mark.asyncio
class TestShipmentRoutes:
    async def test_create_shipment(self, client_for_unit_testing, mock_route_shipment_service):
        payload = {
            "order_id": str(test_settings.TEST_ORDER_ID),
            "user_id": str(test_settings.TEST_USER_ID),
            "user_email": "test@example.com",
            "method_id": str(test_settings.TEST_SHIPPING_METHOD_ID),
            "destination": {
                "street": "123 Main St",
                "city": "Toronto",
                "province": "ON",
                "postal_code": "M5V 1K4",
            },
        }
        response = await client_for_unit_testing.post("/api/v1/shipments", json=payload)

        assert response.status_code == 200
        mock_route_shipment_service.create_shipment.assert_awaited_once()

    async def test_get_shipment_by_id(self, client_for_unit_testing, mock_route_shipment_service):
        response = await client_for_unit_testing.get(f"/api/v1/shipments/{test_settings.TEST_SHIPMENT_ID}")

        assert response.status_code == 200
        mock_route_shipment_service.get_shipment_by_id.assert_awaited_once()

    async def test_get_shipment_by_order_id(self, client_for_unit_testing, mock_route_shipment_service):
        response = await client_for_unit_testing.get(f"/api/v1/shipments/order/{test_settings.TEST_ORDER_ID}")

        assert response.status_code == 200
        mock_route_shipment_service.get_shipment_by_order_id.assert_awaited_once()

    async def test_update_shipment(self, client_for_unit_testing, mock_route_shipment_service):
        payload = {"status": "shipped", "tracking_number": "TRACK123"}
        response = await client_for_unit_testing.patch(f"/api/v1/shipments/{test_settings.TEST_SHIPMENT_ID}", json=payload)

        assert response.status_code == 200
        mock_route_shipment_service.update_shipment.assert_awaited_once()

    async def test_calculate_rates(self, client_for_unit_testing, mock_route_shipment_service):
        payload = {
            "destination": {
                "street": "123 Main St",
                "city": "Toronto",
                "province": "ON",
                "postal_code": "M5V 1K4",
            },
            "weight_kg": "2.5",
        }
        response = await client_for_unit_testing.post("/api/v1/shipping/rates", json=payload)

        assert response.status_code == 200
        mock_route_shipment_service.calculate_rate.assert_awaited_once()
