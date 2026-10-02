"""
Drive a CJ sandbox order through shipping, for end-to-end tests.

A sandbox order (created with CJ_DROPSHIPPING_SANDBOX on) never ships for
real, so its later life has to be played by hand through CJ's sandbox API.
Run through dev.sh, with our own order id (the one the storefront shows):

    ./local/dev.sh cj-sandbox status  <order_id>
    ./local/dev.sh cj-sandbox ship    <order_id> [--tracking SBX123]
    ./local/dev.sh cj-sandbox deliver <order_id>
    ./local/dev.sh cj-sandbox poll    <order_id>

``ship`` and ``deliver`` then run one tracking poll for the order, so the
shipped / delivered events (and the customer emails) follow at once instead
of on the poller's next pass.

Only orders recorded as sandbox orders are touched: CJ itself refuses these
calls for a real order, and this tool refuses before asking.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import update

from database_layer.cj_order_attempt_repository import CJOrderAttemptRepository
from models.cj_order_attempt_models import CJOrderAttempt
from resources import create_database_manager, logger, settings
from service_layer.cj_api_client import CJDropshippingAPIClient, CJDropshippingAPIError
from service_layer.cj_order_tracking_service import CJOrderTrackingService
from shared.managers.database_session_manager import DatabaseSessionManager

# CJ allows one request per second per account; back-to-back calls get a 429.
CJ_CALL_INTERVAL_SECONDS = 1.1

# CJ's sandbox status codes. They only move forward, one step at a time.
UNSHIPPED, SHIPPED, COMPLETED = 400, 500, 600


class SandboxOrderError(Exception):
    """The order cannot be driven: unknown, not a sandbox order, or not paid yet."""


@dataclass(frozen=True)
class SandboxOrder:
    order_id: UUID
    cj_order_number: str
    attempt_status: str


class CJSandboxDriver:
    """Plays CJ's part for one sandbox order: status steps, tracking number, a poll."""

    def __init__(self, database: DatabaseSessionManager, api_client: CJDropshippingAPIClient) -> None:
        self._database = database
        self._cj = api_client

    async def load(self, order_id: UUID) -> SandboxOrder:
        async with self._database.transaction() as session:
            attempt = await CJOrderAttemptRepository(session).get_by_field("order_id", order_id)
        if attempt is None:
            raise SandboxOrderError(f"No CJ order is recorded for order {order_id}")
        if not attempt.is_sandbox:
            raise SandboxOrderError(
                f"Order {order_id} is a real CJ order, not a sandbox one: refusing to touch it"
            )
        if not attempt.cj_order_number:
            raise SandboxOrderError(f"Order {order_id} has no CJ order number yet (status {attempt.status})")
        return SandboxOrder(order_id, attempt.cj_order_number, attempt.status)

    async def status(self, order: SandboxOrder) -> dict[str, str | None]:
        data = (await self._cj.get_order_detail(order.cj_order_number)).get("data") or {}
        if isinstance(data, list):
            data = data[0] if data else {}
        return {
            "order_id": str(order.order_id),
            "cj_order_number": order.cj_order_number,
            "our_status": order.attempt_status,
            "cj_status": data.get("orderStatus"),
            "tracking_number": data.get("trackNumber"),
            "is_sandbox": str(data.get("isSandbox")),
        }

    async def ship(self, order: SandboxOrder, tracking_number: str) -> None:
        """Tracking number first, then shipped: the poller needs both to announce it."""
        await self._cj.sandbox_update_track_number(order.cj_order_number, tracking_number)
        await asyncio.sleep(CJ_CALL_INTERVAL_SECONDS)
        await self._advance_to(order, SHIPPED)

    async def deliver(self, order: SandboxOrder) -> None:
        await self._advance_to(order, COMPLETED)

    async def poll(self, order: SandboxOrder) -> dict[str, int]:
        """Make the order due now and run one tracking pass."""
        await asyncio.sleep(CJ_CALL_INTERVAL_SECONDS)  # usually right after a status change
        async with self._database.transaction() as session:
            await session.execute(
                update(CJOrderAttempt)
                .where(CJOrderAttempt.order_id == order.order_id)
                .values(last_polled_at=None)
            )
        report = await CJOrderTrackingService(
            settings=settings, database=self._database, api_client=self._cj, logger=logger
        ).poll_open_orders()
        return report.as_dict()

    async def _advance_to(self, order: SandboxOrder, target: int) -> None:
        """
        Step through every status up to ``target``.

        CJ refuses a step the order has already passed, and this tool cannot
        read the sandbox's numeric status back, so an earlier step that fails
        is reported and skipped; only a failed final step is an error.
        """
        for index, step in enumerate((UNSHIPPED, SHIPPED, COMPLETED)):
            if step > target:
                break
            if index:
                await asyncio.sleep(CJ_CALL_INTERVAL_SECONDS)
            try:
                await self._cj.sandbox_update_status(order.cj_order_number, step)
                print(f"  CJ status -> {step}")
            except CJDropshippingAPIError as exc:
                if step == target:
                    raise
                print(f"  CJ status {step} skipped ({exc})")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dev.sh cj-sandbox", description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("action", choices=["status", "ship", "deliver", "poll"])
    parser.add_argument("order_id", type=UUID, help="our order id, as the storefront shows it")
    parser.add_argument("--tracking", help="tracking number to give the parcel (ship only)")
    parser.add_argument("--no-poll", action="store_true", help="do not run a tracking poll afterwards")
    return parser


async def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    # A CLI prints its own results: no SQL echo, whatever DEBUG_MODE says.
    database = create_database_manager(settings.model_copy(update={"DEBUG_MODE": False}))
    api_client = CJDropshippingAPIClient(settings)
    driver = CJSandboxDriver(database, api_client)
    try:
        order = await driver.load(args.order_id)
        if args.action == "status":
            for key, value in (await driver.status(order)).items():
                print(f"  {key:16} {value}")
            return 0
        if args.action == "ship":
            tracking = args.tracking or f"SBX{order.order_id.hex[:12].upper()}"
            await driver.ship(order, tracking)
            print(f"  tracking number {tracking}")
        elif args.action == "deliver":
            await driver.deliver(order)
        if args.action == "poll" or not args.no_poll:
            print(f"  tracking poll: {await driver.poll(order)}")
        return 0
    except (SandboxOrderError, CJDropshippingAPIError) as exc:
        print(f"cj-sandbox: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            await api_client.close()
        finally:
            await database.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
