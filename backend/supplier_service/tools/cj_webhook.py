"""
Point CJ's stock pushes at us, and keep the products we sell subscribed.

Run through dev.sh, which gives it supplier-service's Vault identity:

    ./local/dev.sh cj-webhook enable  <public base url>   # register, then subscribe
    ./local/dev.sh cj-webhook disable <public base url>   # stop the pushes
    ./local/dev.sh cj-webhook subscribe                   # reconcile subscriptions now
    ./local/dev.sh cj-webhook status                      # what is recorded here

``<public base url>`` is the gateway's public HTTPS address (locally, a
cloudflared tunnel to it); CJ is told to push to
``<base>/api/v1/cjdropshipping/webhook``. CJ refuses localhost addresses.

``open-id --to <file>`` writes the account's openId (the key CJ signs pushes
with) into a private file dev.sh created, which dev.sh then pipes into Vault
and deletes. Never to standard output: the service's JSON log lines go there,
and capturing it once stored them in Vault around the openId.
"""

import argparse
import asyncio
import re
import stat
import sys
from pathlib import Path

from sqlalchemy import func, select

from models.cj_stock_subscription_models import CJStockSubscription, CJStockSubscriptionVariant
from resources import create_database_manager, logger, settings
from service_layer.cj_api_client import CJDropshippingAPIClient, CJDropshippingAPIError
from service_layer.cj_webhook_subscription_service import CJWebhookSubscriptionService
from service_layer.product_service_client import ProductServiceClient, ProductServiceError
from shared.managers.database_session_manager import DatabaseSessionManager

# CJ's openId is a Long.
_OPEN_ID = re.compile(r"\d{1,20}")


async def _status(database: DatabaseSessionManager) -> dict[str, int]:
    async with database.transaction() as session:
        products = await session.scalar(select(func.count()).select_from(CJStockSubscription))
        subscribed = await session.scalar(
            select(func.count()).select_from(CJStockSubscription).where(CJStockSubscription.subscribed_at.is_not(None))
        )
        variants = await session.scalar(select(func.count()).select_from(CJStockSubscriptionVariant))
    return {"products": products or 0, "subscribed": subscribed or 0, "variants": variants or 0}


async def _open_id(api_client: CJDropshippingAPIClient) -> str:
    """The openId CJ returns with an access token. CJ rate-limits token requests: run it rarely."""
    response = await api_client.request(
        "POST",
        settings.CJ_DROPSHIPPING_ACCESS_TOKEN_URL,
        json=settings.CJ_DROPSHIPPING_AUTH_PAYLOAD,
        idempotent=True,
        _retry_on_401=False,
    )
    open_id = str((response.get("data") or {}).get("openId") or "").strip()
    if not _OPEN_ID.fullmatch(open_id):
        # Never echo it: whatever CJ sent there may still be the real one.
        raise CJDropshippingAPIError("CJ's access-token response carries no numeric openId")
    return open_id


def _private_empty_file(path: Path | None) -> bool:
    """
    ``path`` is the empty, owner-only regular file dev.sh made for the openId.

    Checked before CJ is asked for anything: a token request is rate-limited.
    """
    if path is None:
        return False
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(info.st_mode) and info.st_size == 0 and stat.S_IMODE(info.st_mode) & 0o077 == 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dev.sh cj-webhook", description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("action", choices=["enable", "disable", "subscribe", "status", "open-id"])
    parser.add_argument("public_base_url", nargs="?", help="the gateway's public https address (enable/disable)")
    parser.add_argument("--to", type=Path, help="open-id: the private file to write the openId into")
    return parser


async def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    if args.action in ("enable", "disable"):
        if not args.public_base_url or not args.public_base_url.startswith("https://"):
            print("cj-webhook: enable/disable need the public https:// base address", file=sys.stderr)
            return 2
    if args.action == "open-id" and not _private_empty_file(args.to):
        print("cj-webhook: open-id is a secret, written only into an empty owner-only file (--to); "
              "use ./local/dev.sh cj-webhook store-open-id", file=sys.stderr)
        return 2

    # A CLI prints its own results: no SQL echo, whatever DEBUG_MODE says.
    database = create_database_manager(settings.model_copy(update={"DEBUG_MODE": False}))
    api_client = CJDropshippingAPIClient(settings)
    product_client = ProductServiceClient(settings)
    service = CJWebhookSubscriptionService(
        settings=settings, database=database, api_client=api_client,
        product_client=product_client, logger=logger,
    )
    try:
        match args.action:
            case "open-id":
                args.to.write_text(await _open_id(api_client))
            case "status":
                for key, value in (await _status(database)).items():
                    print(f"  {key:12} {value}")
            case "disable":
                print(f"  cancelled for {await service.register(args.public_base_url, 'CANCEL')}")
            case "enable" | "subscribe":
                if args.action == "enable":
                    print(f"  CJ pushes to {await service.register(args.public_base_url, 'ENABLE')}")
                for key, value in (await service.reconcile()).as_dict().items():
                    print(f"  {key:16} {value}")
        return 0
    except (CJDropshippingAPIError, ProductServiceError) as exc:
        print(f"cj-webhook: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            await product_client.close()
            await api_client.close()
        finally:
            await database.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
