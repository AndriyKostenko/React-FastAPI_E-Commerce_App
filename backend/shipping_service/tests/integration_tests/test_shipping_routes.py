import pytest


@pytest.mark.asyncio
class TestShippingMethodIntegration:
    async def test_create_and_list_methods(self, integration_client):
        payload = {
            "name": "Standard",
            "carrier": "FedEx",
            "base_cost": "5.99",
            "estimated_days": 5,
            "is_active": True,
        }
        create_response = await integration_client.post("/api/v1/shipping/methods", json=payload)
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["name"] == "Standard"

        list_response = await integration_client.get("/api/v1/shipping/methods")
        assert list_response.status_code == 200
        methods = list_response.json()
        assert len(methods) == 1
        assert methods[0]["name"] == "Standard"

    async def test_update_method(self, integration_client):
        payload = {
            "name": "Standard",
            "carrier": "FedEx",
            "base_cost": "5.99",
            "estimated_days": 5,
            "is_active": True,
        }
        create_response = await integration_client.post("/api/v1/shipping/methods", json=payload)
        method_id = create_response.json()["id"]

        update_response = await integration_client.patch(
            f"/api/v1/shipping/methods/{method_id}",
            json={"name": "Updated Standard"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Updated Standard"


@pytest.mark.asyncio
class TestShipmentIntegration:
    async def test_create_and_get_shipment(self, integration_client):
        method_payload = {
            "name": "Standard",
            "carrier": "FedEx",
            "base_cost": "5.99",
            "estimated_days": 5,
            "is_active": True,
        }
        method_response = await integration_client.post("/api/v1/shipping/methods", json=method_payload)
        method_id = method_response.json()["id"]

        shipment_payload = {
            "order_id": "12345678-1234-5678-1234-567812345678",
            "user_id": "87654321-4321-8765-4321-876543218765",
            "user_email": "test@example.com",
            "method_id": method_id,
            "destination": {
                "street": "123 Main St",
                "city": "Toronto",
                "province": "ON",
                "postal_code": "M5V 1K4",
            },
        }
        create_response = await integration_client.post("/api/v1/shipments", json=shipment_payload)
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["status"] == "pending"

        get_response = await integration_client.get(f"/api/v1/shipments/{created['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["order_id"] == shipment_payload["order_id"]

    async def test_update_shipment_status(self, integration_client):
        method_payload = {
            "name": "Standard",
            "carrier": "FedEx",
            "base_cost": "5.99",
            "estimated_days": 5,
            "is_active": True,
        }
        method_response = await integration_client.post("/api/v1/shipping/methods", json=method_payload)
        method_id = method_response.json()["id"]

        shipment_payload = {
            "order_id": "12345678-1234-5678-1234-567812345678",
            "user_id": "87654321-4321-8765-4321-876543218765",
            "user_email": "test@example.com",
            "method_id": method_id,
            "destination": {
                "street": "123 Main St",
                "city": "Toronto",
                "province": "ON",
                "postal_code": "M5V 1K4",
            },
        }
        create_response = await integration_client.post("/api/v1/shipments", json=shipment_payload)
        shipment_id = create_response.json()["id"]

        update_response = await integration_client.patch(
            f"/api/v1/shipments/{shipment_id}",
            json={"status": "shipped", "tracking_number": "TRACK123"},
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["status"] == "shipped"
        assert updated["tracking_number"] == "TRACK123"
