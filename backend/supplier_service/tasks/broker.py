from taskiq_aio_pika import AioPikaBroker, Exchange, Queue
from aio_pika.abc import ExchangeType as AioPikaExchangeType
from taskiq_redis import RedisAsyncResultBackend

from shared.shared_instances import settings


taskiq_broker = AioPikaBroker(
    url=settings.RABBITMQ_BROKER_URL,
    exchange=Exchange(
        name="taskiq.supplier.exchange",
        durable=True,
        declare=True,
        auto_delete=False,
        type=AioPikaExchangeType.TOPIC,
    ),
    task_queues=[
        Queue(
            name="taskiq.supplier.queue",
            durable=True,
            declare=True,
            auto_delete=False,
        )
    ],
    delay_queue=Queue(
        name="taskiq.supplier.delay.queue",
        durable=True,
        declare=True,
        auto_delete=False,
    ),
).with_result_backend(
    RedisAsyncResultBackend(
        redis_url=settings.SUPPLIER_SERVICE_REDIS_URL,
        prefix_str=f"{settings.SUPPLIER_SERVICE_REDIS_PREFIX}:taskiq",
    )
)
