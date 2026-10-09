"""
Run one catalogue image sweep now (``./local/dev.sh images mirror``).

The scheduled task does the same every 15 minutes, one batch at a time;
this repeats batches until nothing due is left, for a backfill.
"""

import asyncio
import json

from tasks.catalogue_image_tasks import run_catalogue_image_mirror


async def main() -> int:
    while True:
        report = await run_catalogue_image_mirror()
        print(json.dumps(report.as_dict()))
        if report.skipped_already_running:
            print("Another sweep is running; try again when it is done.")
            return 1
        # A batch that copied or rewrote nothing means only retries that
        # are not yet due (or nothing at all) are left.
        if report.mirrored == 0 and report.rows_rewritten == 0:
            return 0 if report.failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
