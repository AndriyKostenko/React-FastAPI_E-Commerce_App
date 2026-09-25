"""
Move parked messages out of a dead-letter queue and back to work.

    python -m shared.messaging.dead_letter_replay <dlq> [--to <queue>] [--limit N]

Driven by ``./local/dev.sh dlq replay``. Replay only once the cause is fixed:
a message that still fails simply goes round its retries and parks again.
"""

import argparse
import asyncio
from dataclasses import dataclass, field
from logging import Logger, basicConfig, getLogger

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage

from shared.messaging.retry_dispatcher import RETRY_ATTEMPT_HEADER


# Stripped on replay so the message starts over with a full retry budget and
# without the history of the failures that parked it.
_RESET_HEADERS = frozenset({RETRY_ATTEMPT_HEADER, "x-death", "x-first-death-queue",
                            "x-first-death-reason", "x-first-death-exchange",
                            "x-last-death-queue", "x-last-death-reason", "x-last-death-exchange"})


@dataclass
class ReplayReport:
    replayed: dict[str, int] = field(default_factory=dict)  # target queue -> count
    skipped: int = 0  # no way to tell where they came from; left in the DLQ

    @property
    def total(self) -> int:
        return sum(self.replayed.values())


class DeadLetterReplayer:
    def __init__(self, broker_url: str, logger: Logger) -> None:
        self._broker_url = broker_url
        self._logger = logger

    async def replay(self, dead_letter_queue: str, *, to: str | None = None, limit: int | None = None) -> ReplayReport:
        """
        Republish up to ``limit`` parked messages to the queue each came from
        (or to ``to``), then remove them from the DLQ.

        Publish-then-ack: a crash in between leaves a copy in both places,
        never in neither. Every consumer is idempotent, so a duplicate is safe.
        """
        report = ReplayReport()
        connection = await aio_pika.connect_robust(self._broker_url)
        async with connection:
            channel = await connection.channel(publisher_confirms=True)
            queue = await channel.declare_queue(dead_letter_queue, passive=True)
            # Bounded by the count at the start, so a message that is put back
            # (no known origin) is not fetched again in the same run.
            pending = queue.declaration_result.message_count or 0
            if limit is not None:
                pending = min(pending, limit)
            for _ in range(pending):
                message = await queue.get(no_ack=False, fail=False)
                if message is None:
                    break
                target = to or self._origin_of(message, dead_letter_queue)
                if target is None:
                    await message.nack(requeue=True)
                    report.skipped += 1
                    continue
                await self._republish(channel, message, target)
                await message.ack()
                report.replayed[target] = report.replayed.get(target, 0) + 1
        self._logger.info("Replayed %s message(s) from %s: %s", report.total, dead_letter_queue, report.replayed)
        return report

    @staticmethod
    def _origin_of(message: AbstractIncomingMessage, dead_letter_queue: str) -> str | None:
        """
        The queue whose consumer rejected the message, from RabbitMQ's x-death
        record. Entries for our retry queues (reason "expired") are passed over:
        the message must go back to the queue that actually handles it.
        """
        deaths = (message.headers or {}).get("x-death")
        if not isinstance(deaths, list):
            return None
        for death in deaths:
            if isinstance(death, dict) and death.get("reason") == "rejected":
                queue = death.get("queue")
                if isinstance(queue, str) and queue != dead_letter_queue:
                    return queue
        return None

    @staticmethod
    async def _republish(channel: AbstractChannel, message: AbstractIncomingMessage, target: str) -> None:
        headers = {key: value for key, value in (message.headers or {}).items() if key not in _RESET_HEADERS}
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=message.body,
                headers=headers,
                content_type=message.content_type,
                content_encoding=message.content_encoding,
                correlation_id=message.correlation_id,
                message_id=message.message_id,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=target,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dead_letter_queue")
    parser.add_argument("--to", help="target queue, for messages with no x-death origin (taskiq's parked tasks)")
    parser.add_argument("--limit", type=int, help="replay at most this many")
    args = parser.parse_args()

    from shared.settings import get_settings  # deferred: only the CLI needs settings

    basicConfig(level="INFO", format="%(message)s")
    replayer = DeadLetterReplayer(get_settings().RABBITMQ_BROKER_URL, getLogger("dlq-replay"))
    report = asyncio.run(replayer.replay(args.dead_letter_queue, to=args.to, limit=args.limit))
    for target, count in report.replayed.items():
        print(f"  {count:>5}  -> {target}")
    print(f"replayed {report.total}, left in place {report.skipped}")
    if report.skipped:
        print("  (no x-death origin: pass --to <queue> to send those somewhere)")


if __name__ == "__main__":
    main()
