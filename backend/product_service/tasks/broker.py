from taskiq_aio_pika import AioPikaBroker, Exchange, Queue
from aio_pika.abc import ExchangeType as AioPikaExchangeType
from taskiq_redis import RedisAsyncResultBackend

from shared.shared_instances import settings


# TaskiQ broker for product-service background tasks.
#
# Uses the same RabbitMQ cluster as the rest of the app (RABBITMQ_BROKER_URL)
# with a dedicated TOPIC exchange + queue pair so image-generation tasks are
# isolated from the FastStream notification queues.
#
# Results are stored in the product-service Redis DB with a namespaced prefix
# so they don't collide with HTTP response cache keys.
taskiq_broker = AioPikaBroker(
    url=settings.RABBITMQ_BROKER_URL,
    exchange=Exchange(
        name="taskiq.product.exchange",
        durable=True,
        declare=True,
        auto_delete=False,
        type=AioPikaExchangeType.TOPIC,
    ),
    task_queues=[
        Queue(
            name="taskiq.product.queue",
            durable=True,
            declare=True,
            auto_delete=False,
        )
    ],
    delay_queue=Queue(
        name="taskiq.product.delay.queue",
        durable=True,
        declare=True,
        auto_delete=False,
    ),
).with_result_backend(
    RedisAsyncResultBackend(
        redis_url=settings.PRODUCT_SERVICE_REDIS_URL,
        prefix_str=f"{settings.PRODUCT_SERVICE_REDIS_PREFIX}:taskiq",
    )
)
