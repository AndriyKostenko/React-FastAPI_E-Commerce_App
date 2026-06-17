"""
Unit tests for OutboxEventService.

The OutboxRepository is mocked so no live database is required.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

import pytest
from pydantic import BaseModel

from exceptions.outbox_event_exceptions import (
    OutboxEventCreatioError,
    OutboxEventNotFoundError,
    OutboxEventUpdateError,
)
from shared.models.outbox_events import OutboxEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _SamplePayload(BaseModel):
    message: str = "test payload"


def _make_outbox_orm(event_id=None) -> MagicMock:
    orm = MagicMock(spec=OutboxEvent)
    orm.id = event_id or uuid4()
    orm.event_type = "test.event"
    orm.payload = {"message": "test payload"}
    orm.processed = False
    orm.processed_at = None
    return orm


# ---------------------------------------------------------------------------
# add_outbox_event
# ---------------------------------------------------------------------------

class TestAddOutboxEvent:
    async def test_creates_event_successfully(
        self,
        mock_outbox_event_service,
        mock_outbox_repository: MagicMock,
    ) -> None:
        orm = _make_outbox_orm()
        mock_outbox_repository.create.return_value = orm

        await mock_outbox_event_service.add_outbox_event(
            event_type="test.event",
            payload=_SamplePayload(),
        )

        mock_outbox_repository.create.assert_awaited_once()
        call_arg = mock_outbox_repository.create.call_args[0][0]
        assert isinstance(call_arg, OutboxEvent)
        assert call_arg.event_type == "test.event"

    async def test_raises_when_create_returns_none(
        self,
        mock_outbox_event_service,
        mock_outbox_repository: MagicMock,
    ) -> None:
        mock_outbox_repository.create.return_value = None

        with pytest.raises(OutboxEventCreatioError):
            await mock_outbox_event_service.add_outbox_event(
                event_type="test.event",
                payload=_SamplePayload(),
            )


# ---------------------------------------------------------------------------
# get_unprocessed_events
# ---------------------------------------------------------------------------

class TestGetUnprocessedEvents:
    async def test_returns_unprocessed_event_list(
        self,
        mock_outbox_event_service,
        mock_outbox_repository: MagicMock,
    ) -> None:
        events = [_make_outbox_orm(), _make_outbox_orm()]
        mock_outbox_repository.get_many_by_field_with_lock.return_value = events

        result = await mock_outbox_event_service.get_unprocessed_events()

        assert len(result) == 2
        mock_outbox_repository.get_many_by_field_with_lock.assert_awaited_once_with(
            field_name="processed", value=False, limit=50
        )

    async def test_respects_custom_limit(
        self,
        mock_outbox_event_service,
        mock_outbox_repository: MagicMock,
    ) -> None:
        mock_outbox_repository.get_many_by_field_with_lock.return_value = [_make_outbox_orm()]

        await mock_outbox_event_service.get_unprocessed_events(limit=10)

        mock_outbox_repository.get_many_by_field_with_lock.assert_awaited_once_with(
            field_name="processed", value=False, limit=10
        )

    async def test_raises_when_no_unprocessed_events(
        self,
        mock_outbox_event_service,
        mock_outbox_repository: MagicMock,
    ) -> None:
        mock_outbox_repository.get_many_by_field_with_lock.return_value = []

        with pytest.raises(OutboxEventNotFoundError):
            await mock_outbox_event_service.get_unprocessed_events()


# ---------------------------------------------------------------------------
# mark_event_as_processed
# ---------------------------------------------------------------------------

class TestMarkEventAsProcessed:
    async def test_marks_event_processed_successfully(
        self,
        mock_outbox_event_service,
        mock_outbox_repository: MagicMock,
    ) -> None:
        event_id = uuid4()
        mock_outbox_repository.update_by_id.return_value = _make_outbox_orm(event_id)

        await mock_outbox_event_service.mark_event_as_processed(event_id)

        call_kwargs = mock_outbox_repository.update_by_id.call_args[1]
        assert call_kwargs["item_id"] == event_id
        assert call_kwargs["data"]["processed"] is True
        assert "processed_at" in call_kwargs["data"]

    async def test_raises_when_event_not_found(
        self,
        mock_outbox_event_service,
        mock_outbox_repository: MagicMock,
    ) -> None:
        mock_outbox_repository.update_by_id.return_value = None

        with pytest.raises(OutboxEventUpdateError):
            await mock_outbox_event_service.mark_event_as_processed(uuid4())
