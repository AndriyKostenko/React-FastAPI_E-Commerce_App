"""
Integration tests for notification_service routes using the real test PostgreSQL database.

All tests use the `integration_client` fixture which:
  - creates all tables (idempotent via init_db)
  - provides a real AsyncClient wired to the test database
  - truncates all tables after each test function

Tests cover the full request-through-DB lifecycle.
"""
import pytest
from httpx import AsyncClient

from shared.shared_instances import test_notification_service_database_session_manager
from service_layer.notification_service import NotificationService
from database_layer.notification_repository import NotificationRepository
from tests.constants import TEST_USER_ID, TEST_MESSAGE, TEST_NOTIFICATION_TYPE, TEST_API


async def _create_notification(
    *,
    user_id=TEST_USER_ID,
    message=TEST_MESSAGE,
    notification_type=TEST_NOTIFICATION_TYPE,
):
    """Helper: persist a notification directly via the service layer."""
    async with test_notification_service_database_session_manager.transaction() as session:
        svc = NotificationService(repository=NotificationRepository(session=session))
        result = await svc.save_notification(
            message=message,
            notification_type=notification_type,
            user_id=user_id,
        )
    return result


# ---------------------------------------------------------------------------
# GET /notifications/users/{user_id}
# ---------------------------------------------------------------------------

class TestGetUserNotificationsIntegration:
    async def test_returns_list_of_notifications(self, integration_client: AsyncClient):
        await _create_notification()
        await _create_notification(message="Second notification")

        response = await integration_client.get(
            f"{TEST_API}/notifications/users/{TEST_USER_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    async def test_filter_by_is_read_false(self, integration_client: AsyncClient):
        await _create_notification()

        response = await integration_client.get(
            f"{TEST_API}/notifications/users/{TEST_USER_ID}?is_read=false"
        )
        assert response.status_code == 200
        data = response.json()
        assert all(n["is_read"] is False for n in data)

    async def test_empty_list_for_user_without_notifications(
        self, integration_client: AsyncClient
    ):
        from uuid import uuid4
        response = await integration_client.get(
            f"{TEST_API}/notifications/users/{uuid4()}"
        )
        assert response.status_code == 200
        assert response.json() == []


# ---------------------------------------------------------------------------
# GET /notifications/users/{user_id}/unread-count
# ---------------------------------------------------------------------------

class TestGetUnreadCountIntegration:
    async def test_returns_correct_unread_count(self, integration_client: AsyncClient):
        await _create_notification()
        await _create_notification(message="Another unread")

        response = await integration_client.get(
            f"{TEST_API}/notifications/users/{TEST_USER_ID}/unread-count"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["unread_count"] == 2
        assert data["user_id"] == str(TEST_USER_ID)

    async def test_returns_zero_when_no_notifications(self, integration_client: AsyncClient):
        response = await integration_client.get(
            f"{TEST_API}/notifications/users/{TEST_USER_ID}/unread-count"
        )
        assert response.status_code == 200
        assert response.json()["unread_count"] == 0


# ---------------------------------------------------------------------------
# PATCH /notifications/{id}/read
# ---------------------------------------------------------------------------

class TestMarkAsReadIntegration:
    async def test_marks_single_notification_as_read(self, integration_client: AsyncClient):
        notif = await _create_notification()
        notif_id = notif.id

        response = await integration_client.patch(
            f"{TEST_API}/notifications/{notif_id}/read"
        )
        assert response.status_code == 200
        assert response.json()["is_read"] is True

    async def test_returns_404_for_nonexistent_id(self, integration_client: AsyncClient):
        from uuid import uuid4
        response = await integration_client.patch(
            f"{TEST_API}/notifications/{uuid4()}/read"
        )
        assert response.status_code == 404

    async def test_unread_count_decreases_after_mark_as_read(
        self, integration_client: AsyncClient
    ):
        notif = await _create_notification()
        await _create_notification(message="Another notification")

        await integration_client.patch(f"{TEST_API}/notifications/{notif.id}/read")

        response = await integration_client.get(
            f"{TEST_API}/notifications/users/{TEST_USER_ID}/unread-count"
        )
        assert response.json()["unread_count"] == 1


# ---------------------------------------------------------------------------
# PATCH /notifications/users/{user_id}/read-all
# ---------------------------------------------------------------------------

class TestMarkAllAsReadIntegration:
    async def test_marks_all_as_read_and_returns_count(self, integration_client: AsyncClient):
        await _create_notification()
        await _create_notification(message="Another one")
        await _create_notification(message="Third one")

        response = await integration_client.patch(
            f"{TEST_API}/notifications/users/{TEST_USER_ID}/read-all"
        )
        assert response.status_code == 200
        assert response.json()["updated"] == 3

    async def test_unread_count_is_zero_after_mark_all_read(
        self, integration_client: AsyncClient
    ):
        await _create_notification()
        await _create_notification(message="Second notification")

        await integration_client.patch(
            f"{TEST_API}/notifications/users/{TEST_USER_ID}/read-all"
        )

        response = await integration_client.get(
            f"{TEST_API}/notifications/users/{TEST_USER_ID}/unread-count"
        )
        assert response.json()["unread_count"] == 0

    async def test_returns_zero_when_no_unread(self, integration_client: AsyncClient):
        response = await integration_client.patch(
            f"{TEST_API}/notifications/users/{TEST_USER_ID}/read-all"
        )
        assert response.status_code == 200
        assert response.json()["updated"] == 0


# ---------------------------------------------------------------------------
# DELETE /notifications/{id}
# ---------------------------------------------------------------------------

class TestDeleteNotificationIntegration:
    async def test_delete_returns_204(self, integration_client: AsyncClient):
        notif = await _create_notification()

        response = await integration_client.delete(
            f"{TEST_API}/notifications/{notif.id}"
        )
        assert response.status_code == 204

    async def test_deleted_notification_is_gone(self, integration_client: AsyncClient):
        notif = await _create_notification()

        await integration_client.delete(f"{TEST_API}/notifications/{notif.id}")

        get_response = await integration_client.get(
            f"{TEST_API}/notifications/users/{TEST_USER_ID}"
        )
        ids_remaining = [n["id"] for n in get_response.json()]
        assert str(notif.id) not in ids_remaining

    async def test_delete_nonexistent_returns_404(self, integration_client: AsyncClient):
        from uuid import uuid4
        response = await integration_client.delete(
            f"{TEST_API}/notifications/{uuid4()}"
        )
        assert response.status_code == 404
