from taskiq_aio_pika import AioPikaBroker, Exchange, Queue
from aio_pika.abc import ExchangeType as AioPikaExchangeType
from logging import getLogger

from taskiq_redis import RedisAsyncResultBackend
from shared.messaging.task_dead_letter import DeadLetteringRetryMiddleware
from shared.settings import get_settings

settings = get_settings()



# Taskiq task manager setup (service-owned configuratio)
# The AioPikaBroker is configured with the same RabbitMQ URL and defines a TOPIC exchange for notifications,
# along with a main queue and a delay queue for retrying failed tasks.
# The result backend is set to Redis, using a separate Redis URL and prefix for the notification service.
# This allows Taskiq to manage asynchronous tasks related to notifications,
# such as sending emails, with retry capabilities and result tracking.
# The notification_idempotency_service is also set up to ensure that events are processed idempotently,
# preventing duplicate notifications in case of retries or multiple event deliveries.
taskiq_broker = AioPikaBroker(url=settings.RABBITMQ_BROKER_URL,
                              exchange=Exchange(name="taskiq.notifications.exchange",
                                                durable=True,
                                                declare=True,
                                                auto_delete=False,
                                                type=AioPikaExchangeType.TOPIC),
                              task_queues=[Queue(name="taskiq.notifications.queue",
                                                 durable=True,
                                                 declare=True,
                                                 auto_delete=False)],
                              delay_queue=Queue(name="taskiq.notifications.delay.queue",
                                                durable=True,
                                                declare=True,
                                                auto_delete=False)
).with_result_backend(RedisAsyncResultBackend(redis_url=settings.NOTIFICATION_SERVICE_REDIS_RESULT_BACKEND_URL,
                                              prefix_str=settings.NOTIFICATION_SERVICE_REDIS_PREFIX)
).with_middlewares(
    # Every task here sends an email, so every task retries (with backoff and
    # jitter, 5 attempts); one that still fails is parked in the DLQ below
    # rather than lost. A duplicate email beats a missing order confirmation.
    DeadLetteringRetryMiddleware(
        dead_letter_queue_name="taskiq.notifications.dead_letter",
        logger=getLogger("notification-service"),
        default_retry_label=True,
    )
)
