"""A consumer queue together with the retry and dead-letter queues that back it."""

from dataclasses import dataclass, field

from faststream.rabbit import RabbitQueue


DEAD_LETTER_EXCHANGE_NAME = "dlx"
# Publishing to the default exchange ("") delivers straight to the queue whose
# name equals the routing key, which is how a delayed retry finds its way home.
DEFAULT_EXCHANGE_NAME = ""


@dataclass(frozen=True, slots=True)
class RetrySchedule:
    """
    How long to wait before each redelivery of a failed message.

    One delay per retry: (5s, 30s, 120s) means three retries, so a message is
    handled at most four times before it is dead-lettered.
    """

    delays_ms: tuple[int, ...] = (5_000, 30_000, 120_000)

    def __post_init__(self) -> None:
        if any(delay <= 0 for delay in self.delays_ms):
            raise ValueError("Retry delays must be positive")

    @property
    def max_retries(self) -> int:
        return len(self.delays_ms)

    def delay_for(self, retry_number: int) -> int:
        """Delay before retry ``retry_number`` (0-based)."""
        return self.delays_ms[retry_number]


@dataclass(frozen=True, slots=True)
class ResilientQueue:
    """
    A durable consumer queue whose failures are retried with backoff and then
    parked in a dead-letter queue instead of being dropped.

    Topology for a queue ``orders`` with dead-letter key ``orders.dlq``::

        orders                 --reject-->  dlx --orders.dlq-->  orders.dlq
        orders.retry.5s  (TTL 5s)   --expire-->  "" --orders-->  orders
        orders.retry.30s (TTL 30s)  --expire-->  "" --orders-->  orders

    The main queue's arguments are exactly the ones every service declared
    before this class existed: RabbitMQ refuses to redeclare a queue with
    different arguments, so changing them would stop the consumer starting.
    """

    name: str
    routing_key: str
    dead_letter_key: str
    retry_schedule: RetrySchedule = field(default_factory=RetrySchedule)

    @property
    def queue(self) -> RabbitQueue:
        """The queue the subscriber consumes from."""
        return RabbitQueue(
            name=self.name,
            durable=True,
            routing_key=self.routing_key,
            arguments={
                "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE_NAME,
                "x-dead-letter-routing-key": self.dead_letter_key,
            },
        )

    @property
    def dead_letter_queue(self) -> RabbitQueue:
        """Where messages land once retries are exhausted or the failure is permanent."""
        return RabbitQueue(name=self.dead_letter_key, durable=True)

    def retry_queue_name(self, retry_number: int) -> str:
        delay_ms = self.retry_schedule.delay_for(retry_number)
        suffix = f"{delay_ms // 1000}s" if delay_ms % 1000 == 0 else f"{delay_ms}ms"
        return f"{self.name}.retry.{suffix}"

    @property
    def retry_queues(self) -> tuple[RabbitQueue, ...]:
        """
        One holding queue per delay. Nothing consumes them: a message waits out
        the queue's TTL and is then dead-lettered back to the main queue.

        A queue per delay, rather than one queue with per-message expiry,
        because RabbitMQ only expires messages at the head of a queue — a 120s
        message would hold back a 5s one queued behind it.
        """
        return tuple(
            RabbitQueue(
                name=self.retry_queue_name(retry_number),
                durable=True,
                arguments={
                    "x-message-ttl": delay_ms,
                    "x-dead-letter-exchange": DEFAULT_EXCHANGE_NAME,
                    "x-dead-letter-routing-key": self.name,
                },
            )
            for retry_number, delay_ms in enumerate(self.retry_schedule.delays_ms)
        )
