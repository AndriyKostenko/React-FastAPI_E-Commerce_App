"""Unit tests for NotificationService business logic (all DB/IO replaced with mocks)."""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from service_layer.notification_service import NotificationService
from shared.schemas.notifications_schemas import NotificationInfo, NotificationsFilterParams
from exceptions.notification_exceptions import (
    NotificationNotFoundError,
    NotificationAccessDeniedError,
)
from tests.constants import (
    TEST_NOTIFICATION_ID, TEST_USER_ID, TEST_MESSAGE, TEST_NOTIFICATION_TYPE, TEST_DATETIME,
)


def _make_notification_info(**overrides) -> NotificationInfo:
    data = dict(
        id=TEST_NOTIFICATION_ID,
        user_id=TEST_USER_ID,
        message=TEST_MESSAGE,
        notification_type=TEST_NOTIFICATION_TYPE,
        is_read=False,
        date_created=TEST_DATETIME,
        date_updated=None,
    )
    data.update(overrides)
    return NotificationInfo(**data)


# ---------------------------------------------------------------------------
# get_user_notifications
# ---------------------------------------------------------------------------

class TestGetUserNotifications:
    async def test_returns_list_of_notification_info(
        self, notification_service_unit: NotificationService, mock_notification_orm: MagicMock
    ):
        svc = notification_service_unit
        svc.repository.get_by_user_id = AsyncMock(return_value=[mock_notification_orm])

        params = NotificationsFilterParams()
        result = await svc.get_user_notifications(user_id=TEST_USER_ID, params=params)

        assert len(result) == 1
        assert isinstance(result[0], NotificationInfo)
        assert result[0].user_id == TEST_USER_ID

    async def test_calls_repo_with_correct_user_id(
        self, notification_service_unit: NotificationService, mock_notification_orm: MagicMock
    ):
        svc = notification_service_unit
        svc.repository.get_by_user_id = AsyncMock(return_value=[mock_notification_orm])

        await svc.get_user_notifications(user_id=TEST_USER_ID, params=NotificationsFilterParams())

        call_kwargs = svc.repository.get_by_user_id.call_args.kwargs
        assert call_kwargs["user_id"] == TEST_USER_ID

    async def test_passes_is_read_filter(
        self, notification_service_unit: NotificationService, mock_notification_orm: MagicMock
    ):
        svc = notification_service_unit
        svc.repository.get_by_user_id = AsyncMock(return_value=[mock_notification_orm])

        params = NotificationsFilterParams(is_read=False)
        await svc.get_user_notifications(user_id=TEST_USER_ID, params=params)

        call_kwargs = svc.repository.get_by_user_id.call_args.kwargs
        assert call_kwargs["filters"].get("is_read") is False

    async def test_passes_notification_type_filter(
        self, notification_service_unit: NotificationService, mock_notification_orm: MagicMock
    ):
        svc = notification_service_unit
        svc.repository.get_by_user_id = AsyncMock(return_value=[mock_notification_orm])

        params = NotificationsFilterParams(notification_type="user.registered")
        await svc.get_user_notifications(user_id=TEST_USER_ID, params=params)

        call_kwargs = svc.repository.get_by_user_id.call_args.kwargs
        assert call_kwargs["filters"].get("notification_type") == "user.registered"

    async def test_returns_empty_list_when_none(
        self, notification_service_unit: NotificationService
    ):
        svc = notification_service_unit
        svc.repository.get_by_user_id = AsyncMock(return_value=[])

        result = await svc.get_user_notifications(
            user_id=TEST_USER_ID, params=NotificationsFilterParams()
        )
        assert result == []


# ---------------------------------------------------------------------------
# get_notification_by_id
# ---------------------------------------------------------------------------

class TestGetNotificationById:
    async def test_returns_notification_info(
        self, notification_service_unit: NotificationService, mock_notification_orm: MagicMock
    ):
        svc = notification_service_unit
        svc.repository.get_by_id = AsyncMock(return_value=mock_notification_orm)

        result = await svc.get_notification_by_id(TEST_NOTIFICATION_ID)

        assert isinstance(result, NotificationInfo)
        assert result.id == TEST_NOTIFICATION_ID

    async def test_not_found_raises(self, notification_service_unit: NotificationService):
        svc = notification_service_unit
        svc.repository.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotificationNotFoundError):
            await svc.get_notification_by_id(TEST_NOTIFICATION_ID)

    async def test_wrong_user_id_raises_access_denied(
        self, notification_service_unit: NotificationService, mock_notification_orm: MagicMock
    ):
        svc = notification_service_unit
        mock_notification_orm.user_id = TEST_USER_ID
        svc.repository.get_by_id = AsyncMock(return_value=mock_notification_orm)

        different_user = uuid4()
        with pytest.raises(NotificationAccessDeniedError):
            await svc.get_notification_by_id(TEST_NOTIFICATION_ID, requesting_user_id=different_user)

    async def test_correct_user_id_succeeds(
        self, notification_service_unit: NotificationService, mock_notification_orm: MagicMock
    ):
        svc = notification_service_unit
        mock_notification_orm.user_id = TEST_USER_ID
        svc.repository.get_by_id = AsyncMock(return_value=mock_notification_orm)

        result = await svc.get_notification_by_id(
            TEST_NOTIFICATION_ID, requesting_user_id=TEST_USER_ID
        )
        assert result.id == TEST_NOTIFICATION_ID


# ---------------------------------------------------------------------------
# get_unread_count
# ---------------------------------------------------------------------------

