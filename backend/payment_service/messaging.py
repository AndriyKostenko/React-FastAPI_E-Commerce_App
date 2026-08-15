"""RabbitMQ topology owned by payment-service."""

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange

from shared.settings import Settings


payment_exchange = RabbitExchange(
    name="payment.events.exchange",
    durable=True,
    type=ExchangeType.TOPIC,
)
order_exchange = RabbitExchange(
    name="order.events.exchange",
    durable=True,
    type=ExchangeType.TOPIC,
)


def create_rabbitmq_broker(settings: Settings) -> RabbitBroker:
    """Create the broker owned by the current payment-service process role."""
    return RabbitBroker(url=settings.RABBITMQ_BROKER_URL)
