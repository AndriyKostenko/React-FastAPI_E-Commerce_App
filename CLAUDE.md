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
is driven by `backend/local/dev.sh`, which runs Postgres, Redis, RabbitMQ and
SeaweedFS (the local S3 server) as Homebrew processes (data under `backend/local/data`) and every service straight out
of its own `.venv`. The Next.js frontend is started by the same script.

`backend/.env` is the single source of configuration and holds the local values
(`POSTGRES_HOST=127.0.0.1`, `*_SERVICE_URL=http://127.0.0.1:80xx`, …). There is no
`.env.local` any more.

Secrets are not in it: they live in a local HashiCorp Vault that `dev.sh` runs
on `127.0.0.1:8200`, one path per service (`secret/ecommerce/<service>`, plus
`secret/ecommerce/shared-infra` for the Postgres/Redis/RabbitMQ passwords).
Every process `dev.sh` starts signs in with its own AppRole and can read only
its own path; a service that can't reach Vault refuses to start, naming what is
missing. The unseal key, root token and AppRole credentials are kept in
`backend/local/run/vault/` (this machine only).

## First-time setup

```bash
cd backend
./local/dev.sh install          # brew: postgresql@16, redis, rabbitmq, cloudflared, seaweedfs, vault
./local/dev.sh vault up         # start, initialise and unseal Vault; one AppRole per service
./local/dev.sh vault import     # one time, run it yourself: move the secrets from
                                # backend's config file into Vault (--dry-run first)
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
./local/dev.sh vault status     # which secret keys each Vault path holds (names only)
./local/dev.sh storage status   # S3 buckets and object counts
./local/dev.sh storage import-local   # one time: copy local-disk designs and return photos into S3
./local/dev.sh images mirror    # copy CJ catalogue images into S3 now (also runs every 15 min)
./local/dev.sh reset            # down + delete local data (destructive)
./local/dev.sh cj-sandbox status|ship|deliver|poll <order_id>   # see below
./local/dev.sh cj-webhook tunnel|tunnel-stop|subscribe|status    # see below
```

**CJ sandbox.** With `CJ_DROPSHIPPING_SANDBOX=true`, new CJ orders are created
with `isSandbox=1`: CJ simulates the payment (`simulatePay`, no wallet money) and
never ships. The rest of the flow is real: confirm, cost ceiling, card capture,
tracking, emails. A sandbox order never ships by itself, so
`./local/dev.sh cj-sandbox ship <order_id>` gives it a tracking number and moves it
to shipped, `deliver` to completed; both then run one tracking poll so the events
follow at once. Whether an order is a sandbox one is recorded when it is sent
(`cj_order_attempts.is_sandbox`), so toggling the setting never changes how an
existing order is paid. Never enable it where real sales happen.

**Images live in S3** (SeaweedFS on `127.0.0.1:8333`, started by `infra up`).
Two buckets: `ecommerce-catalogue` is anonymously readable and holds product,
variant and category images (CJ copies and admin uploads); `ecommerce-private`
holds generated designs and return photos and is reached only with a
service's own key or a presigned URL. The non-secret settings
(`OBJECT_STORAGE_BACKEND=s3`, endpoint, bucket names) are exported by `dev.sh`;
product- and order-service's access keys, the admin key and the at-rest
encryption key are generated into Vault on first start (`local/s3_local.py`),
and each service's key reaches only its own bucket or prefix. The database
keeps catalogue *keys*, not URLs; responses add the public origin. CJ images
are copied in by the product taskiq task `mirror_catalogue_images`; until an
image is copied its CJ URL is served. Test suites use their own
`ecommerce-*-test` buckets. Details: `backend/product_service/ARTWORK_STORAGE.md`.

