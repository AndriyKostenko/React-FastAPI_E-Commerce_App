"""Check that every process's database pool fits Postgres's max_connections.

Reads docker-compose.yml. A container built from a service that has a database
holds, at most:

    GUNICORN_WORKERS (default 1)
  x ecommerce.db.max-engines label (default 1; taskiq workers open one per task)
  x (DB_POOL_SIZE + DB_MAX_OVERFLOW)

and the sum over all of them must stay within the db container's
max_connections minus RESERVED (superuser slots, alembic migrations, psql,
backups, monitoring). A container from such a service must state its pool
explicitly, or carry ecommerce.db.max-engines "0" when it uses no database, so
a new worker cannot quietly take connections nobody budgeted for.

usage (from backend/):  ./local/dev.sh pool-budget
"""

import re
import sys
from pathlib import Path

import yaml

COMPOSE = Path(__file__).resolve().parents[1] / "docker-compose.yml"
DB_SERVICE_DIRS = frozenset({
    "user_service", "product_service", "supplier_service", "notification_service", "order_service",
    "payment_service", "cart_service", "wishlist_service", "shipping_service",
})
# Postgres keeps 3 for superusers by default; the rest covers migrations
# running beside the stack, psql sessions, backups and monitoring.
RESERVED = 15
ENGINES_LABEL = "ecommerce.db.max-engines"


def max_connections(db: dict) -> int:
    command = db.get("command", "")
    command = " ".join(command) if isinstance(command, list) else str(command)
    found = re.search(r"max_connections=(\d+)", command)
    if not found:
        raise SystemExit("db: no -c max_connections=N in its command")
    return int(found.group(1))


def as_dict(value: dict | list | None) -> dict[str, str]:
    """Compose allows both `KEY: value` maps and `- KEY=value` lists."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    return dict(item.split("=", 1) for item in value if "=" in item)


def main() -> int:
    services: dict = yaml.safe_load(COMPOSE.read_text())["services"]
    limit = max_connections(services["db"])
    rows: list[tuple[str, int, int, int, int]] = []
    problems: list[str] = []
    for name, spec in services.items():
        build = spec.get("build") or {}
        context = build.get("context", "") if isinstance(build, dict) else str(build)
        if Path(context).name not in DB_SERVICE_DIRS:
            continue
        env, labels = as_dict(spec.get("environment")), as_dict(spec.get("labels"))
        engines = int(labels.get(ENGINES_LABEL, "1"))
        if engines == 0:
            continue
        if "DB_POOL_SIZE" not in env or "DB_MAX_OVERFLOW" not in env:
            problems.append(f"{name}: no DB_POOL_SIZE / DB_MAX_OVERFLOW (or {ENGINES_LABEL}: \"0\")")
            continue
        per_engine = int(env["DB_POOL_SIZE"]) + int(env["DB_MAX_OVERFLOW"])
        workers = int(env.get("GUNICORN_WORKERS", "1"))
        rows.append((name, workers, engines, per_engine, workers * engines * per_engine))

    total = sum(row[4] for row in rows)
    budget = limit - RESERVED
    print(f"{'container':28} {'workers':>7} {'engines':>7} {'pool+ovf':>8} {'max':>4}")
    for name, workers, engines, per_engine, most in sorted(rows):
        print(f"{name:28} {workers:>7} {engines:>7} {per_engine:>8} {most:>4}")
    print(f"\ntotal {total} of {budget} (max_connections {limit} - reserve {RESERVED})")
    for problem in problems:
        print(f"!! {problem}")
    if total > budget:
        print(f"!! over budget by {total - budget}: shrink a pool or raise max_connections")
    return 1 if problems or total > budget else 0


if __name__ == "__main__":
    sys.exit(main())
