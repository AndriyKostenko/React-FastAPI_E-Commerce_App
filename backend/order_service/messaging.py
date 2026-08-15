"""RabbitMQ topology owned by order-service."""

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange

from shared.settings import Settings


order_exchange = RabbitExchange(
    name="order.events.exchange",
    durable=True,
    type=ExchangeType.TOPIC,
)
inventory_exchange = RabbitExchange(
    name="inventory.events.exchange",
    durable=True,
    type=ExchangeType.TOPIC,
)
payment_exchange = RabbitExchange(
    name="payment.events.exchange",
    durable=True,
    type=ExchangeType.TOPIC,
)
shipping_exchange = RabbitExchange(
    name="shipping.events.exchange",
    durable=True,
    type=ExchangeType.TOPIC,
)


def create_rabbitmq_broker(settings: Settings) -> RabbitBroker:
    """Create the broker owned by the current order-service process role."""
    return RabbitBroker(url=settings.RABBITMQ_BROKER_URL)