**CJ stock webhook.** CJ pushes stock changes (topic STOCK) to
`POST /api/v1/cjdropshipping/webhook` on the gateway, which forwards the raw
body to supplier-service; each push is verified against CJ's `sign` header
(HMAC-SHA256 keyed by the account's openId, `CJ_DROPSHIPPING_OPEN_ID` in
supplier-service's Vault path) and becomes the same `supplier.stock.updated`
event the hourly refresh sends, which stays as the backstop. CJ only pushes to a
public HTTPS address, so locally `./local/dev.sh cj-webhook tunnel` starts a
cloudflared quick tunnel to the gateway and registers its URL with CJ (a new
URL each run, so re-run it after a restart; `tunnel-stop` cancels it).
`./local/dev.sh cj-webhook store-open-id` (run it yourself, once) copies the
openId from CJ into Vault without printing it; restart supplier-service after.
Only subscribed products push: the hourly `reconcile_cj_stock_subscriptions`
task (and `cj-webhook subscribe`) keeps the subscriptions equal to what we sell.

A single process by name — `frontend` included:

```bash
./local/dev.sh up frontend
./local/dev.sh down frontend
FRONTEND_PORT=3000 ./local/dev.sh up frontend   # default is 30000
./local/dev.sh up admin-js                      # AdminJS on :3001 (ADMIN_JS_PORT)
```

admin-js (`backend/admin-js-service`) runs `npm run start:local`: it compiles and
reads `backend/.env` through node's own `--env-file`, with the
host-specific values (Redis host, gateway URL, port) pinned by `dev.sh`. It needs
`COOKIE_SECRET`, `ADMINJS_SERVICE_REDIS_DB` and `ADMINJS_SERVICE_REDIS_PREFIX` in
`backend/.env` and refuses to start, naming the missing ones, without them.

Logs land in `backend/local/logs/<name>.log`, pids in `backend/local/run/`.

## Frontend runs on webpack, not Turbopack

`package.json`'s `dev` script is `next dev --webpack` on purpose. Turbopack — the
Next 16 default — intermittently fails to register client components in the RSC
manifest (`Could not find the module "…global-error.js#default" in the React Client
Manifest`), which 500s roughly 40% of renders. Those 500s surface as an unstyled
page, because the `/_error` fallback ships no stylesheet. Do not drop the flag
without re-testing repeated reloads; `next build` is unaffected.

# Local service URLs

| Process                      | URL                                                               |
| ---------------------------- | ----------------------------------------------------------------- |
| Frontend (Next.js)           | `http://localhost:30000`                                          |
| API Gateway                  | `http://127.0.0.1:8000` — the only entry point the frontend calls |
| user-service                 | `http://127.0.0.1:8001`                                           |
| product-service              | `http://127.0.0.1:8002`                                           |
| notification-service         | `http://127.0.0.1:8003`                                           |
| order-service                | `http://127.0.0.1:8005`                                           |
| payment-service              | `http://127.0.0.1:8006`                                           |
| cart-service                 | `http://127.0.0.1:8007`                                           |
| shipping-service             | `http://127.0.0.1:8008`                                           |
| wishlist-service             | `http://127.0.0.1:8009`                                           |
| supplier-service             | `http://127.0.0.1:8010`                                           |
| cj-mcp (CJ Dropshipping MCP) | `http://127.0.0.1:3009/mcp` — health at `/health`                 |
| admin-js (AdminJS)           | `http://localhost:3001/admin` — log in with an admin account      |
| Vault                        | `http://127.0.0.1:8200` — UI at `/ui`, root token in `backend/local/run/vault/init.json` |
| S3 (SeaweedFS)               | `http://127.0.0.1:8333` — catalogue images public at `/ecommerce-catalogue/<key>` |

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
otel-collector.

# Running the tests locally

Each service is a standalone `uv` project; pytest is configured in its `pyproject.toml`
(`asyncio_mode = "auto"`, `testpaths = ["tests"]`). Tests split into
`tests/unit_tests/` and `tests/integration_tests/`.

Settings read their secrets (the database password included) from Vault, so run
a suite through `dev.sh`, which gives it that service's Vault identity:

```bash
cd backend
./local/dev.sh test order_service                 # the whole suite
./local/dev.sh test order_service -k integration  # any pytest arguments
./local/dev.sh test shared                        # shared/'s own suite
```

Inside a service directory, plain `uv run pytest` works only with the `VAULT_*`
variables `dev.sh` exports (see `export_vault_identity` in `local/dev.sh`):

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
