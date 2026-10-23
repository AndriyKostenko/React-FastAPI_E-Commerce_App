"""
Once a day, deletes what product-service keeps no longer than needed:
designs no order holds, GENERATED_DESIGN_RETENTION_DAYS after they were
made, and refusal records after DESIGN_REFUSAL_RETENTION_DAYS.
"""

from resources import create_database_manager, create_design_refusal_retention, create_design_retention
from tasks.broker import taskiq_broker


async def run_product_retention() -> dict[str, int]:
    """One run, with a database engine of its own."""
    database = create_database_manager()
    try:
        return {
            "designs_deleted": await create_design_retention(database).prune(),
            "refusals_deleted": await create_design_refusal_retention(database).prune(),
        }
    finally:
        await database.close()


@taskiq_broker.task(schedule=[{"cron": "20 3 * * *"}])
async def delete_expired_designs() -> dict[str, int]:
    return await run_product_retention()