class TestGetUnreadCount:
    async def test_returns_integer_count(self, notification_service_unit: NotificationService):
        svc = notification_service_unit
        svc.repository.get_unread_count = AsyncMock(return_value=7)

        result = await svc.get_unread_count(TEST_USER_ID)

        assert result == 7
        svc.repository.get_unread_count.assert_awaited_once_with(TEST_USER_ID)

    async def test_returns_zero_when_none_unread(
        self, notification_service_unit: NotificationService
    ):
        svc = notification_service_unit
        svc.repository.get_unread_count = AsyncMock(return_value=0)

        result = await svc.get_unread_count(TEST_USER_ID)
        assert result == 0


# ---------------------------------------------------------------------------
# mark_as_read
# ---------------------------------------------------------------------------

class TestMarkAsRead:
    async def test_mark_as_read_sets_is_read_true(
        self, notification_service_unit: NotificationService, mock_notification_orm: MagicMock
    ):
        svc = notification_service_unit
        mock_notification_orm.is_read = False
        updated_orm = MagicMock()
        updated_orm.id = TEST_NOTIFICATION_ID
        updated_orm.user_id = TEST_USER_ID
        updated_orm.message = TEST_MESSAGE
        updated_orm.notification_type = TEST_NOTIFICATION_TYPE
        updated_orm.is_read = True
        updated_orm.date_created = TEST_DATETIME
        updated_orm.date_updated = None

        svc.repository.get_by_id = AsyncMock(return_value=mock_notification_orm)
        svc.repository.update = AsyncMock(return_value=updated_orm)

        result = await svc.mark_as_read(TEST_NOTIFICATION_ID)

        assert mock_notification_orm.is_read is True
        assert isinstance(result, NotificationInfo)
        assert result.is_read is True
        svc.repository.update.assert_awaited_once_with(mock_notification_orm)

    async def test_mark_as_read_not_found_raises(
        self, notification_service_unit: NotificationService
    ):
        svc = notification_service_unit
        svc.repository.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotificationNotFoundError):
            await svc.mark_as_read(TEST_NOTIFICATION_ID)

    async def test_mark_as_read_wrong_user_raises_access_denied(
        self, notification_service_unit: NotificationService, mock_notification_orm: MagicMock
    ):
        svc = notification_service_unit
        mock_notification_orm.user_id = TEST_USER_ID
        svc.repository.get_by_id = AsyncMock(return_value=mock_notification_orm)

        with pytest.raises(NotificationAccessDeniedError):
            await svc.mark_as_read(TEST_NOTIFICATION_ID, requesting_user_id=uuid4())


# ---------------------------------------------------------------------------
# mark_all_as_read
# ---------------------------------------------------------------------------

class TestMarkAllAsRead:
    async def test_returns_updated_count(self, notification_service_unit: NotificationService):
        svc = notification_service_unit
        svc.repository.mark_all_as_read = AsyncMock(return_value=4)

        result = await svc.mark_all_as_read(TEST_USER_ID)

        assert result == {"updated": 4}
        svc.repository.mark_all_as_read.assert_awaited_once_with(TEST_USER_ID)

    async def test_returns_zero_when_already_all_read(
        self, notification_service_unit: NotificationService
    ):
        svc = notification_service_unit
        svc.repository.mark_all_as_read = AsyncMock(return_value=0)

        result = await svc.mark_all_as_read(TEST_USER_ID)
        assert result == {"updated": 0}


# ---------------------------------------------------------------------------
# delete_notification
# ---------------------------------------------------------------------------

class TestDeleteNotification:
    async def test_delete_calls_repo_delete(
        self, notification_service_unit: NotificationService, mock_notification_orm: MagicMock
    ):
        svc = notification_service_unit
        svc.repository.get_by_id = AsyncMock(return_value=mock_notification_orm)
        svc.repository.delete = AsyncMock(return_value=None)

        await svc.delete_notification(TEST_NOTIFICATION_ID)

        svc.repository.delete.assert_awaited_once_with(mock_notification_orm)

    async def test_delete_not_found_raises(self, notification_service_unit: NotificationService):
        svc = notification_service_unit
        svc.repository.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotificationNotFoundError):
            await svc.delete_notification(TEST_NOTIFICATION_ID)

    async def test_delete_wrong_user_raises_access_denied(
        self, notification_service_unit: NotificationService, mock_notification_orm: MagicMock
    ):
        svc = notification_service_unit
        mock_notification_orm.user_id = TEST_USER_ID
        svc.repository.get_by_id = AsyncMock(return_value=mock_notification_orm)

        with pytest.raises(NotificationAccessDeniedError):
            await svc.delete_notification(TEST_NOTIFICATION_ID, requesting_user_id=uuid4())


# ---------------------------------------------------------------------------
# save_notification
# ---------------------------------------------------------------------------

class TestSaveNotification:
    async def test_save_notification_returns_notification_info(
        self, notification_service_unit: NotificationService, mock_notification_orm: MagicMock
    ):
        svc = notification_service_unit
        svc.repository.create = AsyncMock(return_value=mock_notification_orm)

        result = await svc.save_notification(
            message=TEST_MESSAGE,
            notification_type=TEST_NOTIFICATION_TYPE,
            user_id=TEST_USER_ID,
        )

        assert isinstance(result, NotificationInfo)
        assert result.message == TEST_MESSAGE
        assert result.notification_type == TEST_NOTIFICATION_TYPE
        svc.repository.create.assert_awaited_once()

    async def test_save_notification_without_user_id(
        self, notification_service_unit: NotificationService, mock_notification_orm: MagicMock
    ):
        svc = notification_service_unit
        mock_notification_orm.user_id = None
        svc.repository.create = AsyncMock(return_value=mock_notification_orm)

        result = await svc.save_notification(
            message="System broadcast",
            notification_type="system",
            user_id=None,
        )
        assert isinstance(result, NotificationInfo)
