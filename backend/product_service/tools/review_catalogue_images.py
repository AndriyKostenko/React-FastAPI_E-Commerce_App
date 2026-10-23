"""
Review the photos of supplier products imported before photo reviews existed
(``./local/dev.sh products review [limit]``, 20 at most by default).

The import reviews new products itself; this is the one-off for the rest.
Each photo costs one OpenRouter call. An approved product gets the model's
description; a rejected one is listed here for the owner to decide on and is
never deleted, but later syncs leave it as it is. A product with no answer
(provider down, photo gone) is listed too and stays unreviewed, so a later
run tries it again.
"""

import asyncio
import json
import sys

from aiohttp import ClientSession

from resources import create_cache_manager, create_database_manager, create_supplier_image_review_service, settings


async def main(limit: int) -> int:
    # A CLI prints its own results: no SQL echo, whatever DEBUG_MODE says.
    database = create_database_manager(settings.model_copy(update={"DEBUG_MODE": False}))
    cache = create_cache_manager()
    try:
        await cache.connect()
        async with ClientSession() as http:
            report = await create_supplier_image_review_service(database, http).review_catalogue(limit)
        if report.described:
            # Descriptions changed: cached catalogue responses would show the old ones.
            await cache.invalidate_namespace(namespace="products")
    finally:
        try:
            await cache.close()
        finally:
            await database.close()

    for pid, name, reason in report.rejected:
        print(f"rejected     {pid}  {name[:60]}  -- {reason}")
    for pid, reason in report.unavailable:
        print(f"no answer    {pid}  -- {reason}")
    print(json.dumps(report.as_dict()))
    return 0 if not report.unavailable else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 20)))
