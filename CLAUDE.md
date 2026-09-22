# CLAUDE.md

# General guidance
 - We work in "Ask" mode where i will be asking quatiuons and you will be providing the answers with the code snippets without direct changes of files (only if i explicitly ask to do changes or I changed the mode to "auto")
 - Always use comments in code when a deep and/or nested logic is expected
 - Do not mock the critical scenarios during the test creation, always ask me for clarifications

# Frontend (@frontend)
 - Don't use "any" as a type - always ask me for clarifications what data im expecting to send/receive
 - Use the generic types where its applicable
 - Use the OOP style with appropriate design patterns where they applicable (watch for @docs/DESIGN_PATTERNS.md)
 - Use Chrome for testing the UI/UX

# Backend (@backend)
 - Follow the current event-driven micro-service architecture 
 - Do coding in OOP style with the usage of design patterns where they are applicable (watch for @docs/DESIGN_PATTERNS.md)
 - Follow the clean / layered architecture 
 - Break the complex classes using proper inheritance or composition or decomposition 
 - Never use “Any” as the type - ask for clarifications what i’m expecting to send/receive
 - Where the generic types with latest syntax where they are applicable

# Running the project locally (no Docker)

We develop natively — Docker / docker-compose is **not** used day to day. Everything
is driven by `backend/local/dev.sh`, which runs Postgres, Redis and RabbitMQ as
Homebrew processes (data under `backend/local/data`) and every service straight out
of its own `.venv`. The Next.js frontend is started by the same script.

`backend/.env.local` holds the no-Docker overrides (`POSTGRES_HOST=127.0.0.1`,
`*_SERVICE_URL=http://127.0.0.1:80xx`, …) and is layered on top of `backend/.env`.

## First-time setup
```bash
cd backend
./local/dev.sh install          # brew: postgresql@16, redis, rabbitmq
./local/dev.sh init             # initdb, create every DB, provision the rabbit user

# Python deps — once per service
for s in api_gateway user_service product_service supplier_service order_service \
         payment_service cart_service wishlist_service shipping_service notification_service; do
  (cd "$s" && uv sync)
done

# Frontend deps
cd ../frontend && npm install
```

## Day to day

```bash
cd backend
./local/dev.sh up               # infra + migrations + all services + frontend
RELOAD=1 ./local/dev.sh up      # same, with uvicorn --reload
./local/dev.sh status           # what is up, with pids
./local/dev.sh logs order-service
./local/dev.sh restart order-service
./local/dev.sh down             # stop services + infra
./local/dev.sh migrate          # alembic upgrade head for every service
./local/dev.sh reset            # down + delete local data (destructive)
```

A single process by name — `frontend` included:

```bash
./local/dev.sh up frontend
./local/dev.sh down frontend
FRONTEND_PORT=3000 ./local/dev.sh up frontend   # default is 30000
```

Logs land in `backend/local/logs/<name>.log`, pids in `backend/local/run/`.

## Frontend runs on webpack, not Turbopack

`package.json`'s `dev` script is `next dev --webpack` on purpose. Turbopack — the
Next 16 default — intermittently fails to register client components in the RSC
manifest (`Could not find the module "…global-error.js#default" in the React Client
Manifest`), which 500s roughly 40% of renders. Those 500s surface as an unstyled
page, because the `/_error` fallback ships no stylesheet. Do not drop the flag
without re-testing repeated reloads; `next build` is unaffected.


# Local service URLs

| Process | URL |
| --- | --- |
| Frontend (Next.js) | `http://localhost:30000` |
| API Gateway | `http://127.0.0.1:8000` — the only entry point the frontend calls |
| user-service | `http://127.0.0.1:8001` |
| product-service | `http://127.0.0.1:8002` |
| notification-service | `http://127.0.0.1:8003` |
| order-service | `http://127.0.0.1:8005` |
| payment-service | `http://127.0.0.1:8006` |
| cart-service | `http://127.0.0.1:8007` |
| shipping-service | `http://127.0.0.1:8008` |
| wishlist-service | `http://127.0.0.1:8009` |
| supplier-service | `http://127.0.0.1:8010` |
| cj-mcp (CJ Dropshipping MCP) | `http://127.0.0.1:3009/mcp` — health at `/health` |

Every FastAPI app serves Swagger at `/docs` and its routes under `/api/v1`.
The gateway exposes `/health`; the services expose `/health/live` and `/health/ready`.

Backing services:

- Postgres: `127.0.0.1:5432`
- Redis: `127.0.0.1:6379` (compose publishes its container on 6380 instead)
- RabbitMQ: `127.0.0.1:5672`, management UI `http://localhost:15672`

`cj-mcp` is not part of the app: it is the CJ Dropshipping MCP server, started by
`dev.sh` out of the sibling `../api-mcp` checkout (override with `CJ_MCP_DIR` /
`CJ_MCP_PORT`) and skipped when that checkout is missing. It runs in HTTP transport
because only that one accepts CJ's direct-token URL,
`/mcp/MCP@<userId>@CJ:<accessToken>` — the access token lives in the MCP client
config (`~/.claude.json`), never in this repo.

Only reachable when the Docker stack is up, i.e. **not** in the local setup:
PgAdmin `http://localhost:5050`, Traefik dashboard `http://localhost:8090/dashboard`,
Prometheus Alertmanager `http://localhost:9093`, Grafana / Tempo / Loki /
otel-collector, admin-js `http://localhost:3001`.


# Running the tests locally

Each service is a standalone `uv` project; pytest is configured in its `pyproject.toml`
(`asyncio_mode = "auto"`, `testpaths = ["tests"]`). Tests split into
`tests/unit_tests/` and `tests/integration_tests/`.

```bash
cd backend/<service>            # e.g. backend/order_service

# Unit tests only — no infra needed
uv run pytest tests/ -v -k "not integration"

# Integration tests — need local Postgres up and the *_test_db databases
# (both provided by ./local/dev.sh init + ./local/dev.sh infra up)
uv run pytest tests/ -v -k integration

# Everything
uv run pytest tests/ -v
```

Prefix with `OTEL_TRACES_DISABLED=true` to silence the otel-collector export
warnings that appear when the observability stack is not running.

Single file or single test:

```bash
uv run pytest tests/unit_tests/test_order_service.py -v
uv run pytest tests/unit_tests/test_order_service.py::test_create_order -v
```

`backend/run_tests.sh` runs the whole suite across all services in Docker — it needs
a running Docker daemon, so it is unused while we develop locally.

Frontend: no test runner is configured yet. The available checks are
`npm run lint` and `npx tsc --noEmit`.
