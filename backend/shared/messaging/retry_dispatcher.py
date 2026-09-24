"""Runs a message handler, retrying transient failures with backoff."""

from collections.abc import Awaitable, Callable
from logging import Logger

from faststream.rabbit import RabbitBroker
from faststream.rabbit.message import RabbitMessage
from orjson import JSONDecodeError
from pydantic import ValidationError

from shared.messaging.resilient_queue import ResilientQueue


RETRY_ATTEMPT_HEADER = "x-retry-attempt"


class PermanentMessageError(Exception):
    """
    Raised by a handler for a message that can never succeed (unknown order,
    impossible state), so it goes straight to the dead-letter queue instead of
    being retried.
    """


class RetryDispatcher:
    """
    Wraps a subscriber's handler so a failure is retried, not lost.

    FastStream's RabbitMQ default is ``REJECT_ON_ERROR``: a handler that raises
    has its message rejected without requeue, i.e. dead-lettered at once. So:

    - success -> the message is acked as usual;
    - transient failure with retries left -> a copy is published to the next
      retry queue and the original is acked; the copy comes back after the delay;
    - permanent failure, or retries exhausted -> the error is re-raised and
      FastStream's reject dead-letters the message into the queue's DLQ.

    Handlers must stay idempotent: a crash between publishing the retry and
    acking the original delivers the message twice. Every consumer here already
    guards with an idempotency claim that it releases on failure.
    """

    # Failures that no amount of waiting fixes: the payload itself is wrong.
    _PERMANENT_ERRORS: tuple[type[Exception], ...] = (
        PermanentMessageError,
        ValidationError,
        JSONDecodeError,
    )

    def __init__(self, broker: RabbitBroker, logger: Logger) -> None:
        self._broker = broker
        self._logger = logger

    async def dispatch(
        self,
        queue: ResilientQueue,
        message: RabbitMessage,
        handle: Callable[[], Awaitable[None]],
    ) -> None:
        try:
            await handle()
        except self._PERMANENT_ERRORS as error:
            self._logger.error(
                "Message %s on %s failed permanently, dead-lettering: %s",
                message.message_id, queue.name, error,
            )
            raise
        except Exception as error:
            attempt = self._attempt_of(message)
            if attempt >= queue.retry_schedule.max_retries:
                self._logger.error(
                    "Message %s on %s failed after %s retries, dead-lettering: %s",
                    message.message_id, queue.name, attempt, error,
                )
                raise
            await self._schedule_retry(queue, message, attempt)
            self._logger.warning(
                "Message %s on %s failed (retry %s/%s in %sms): %s",
                message.message_id,
                queue.name,
                attempt + 1,
                queue.retry_schedule.max_retries,
                queue.retry_schedule.delay_for(attempt),
                error,
            )

    @staticmethod
    def _attempt_of(message: RabbitMessage) -> int:
        """How many retries this message has already had (0 on first delivery)."""
        raw = message.headers.get(RETRY_ATTEMPT_HEADER, 0)
        try:
            return max(int(raw), 0)
        except (TypeError, ValueError):
            return 0

    async def _schedule_retry(
        self, queue: ResilientQueue, message: RabbitMessage, attempt: int
    ) -> None:
        # The raw body and properties are forwarded untouched so the retried
        # message is byte-identical to the original apart from the counter.
        # If this publish fails the exception propagates and the original is
        # dead-lettered — parked, never lost.
        headers = dict(message.headers)
        headers[RETRY_ATTEMPT_HEADER] = attempt + 1
        await self._broker.publish(
            message.body,
            queue=queue.retry_queue_name(attempt),
            headers=headers,
            content_type=message.content_type,
            correlation_id=message.correlation_id,
            message_id=message.message_id,
            persist=True,
        )
