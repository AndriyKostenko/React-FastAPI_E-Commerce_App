"""Unit tests for notification_service HTTP routes (all services mocked)."""
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from exceptions.notification_exceptions import (
    NotificationNotFoundError,
    NotificationAccessDeniedError,
)
from tests.constants import TEST_NOTIFICATION_ID, TEST_USER_ID, TEST_API


class TestGetUserNotificationsRoute:
    async def test_returns_200_with_list(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.get(
            f"{TEST_API}/notifications/users/{TEST_USER_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

    async def test_returns_200_with_is_read_filter(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.get(
            f"{TEST_API}/notifications/users/{TEST_USER_ID}?is_read=false"
        )
        assert response.status_code == 200

    async def test_returns_200_with_type_filter(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.get(
            f"{TEST_API}/notifications/users/{TEST_USER_ID}?notification_type=user.registered"
        )
        assert response.status_code == 200


class TestGetUnreadCountRoute:
    async def test_returns_200_with_count(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.get(
            f"{TEST_API}/notifications/users/{TEST_USER_ID}/unread-count"
        )
        assert response.status_code == 200
        data = response.json()
        assert "unread_count" in data
        assert data["unread_count"] == 3
        assert data["user_id"] == str(TEST_USER_ID)


class TestMarkNotificationAsReadRoute:
    async def test_returns_200_on_success(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.patch(
            f"{TEST_API}/notifications/{TEST_NOTIFICATION_ID}/read"
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    async def test_returns_404_when_not_found(
        self,
        client_for_unit_testing: AsyncClient,
        mock_route_notification_service: MagicMock,
    ):
        mock_route_notification_service.mark_as_read.side_effect = NotificationNotFoundError()

        response = await client_for_unit_testing.patch(
            f"{TEST_API}/notifications/{uuid4()}/read"
        )
        assert response.status_code == 404

    async def test_returns_403_when_access_denied(
        self,
        client_for_unit_testing: AsyncClient,
        mock_route_notification_service: MagicMock,
    ):
        mock_route_notification_service.mark_as_read.side_effect = NotificationAccessDeniedError()

        response = await client_for_unit_testing.patch(
            f"{TEST_API}/notifications/{TEST_NOTIFICATION_ID}/read"
        )
        assert response.status_code == 403


class TestMarkAllAsReadRoute:
    async def test_returns_200_with_updated_count(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.patch(
            f"{TEST_API}/notifications/users/{TEST_USER_ID}/read-all"
        )
        assert response.status_code == 200
        data = response.json()
        assert "updated" in data


class TestDeleteNotificationRoute:
    async def test_returns_204_on_success(self, client_for_unit_testing: AsyncClient):
        response = await client_for_unit_testing.delete(
            f"{TEST_API}/notifications/{TEST_NOTIFICATION_ID}"
        )
        assert response.status_code == 204

    async def test_returns_404_when_not_found(
        self,
        client_for_unit_testing: AsyncClient,
        mock_route_notification_service: MagicMock,
    ):
        mock_route_notification_service.delete_notification.side_effect = NotificationNotFoundError()

        response = await client_for_unit_testing.delete(
            f"{TEST_API}/notifications/{uuid4()}"
        )
        assert response.status_code == 404

    async def test_returns_403_when_access_denied(
        self,
        client_for_unit_testing: AsyncClient,
        mock_route_notification_service: MagicMock,
    ):
        mock_route_notification_service.delete_notification.side_effect = NotificationAccessDeniedError()

        response = await client_for_unit_testing.delete(
            f"{TEST_API}/notifications/{TEST_NOTIFICATION_ID}"
        )
        assert response.status_code == 403
