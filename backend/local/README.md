# Running the backend locally, without Docker

A temporary alternative to `docker compose up`: Postgres, Redis and RabbitMQ run
as ordinary Homebrew processes, and every Python service runs straight out of the
venv it already has. The observability stack (Prometheus, Grafana, Loki, Tempo,
otel-collector, cAdvisor, Alertmanager), Traefik, pgAdmin and admin-js are **not**
started — this is the business path only.

## How the two env files relate

They are layered, not alternatives. `shared/settings.py` reads `(.env, .env.local)`
in that order, so `.env` supplies the whole configuration — secrets, DB names, mail,
Stripe, CORS — and `.env.local` overlays only the ~20 keys that differ when nothing
runs in Docker: the infra hosts and ports, and the service-to-service URLs. Local
development needs both files; `.env.local` on its own is not a working config.

| | `.env` | `.env.local` |
|---|---|---|
| holds | the full configuration | host/port overrides only |
| tracked in git | no (gitignored) | **yes** — keep it secret-free |
| read in Docker | no, see below | no, see below |

## Why this does not disturb the Docker setup

Neither file reaches a container. Each service's `.dockerignore` excludes `.env*`,
and `settings.py` resolves the pair relative to `shared/`, which lands on `/app/.env`
and `/app/.env.local` inside the image — paths that do not exist there. Compose
feeds every value in through `env_file:` as real environment variables instead, and
pydantic-settings ranks those above both files anyway. Nothing in
`docker-compose.yml` changed.

## One-time setup

```bash
cd backend
./local/dev.sh install   # brew install postgresql@16 redis rabbitmq
./local/dev.sh init      # initdb, create the per-service DBs, add the rabbit user
```

`init` builds a cluster under `backend/local/data/postgres` with the same tuning the
compose `db` service uses (`max_connections=300`, `shared_buffers=256MB`, …). It is
a separate cluster from any other Postgres on the machine and from the compose
volume, so **the databases start empty** — see "Bringing data over" below.

## Day to day

```bash
./local/dev.sh up          # infra + alembic upgrade head + all 29 processes
./local/dev.sh status      # infra and per-process state
./local/dev.sh logs user-service
./local/dev.sh restart order-consumer
./local/dev.sh down        # services + infra
RELOAD=1 ./local/dev.sh up # HTTP services with uvicorn --reload
```

Logs land in `backend/local/logs/<name>.log`, pids in `backend/local/run/`.

Ports are unchanged from compose: gateway `8000`, user `8001`, product `8002`,
notification `8003`, order `8005`, payment `8006`, cart `8007`, shipping `8008`,
wishlist `8009`, supplier `8010`, RabbitMQ management UI `15672`. Redis listens on
**6379** locally (compose publishes its container on 6380) and Postgres on 5432 —
so the compose stack must be down first, or `dev.sh` will refuse to start.

## What differs from compose

- `uvicorn` with one worker instead of `gunicorn`, which keeps
  `PROMETHEUS_MULTIPROC_DIR` out of the picture; `/metrics` still works off the
  single-process registry.
- `OTEL_TRACES_DISABLED=true` is exported, since there is no collector to ship
  spans to. Unset it if you start one.
- Service-to-service URLs point at `127.0.0.1:<port>` instead of container DNS
  names. `ALLOWED_HOSTS` already contains `127.0.0.1`, so host validation passes.
- `MEDIA_ROOT` is `backend/local/data/media` rather than the `product_media` volume.

## Bringing data over from the Docker volume

```bash
# with the compose stack up
docker compose exec -T db pg_dumpall -U postgres > /tmp/dump.sql
docker compose down
./local/dev.sh infra up
PGPASSWORD=... psql -h 127.0.0.1 -U postgres -d postgres -f /tmp/dump.sql
```

## Going back to Docker

```bash
./local/dev.sh down
docker compose up -d --build
```

`.env.local` can stay in place — no container ever reads it. It is a tracked file,
so the only change to revert if you want this setup gone entirely is
`git checkout backend/.env.local` (plus deleting `backend/local/`). Clear the native
databases with `./local/dev.sh reset`.

## Inspecting the data

Two GUI clients are installed: **TablePlus** (`/Applications/TablePlus.app`) for
Postgres and **Redis Insight** (`/Applications/Redis Insight.app`) for Redis.
Reinstall either with `brew install --cask tableplus redis-insight`.

Neither client auto-refreshes — reload the tab after exercising a flow.

### Postgres — TablePlus

| field | value |
|---|---|
| Host | `127.0.0.1` |
| Port | `5432` |
| User | `postgres` |
| Password | `POSTGRES_PASSWORD` from `backend/.env` |
| Database | `user_service_db` (any one — see below) |

Each service owns its own database, so there are 21 of them
(`<service>_service_db` plus a `_test_db` twin, and `outbox_events_db`). Rather
than defining 21 connections, connect to one and use the sidebar database picker;
in DBeaver the equivalent is the "Show all databases" checkbox.

### Redis — Redis Insight

| field | value |
|---|---|
| Host | `127.0.0.1` |
| Port | `6379` |
| Username | *(none)* |
| Password | `REDIS_PASSWORD` from `backend/.env` |

Every client opens on db0, which is nearly empty here — the services are spread
across indices, and each namespaces its keys with its `*_REDIS_PREFIX`:

| db | service | db | service |
|---|---|---|---|
| 0 | api-gateway | 7 | shipping |
| 1 | user | 8 | wishlist |
| 2 | product | 9 | notification taskiq results |
| 3 | notification | 12 | supplier |
| 4 | order | 13 | session registry |
| 5 | payment | | |
| 6 | cart | | |

### From the terminal

```bash
cd backend
export REDISCLI_AUTH=$(sed -n 's/^REDIS_PASSWORD=//p' .env)   # keeps it off the argv
redis-cli -n 12 --scan          # list one service's keys
redis-cli -n 0 monitor          # live firehose of every command

export PGPASSWORD=$(sed -n 's/^POSTGRES_PASSWORD=//p' .env)
psql -h 127.0.0.1 -U postgres -d order_service_db
```

`\watch 2` after a query inside `psql` re-runs it every two seconds — the closest
thing to watching saga status transitions or the outbox drain in real time.
