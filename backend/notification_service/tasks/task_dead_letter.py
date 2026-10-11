"""Retry failed taskiq tasks with backoff, then park them instead of losing them."""

from logging import Logger

from aio_pika import DeliveryMode, Message
from taskiq import TaskiqMessage, TaskiqResult
from taskiq.exceptions import NoResultError
from taskiq.middlewares import SmartRetryMiddleware
from taskiq_aio_pika import AioPikaBroker


TASK_NAME_HEADER = "x-task-name"
TASK_ID_HEADER = "x-task-id"
TASK_ERROR_HEADER = "x-task-error"
_MAX_ERROR_HEADER_LENGTH = 1000


class DeadLetteringRetryMiddleware(SmartRetryMiddleware):
    """
    ``SmartRetryMiddleware`` that parks a task once its retries are exhausted.

    taskiq acks a message once its result is saved — and a failure is a saved
    result — so a failed task never reaches RabbitMQ's dead-letter queue. Plain
    ``SmartRetryMiddleware`` only logs when it gives up, so the job (an email,
    say) is gone. This publishes the original task message to a queue no worker
    consumes, with the task name and error in its headers, for inspection and
    replay.

    Only tasks that opted into retries (``retry_on_error``) are parked: a task
    that did not ask to be retried is one whose failure is handled elsewhere
    (quota refunds, the next cron run).
    """

    def __init__(
        self,
        dead_letter_queue_name: str,
        logger: Logger,
        *,
        default_retry_count: int = 5,
        default_retry_label: bool = False,
        default_delay: float = 10,
        max_delay_exponent: float = 300,
    ) -> None:
        super().__init__(
            default_retry_count=default_retry_count,
            default_retry_label=default_retry_label,
            default_delay=default_delay,
            # delay * attempt, capped — 10s, 20s, 30s ... up to max_delay_exponent
            use_delay_exponent=True,
            max_delay_exponent=max_delay_exponent,
            # spreads out retries of a batch that failed together (SMTP outage)
            use_jitter=True,
        )
        self.dead_letter_queue_name = dead_letter_queue_name
        self._logger = logger

    async def on_error(
        self,
        message: TaskiqMessage,
        result: TaskiqResult[object],
        exception: BaseException,
    ) -> None:
        # Decide before the parent runs: when it schedules a retry it bumps
        # "_retries" in message.labels in place, so checking afterwards would
        # park a task that is in fact still being retried.
        exhausted = self._retries_exhausted(message, exception)
        await super().on_error(message, result, exception)
        if exhausted:
            await self._park(message, exception)

    def _retries_exhausted(self, message: TaskiqMessage, exception: BaseException) -> bool:
        """Mirror of the parent's decision: True exactly when it gave up instead of retrying."""
        if isinstance(exception, NoResultError) or not self.is_retry_on_error(message):
            return False
        if self.types_of_exceptions is not None and not isinstance(
            exception, tuple(self.types_of_exceptions)
        ):
            return False
        retries = int(message.labels.get("_retries", 0)) + 1
        max_retries = int(message.labels.get("max_retries", self.default_retry_count))
        return retries >= max_retries

    async def _park(self, message: TaskiqMessage, exception: BaseException) -> None:
        broker = self.broker
        if not isinstance(broker, AioPikaBroker) or broker.write_channel is None:
            self._logger.error(
                "Task %s (%s) exhausted its retries and could not be parked: no AMQP channel",
                message.task_name, message.task_id,
            )
            return
        # Declared lazily: idempotent, and it keeps the middleware independent
        # of the order in which the broker and its middlewares start up.
        await broker.write_channel.declare_queue(self.dead_letter_queue_name, durable=True)
        await broker.write_channel.default_exchange.publish(
            Message(
                body=broker.formatter.dumps(message).message,
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT,
                message_id=message.task_id,
                headers={
                    TASK_NAME_HEADER: message.task_name,
                    TASK_ID_HEADER: message.task_id,
                    TASK_ERROR_HEADER: repr(exception)[:_MAX_ERROR_HEADER_LENGTH],
                },
            ),
            routing_key=self.dead_letter_queue_name,
        )
        self._logger.error(
            "Task %s (%s) exhausted its retries; parked in %s: %r",
            message.task_name, message.task_id, self.dead_letter_queue_name, exception,
        )
