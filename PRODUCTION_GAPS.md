# Production Readiness — Remaining Gaps

Context: business goal is (1) users create AI print designs on t-shirts that you
produce at home and ship yourself, and (2) users buy t-shirts sourced from
CJDropshipping (products pre-fetched and stored in your DB).

Assessment date: 2026-09-03. Last updated 2026-10-10 (AdminJS: passkeys, sole
back office, every resource, §8.4; before that S3 for images, §8.3; the
CJ stock webhook, §8.2; before that the refund and cancellation paths,
PRs #12-#16, see §5a). The hard architectural + integration work is
substantially done (CJ integration, AI generation, order saga, artwork storage).
What remains is operational glue, hardening, and in-house fulfillment tooling —
estimated a few focused weeks, no re-architecting required.

---

## What's already in place

**AI print-on-demand flow**
- `product_service`: `openrouter_client` -> `image_generation_service` (+ quota, job store)
  -> `image_storage_service` (S3, signed immutable manifest, SHA-256, pixel/DPI/print-area
  validation — see `product_service/ARTWORK_STORAGE.md`)
- Frontend: `GenerationPanel`, `TShirtPreview`, `TshirtMeasurement`, `useGenerationSession`,
  `getCustomTshirtPricing`, `generateImage` action

**CJ Dropshipping**
- `supplier_service`: `cj_api_client` (token auth, `listV2`, `createOrderV2`, order detail,
  delete), `sync_orchestrator_service` + `scheduler` (products fetched & stored in DB),
  `cj_inventory_verifier`, `cj_to_supplier_mapper`, `cj_order_attempt_repository`, unit tests

**Dual fulfillment routing already modeled**
- `order_service`: `OrderLineFulfillment.fulfillment_type` splits per line item;
  `CustomProductionJob` = durable in-house work queue; `supplier_id` path -> CJ
- Order saga with payment/inventory/fulfillment gates + `saga_timeout_worker`

**Infra**: Stripe payments (shared async client), shipping service, full observability
(Prometheus/Grafana/Tempo/Loki/OTel/Alertmanager), Traefik edge routing, Docker Compose,
k6 load tests, Alembic per service. The large `shared/` refactor called out in
`shared/shared_service_issues.txt` was largely completed in the Aug 14–15 commits.

---

## What's still missing for production

### 1. Deployment & CI/CD (biggest gap)
- `.github/` has only Copilot instructions — no CI, no test-on-PR, no image build/publish
- No K8s/Helm manifests; migrations run by hand via `docker compose exec`
- [x] **`order_service` Alembic setup — DONE (2026-09-09).** It was the only one
  of the nine services without migrations, while relying on `init_db`/`create_all`,
  whose own docstring says it "deliberately cannot alter existing columns". That
  became acute with §2, which adds eleven columns to `custom_production_jobs`:
  against any database with history they would simply not appear, and the queue
  would fail at runtime on a service that reported a clean startup.
  - `b1f0c9d24a70` baselines the pre-migration schema exactly, so an existing
    database joins with `alembic stamp b1f0c9d24a70` and then upgrades normally
  - `e2c74b1a8f36` adds the production-queue lifecycle columns
  - `main.py` no longer calls `init_db`; Alembic is the only schema authority
  - `entrypoint-api.sh` runs `alembic upgrade head` before gunicorn, so this
    service's migrations are no longer a hand-run step
  - Verified three ways: a fresh database builds from zero, a baseline-only
    database upgrades with its data intact, and `alembic check` reports
    "No new upgrade operations detected" against the models
  - Removing that last drift needed a small model fix: `unique=True` sat on four
    primary-key columns (`orders`, `order_items`, `order_addresses`, and the
    shared outbox mixin). It is redundant on a PK and `create_all` never emitted
    it — no database anywhere has such a constraint — but it made `alembic check`
    report permanent phantom drift, which would defeat the point of adding
    migration checking to CI.
- [x] **All nine services now own their schema through Alembic — DONE (2026-09-09).**
  Every service had been bolting Alembic beside `create_all`, and *not one of
  them could rebuild its database from migrations*:
  - `user_service` and `product_service` migrations altered tables (`users`,
    `products`) that no migration ever created, so `alembic upgrade head`
    failed outright. Their chains could not run, so each was squashed to a
    baseline generated from the models; the originals are kept under
    `<service>/alembic_archive/` and in git history.
  - `cart`, `shipping`, `wishlist` and `notification` had **no migrations at
    all** — an `alembic/` directory with an empty `versions/`. Each got a
    baseline.
  - `payment` was missing the outbox retry columns; `supplier` created a unique
    *constraint* where the model declares a unique *index*. Each got a
    corrective migration (supplier's fix went into its initial migration,
    since dropping the constraint would have broken a dependent foreign key).
  - The redundant `unique=True` on primary-key columns was removed in 16 places
    across 13 model files. `create_all` never emitted it and no database has
    it, but it made `alembic check` report permanent phantom drift.
  - `init_db` is gone from all nine `main.py` files, and each service runs
    `alembic upgrade head` from an `entrypoint-api.sh` before gunicorn — so
    migrations are no longer a hand-run step anywhere.
  - Verified: every service builds its schema from an empty database, every
    service reports `alembic check` clean against its models, and the whole
    stack was brought up on wiped volumes with all nine applying their own
    migrations at startup.
- **Existing databases** join with `alembic stamp <baseline>` before their
  first upgrade; a database built by the old `create_all` already matches the
  baseline.
- No backup/DR plan for the 9 Postgres DBs; connection pooling unconfirmed
- No blue/green or canary, no auto-rollback on deploy failure

### 2. In-house fulfillment operations — DONE (2026-09-09)

The terminal path for a custom T-shirt now exists end to end. `order_service`
owns the queue, because it owns `CustomProductionJob`.

- [x] Admin production queue API (`order_service/routes/production_routes.py`,
      `/api/v1/admin/production/jobs`, admin-only through the gateway)
  - list/filter the queue with per-status counts, and one job in detail
  - `GET .../artwork` resolves the stored signed manifest into a short-lived
    print-file download; `GET .../packing-slip` returns the slip as structured
    data (the gateway normalizes every upstream response to JSON, and the admin
    UI renders and prints it)
  - `start` / `printed` / `ship` (tracking number) / `delivered` / `hold` /
    `resume` / `cancel`, each row locked for update so two operators cannot
    advance the same job
  - `ProductionJobStateMachine` is the single authority on legal moves; a job
    resumed after a hold returns to the step its timestamps say it reached
- [x] **Terminal path.** `production.job.*` events on the order exchange, relayed
      through the existing outbox. `notification_service` binds
      `notification.production.events.queue` and emails the customer their
      tracking number on shipped and a confirmation on delivered — the same
      templates the CJ flow uses, now fed by a shared `OrderShippedBaseEvent` /
      `OrderDeliveredBaseEvent`. shipping_service's comment about a
      "production-complete event that does not exist" is resolved.
- [x] **Cancelling completed work no longer silently refunds.**
      `OrderCancelledEvent.reconciliation_required` is set when any job was
      already printed or posted; payment_service logs it CRITICAL and blocks the
      automatic Stripe refund, exactly as an already-shipped CJ order is handled.
- [x] **`cancel_order`'s guard now binds.** It refuses per line
      (`LineFulfillmentStatus.blocks_cancellation`) rather than on the
      order-level `delivery_status == DELIVERED` a custom order can never reach,
      so printed and posted goods are no longer cancellable-and-refundable.
- [x] **Order-level `delivery_status` is derived, not overwritten.**
      `OrderDeliveryStatusAggregator` folds every `OrderLineFulfillment.status`
      into one order status, and CJ, catalog-shipping, and production events each
      move only their own channel's lines. A CJ parcel no longer marks an
      unprinted custom line as dispatched.
- [x] **Ordered artwork has a protection marker.** `order.confirmed` also writes
      `artwork.retained` (and cancellation writes `artwork.released`);
      product_service consumes them on `product.artwork.events.queue` into a new
      `retained_artwork` table (in the product baseline migration). The planned
      "clean up unreferenced drafts" job asks
      `RetainedArtworkRepository.is_key_retained` before deleting anything.
- [x] Frontend admin: `/admin/production` — queue with status counts and
      filters, print-file preview and download, printable packing slip, and the
      start/print/ship/deliver/hold/cancel controls. (Moved to AdminJS's
      "Print queue" on 2026-10-10, §8.4; the Next.js admin pages are gone.)

Tests: `tests/unit_tests/test_production_queue_service.py` (state machine +
aggregator) and `tests/integration_tests/test_production_routes.py` (16 tests
covering the full queued→printed→shipped→delivered path against a real
database, plus the cancellation guards). Verified live on a clean stack: a
custom order confirmed by a real `payment.succeeded` event, printed and posted
from the queue, moved the order to `dispatched`.

**Done (2026-09-25):** cancelling a custom job that was never printed now
refunds that line on its own (a partial refund through §5). A job cancelled
after printing is still flagged for reconciliation and left to a human.

**Done (2026-10-07, PR #14):** when that cancellation leaves no line of the
order to ship (every line cancelled, shipping not yet refunded), the refund
includes the order's shipping too; a line that shipped, even one returned
since, keeps the shipping charged. The refund now runs before
`production.job.cancelled` is published, the event carries `refunded_amount`
and `shipping_refunded`, and notification-service emails the customer
(`production_job_cancelled.html`: the item, the reason, the amount refunded).
A job cancelled after printing still sends nothing: that is a human decision.

### 3. CJ dropshipping order lifecycle completeness — DONE (2026-09-08)
- [x] Checkout-time shipping quote from CJ (`freightCalculate`)
  - `cj_api_client.calculate_freight` + `CJFreightQuoteService` (resolves local
    product/variant -> CJ vid, TTL-cached per ASGI process, cheapest option first)
  - `POST /api/v1/cjdropshipping/freight/quote`, proxied by api_gateway behind
    `get_current_user` (each call costs one live CJ request)
  - ~~Remaining: checkout has to call it~~ — done in §3b: the chosen option is
    now part of the order total.
- [x] Tracking polling from CJ -> customer notification
  - `CJOrderTrackingService` + `poll_cj_order_tracking` taskiq job (every 5 min,
    each order re-queried at most every `CJ_DROPSHIPPING_TRACKING_POLL_INTERVAL_MINUTES`)
  - Leases rows by stamping `last_polled_at` inside a short transaction, then
    calls CJ with no session or lock held
  - New `cj.order.shipped` / `cj.order.delivered` events written to the outbox in
    the same transaction as the state change; order_service moves the order to
    dispatched/delivered, notification_service emails the customer their tracking
    number (new `notification.cj.order.events.queue`, bound on `cj.order.#`)
  - CJ does push order and logistics changes by webhook (§8.2 found it), but
    tracking stays polled: those two topics are registered as off.
- [x] Stock-out / order rejection / refund handling
  - Pre-submission stock-out and mapping failures raise before the CJ POST, so
    they stay on the definitive-failure path -> `cj.order.failed` -> order
    cancelled -> Stripe refund
  - A CJ-side cancellation found by the poller emits the same `cj.order.failed`,
    so a rejection after acceptance refunds through one code path
  - Cancelling an order CJ has already shipped no longer retries `deleteOrder`
    forever; it is flagged `reconciliation_required` for a human return decision
- [x] Address validation before submitting a CJ order
  - `CJShippingAddressValidator`: required fields, ISO-2 country, per-country
    postal formats, phone digit count, CJ field-length caps, PO-box and
    missing-house-number rejection, optional country allow-list
  - Reports every problem at once and runs before any CJ call
- [x] **No CJ order for a cancelled order (2026-10-05, PR #12).** `order.confirmed`
  and `order.cancelled` arrive on separate queues; after a backlog the
  cancellation could be handled first, leave nothing behind, and the
  confirmation then submitted (and would have paid) a CJ order for an order
  whose card hold was voided. `cj_order_attempts.cancelled_at` (migration
  `a6d4e2f8c135`) is stamped by every cancellation; the confirm handler checks
  it under the row lock before the CJ request, withdraws a CJ order created
  meanwhile, and the CJ payment service never pays an attempt that has it.
  CJ's code `1600300` ("order not found") is now an authoritative "not at CJ"
  (`CJDropshippingNotFoundError`), so a create that failed (e.g. a 429) is
  submitted again instead of sticking at `creating` until it is dead-lettered.

Schema: `supplier_service` migration `c4a7f1d2e9b8` adds the tracking columns
(it also creates `cj_order_attempts` when absent, since that table had only ever
been bootstrapped by `create_all`).

### 3a. Canada only; CJ goods from China warehouses only — DONE (2026-09-28, sourcing moved US → China 2026-10-02)
- **Selling:** `shared.contracts.shipping_region.CanadianAddress` checks every
  shipping address order-service accepts (order and checkout quote) before it is
  priced: country Canada (a missing one is taken as Canada), a real province or
  territory (stored as its code: Stripe Tax and CJ want `AB`, not `Alberta`) and a
  Canadian postal code (stored as `A1A 1A1`). Anything else is a 422 before any
  money moves. supplier-service refuses a non-Canadian freight quote and CJ order
  again, whatever reaches it.
- **Sourcing:** CJ goods come from CJ's China warehouses only
  (`CJ_WAREHOUSE_COUNTRY_CODE = "CN"`). Every product search sends
  `countryCode=CN`; the catalogue sync replaces CJ's list stock (summed over
  every warehouse) with the China stock per product and per size/colour, and skips
  a product with none; order-time stock checks count only China rows; freight
  quotes and CJ orders ship from `CN`.
- **Why China, not the US (2026-10-02):** CJ has no carrier from its US
  warehouses to Canada. `freightCalculate` gave 0 US→CA options for every
  T-shirt (7 US→US); CJ's Canadian warehouse stocks 1 product in our categories;
  China has 6,000+ products and 16 options to Canada (about USD 4.50–7,
  4–15 days). The original rule (2026-09-28) was US warehouses only, which left
  nothing sellable.
- `CJ_DROPSHIPPING_DEFAULT_FROM_COUNTRY_CODE` (was `CN`) and
  `CJ_DROPSHIPPING_SUPPORTED_COUNTRY_CODES` are gone; the rules live in code.
- **Stock refresh (2026-09-29):** a product that sells out in the warehouse
  country drops out of the country-filtered listing, so the sync alone never zeroed it. An hourly
  supplier-service task (`tasks.stock_tasks.refresh_cj_stock`) now asks CJ about
  every CJ product *we sell* (product-service's `GET /products/stock-keys/{supplier}`,
  supplier-service's signature only) and sends back the sellable US stock per
  variant (CJ's China stock less `CJ_DROPSHIPPING_INVENTORY_BUFFER`) in
  `supplier.stock.updated` batches. product-service sets each variant, the total
  and `in_stock`; `products.stock_checked_at` makes an older measurement a no-op.
  A product CJ could not be asked about keeps its stock. A Postgres advisory lock
  keeps two runs from overlapping. Migration: product `9b4d2e7f1a63`.
  **Trade-off chosen:** the refresh overwrites, so units sold here but not yet
  ordered from CJ are covered only by the buffer; the order-time China check remains
  the final gate. **Since 2026-10-09** CJ's STOCK webhook pushes changes as
  they happen, with this refresh as the backstop (§8.2). **Later:** a live stock
  check at the checkout quote.

### 3c. CJ sandbox for end-to-end tests — DONE (2026-09-28)
`CJ_DROPSHIPPING_SANDBOX=true` creates CJ orders with `isSandbox=1` and pays
them with CJ's `simulatePay` (no wallet balance read or spent); everything
else runs as for a real order. `./local/dev.sh cj-sandbox ship|deliver
<order_id>` plays CJ's shipping and runs a tracking poll. The choice is stored
per order (`cj_order_attempts.is_sandbox`, supplier migration `f3c8a2d6b519`).
**Verified against CJ (2026-10-02):** `confirmOrder` accepts a sandbox order
before `simulatePay`, and `cj-sandbox ship` (status 500) and `deliver` (600)
move a sandbox order through the tracking poll to shipped and delivered. CJ
allows one request per second per account, so the helper waits 1.1s between
calls.

### 3b. Checkout → Stripe → CJ money flow — DONE (2026-09-10)
Branch `feature/checkout-payment-cj-flow`; diagram in `FLOWS.md` →
"Checkout, Payment & CJ Fulfillment Flow".
- [x] **CJ orders are actually paid.** They were created with `payType=3`
  ("create only") and never confirmed or paid, so CJ never shipped anything.
  `CJOrderPaymentService` now runs confirmOrder → cost-ceiling check → balance
  check → payBalance as recorded steps (`CONFIRMED` / `AWAITING_FUNDS` / `PAID`),
  emits `cj.order.paid`, and a taskiq job (`pay_unpaid_cj_orders`, every 5 min)
  retries and gives up after `CJ_PAYMENT_MAX_WAIT_HOURS`.
- [x] **Authorize at checkout, capture after fulfillment is secured.**
  PaymentIntents use `capture_method=manual`; `payment.authorized` gates the
  Saga; capture is requested at confirmation (no CJ lines) or on `cj.order.paid`.
  Pre-capture failures void the hold instead of refunding.
- [x] **Shipping is charged.** Live CJ freight (USD x `CJ_FREIGHT_PRICE_BUFFER`
  x FX) for CJ lines plus `DOMESTIC_FLAT_SHIPPING_CAD` for in-house/catalog
  lines; the order stores subtotal/shipping/tax and the chosen logistic, which
  CJ ships with.
- [x] **CJ USD prices are no longer sold as CAD.** Storefront price =
  max(suggested, cost x `CJ_PRICE_MARKUP_MULTIPLIER`) x `CJ_USD_TO_CAD_RATE`,
  rounded up to .99, stored as `product_variants.retail_price` (backfilled).
- [x] **Order before PaymentIntent.** `POST /checkout` creates the order and
  opens the intent for the order's own `amount_cents`; the client-callable
  `POST /payments/create-intent` is gone, and resuming checks ownership.
- [x] **No money kept without an order.** An authorization/capture for an
  unknown or cancelled order sends `payment.release.requested`.
- [x] **A card decline no longer cancels the order**; the customer retries.
- [x] Cancelling a paid CJ order acks and flags reconciliation instead of
  retrying `deleteOrder` into the DLQ.

Migrations: product `7c3e9a51d2f4`, order `3d8b6f0e2a91`, supplier `e5b21c7d9f60`.
**Before going live:** set `CJ_USD_TO_CAD_RATE` / `CJ_PRICE_MARKUP_MULTIPLIER`
deliberately and prefund the CJ wallet. The Stripe dashboard webhook endpoint
must subscribe to every event the app handles, by name (locally `stripe listen`
forwards everything, so a missing one only shows up in production):
`payment_intent.amount_capturable_updated`, `payment_intent.succeeded`,
`payment_intent.payment_failed`, `payment_intent.canceled`,
`charge.refund.updated`, `charge.dispute.created`, `charge.dispute.updated`,
`charge.dispute.closed`.
**End-to-end run — DONE (2026-10-02, PR #11)** against Stripe test mode + the CJ
sandbox. One CJ T-shirt went the whole way: checkout quote → card authorized →
stock reserved → order confirmed → CJ sandbox order created, confirmed, paid
(`simulatePay`) → card captured (Stripe Tax sale recorded) → shipped →
delivered, with the confirmed / shipped / delivered emails sent. Every service
ended consistent: order `delivered`/`captured`, payment `succeeded` with a tax
transaction, CJ attempt `delivered`. The run found and fixed two blockers:
Stripe webhooks never verified (the gateway re-serialised the signed body; the
handlers read stripe-python 15 objects with `.get()`), and payment-consumer
dead-lettered every message (subscribers typed the already-decoded body as
`str`), so no card was ever captured, voided or refunded.
**Not exercised in that run:** typing a card into the Stripe Payment Element
(the order was placed through `/checkout` and confirmed with `pm_card_visa`,
which is what the Element sends); the refund and cancellation paths; an
in-house custom-print order. (The last two have since been run live, see §5a.)
Stripe Tax is wired in behind `STRIPE_TAX_ENABLED` (off by default, so the
`tax_amount` slot stays 0 until it is switched on — see §5). (Done 2026-09-25:
admin partial refunds, dispute recording and alerts; `STRIPE_SECRET_KEY` rename — old name still loads; live USD/CAD from the Bank of Canada, cached, with `CJ_USD_TO_CAD_RATE` as fallback and `CJ_FX_SOURCE=fixed` to opt out.)

### 4. Security & config hardening (2026-09-09)

Audited live against the running stack, not just read. Four exploitable
authorization holes were found and fixed; two config items turned out to be
already correct; three remain.

- [x] **Host-header validation, and a total user-service outage.** user-service
      had the newest, strictest middleware — an allowlist with no internal-mesh
      case — so every gateway-forwarded request was answered `400 Invalid Host
      header`. Login, registration, activation and `/me` were all unreachable
      through the gateway. The other seven services had the opposite problem:
      they bypassed validation entirely for any RFC-1918 client, which accepts
      any Host header at all from inside the network; supplier-service had no
      validation whatsoever.
      All nine now share `shared/middleware/host_validation_middleware.py`,
      which allowlists public hosts plus the container DNS names services
      legitimately address each other by (`INTERNAL_ALLOWED_HOSTS`). `/health`
      and `/metrics` stay exempt for probes. Verified: register→activate→login
      works through the gateway, a forged Host is refused on all nine ports.
- [x] **IDOR: any user could read and modify any other user's notifications.**
      `GET /notifications/users/{user_id}`, `.../unread-count` and
      `PATCH .../read-all` took the subject from the path and required only
      *authentication*. Now behind an ownership check (403 verified).
- [x] **Review impersonation.** `POST /products/{id}/users/{user_id}/reviews`
      was unguarded, so any authenticated user could post a review attributed
      to someone else. Now ownership-checked (403 verified).
- [x] **Authorization sourced from attacker-controlled input.** The review
      `PUT`/`DELETE` routes used `Depends(require_user_or_admin)`, but that
      helper takes the caller as its *first argument*: FastAPI therefore
      resolved `current_user` from the **request body** and `target_user_id`
      from the **query string**. A caller could simply assert
      `{"current_user": {"role": "<admin>"}}` and pass. Replaced with a
      `path_user_or_admin` dependency that takes the subject from the path and
      the caller from the validated token, so neither is forgeable.
- [x] **JWT `purpose`-claim bypass is genuinely fixed.** Verified by forging
      tokens with the real signing key: a token with no `purpose` claim is
      rejected, and refresh↔access reuse is rejected in both directions.
- [x] **CORS is already correct** — explicit origin list (not `*`), so
      `allow_credentials=True` is safe; a foreign origin gets no
      `access-control-allow-origin` and is blocked by the browser. Production
      only needs the real domain added to `CORS_ALLOWED_ORIGINS`.

- [x] **Session revocation is now immediate.** `token_version` was bumped and
      checked by user-service, but the gateway — which authenticates every
      request that never reaches user-service — only *decoded* the token, so a
      password reset left stolen access tokens working for their remaining
      20-minute lifetime. A shared `SessionRegistry` (its own Redis DB, written
      by user-service, read by the gateway) now carries the current session
      generation. Verified live: after a reset the old token is refused on
      `/me`, `/notifications/...` and `/wishlists/me`, while a fresh login
      works. Refresh-token *reuse* — the signature of a stolen token — now also
      bumps the generation, not just the refresh family.
- [x] **The remaining notification IDORs are closed.** `PATCH
      /notifications/{id}/read` and `DELETE /notifications/{id}` are keyed on
      the notification id, so the gateway could not check ownership. The
      gateway now asserts the caller (`X-Authenticated-User-*`, stripped from
      inbound requests so it cannot be forged) and notification-service uses it
      to answer the ownership question its service layer already knew how to
      ask — that check had been dead code, because no route ever passed
      `requesting_user_id`. It now **fails closed**: no identity means refuse.
- [x] **Per-user rate limiting.** Buckets key on the authenticated user when
      there is one, falling back to the resolved IP for anonymous traffic.
      Keying only on IP meant everyone behind one NAT or mobile carrier shared
      a bucket and throttled each other, while one account could spread abuse
      across addresses. Verified: two signed-in users from one address get
      separate buckets.
- [x] **HTTPS was already configured** — `web`→`websecure` permanent redirect,
      ACME HTTP-01, and HSTS/nosniff/frameDeny/referrer-policy applied globally
      were all in place; the gap note was stale. What was genuinely broken:
      `acme.json` was mode `0644`, and **Traefik refuses to use it unless it is
      `0600`**, so the first production certificate issuance would have failed.
      Set locally — but git records only the exec bit, so a fresh clone arrives
      at `0644` again; `chmod 600 traefik/acme.json` is now documented in
      `traefik.yml` as a per-machine step and belongs in the deploy script.
      Going live is otherwise only: `TRAEFIK_ENTRYPOINT=websecure`,
      `CERT_RESOLVER=letsencrypt`, plus a real `DOMAIN` and `ACME_EMAIL`.
- [x] **Input bounds.** Review `comment` was unbounded, so one request could
      push an arbitrarily large blob into the database; it is now capped at
      5,000 characters. Nothing bounded request size at all, so a new Traefik
      `limit-body-size` middleware caps bodies at 12 MB at the edge, ahead of
      the application. (SQL injection is not a live risk here — every query
      goes through Pydantic then parameterised SQLAlchemy, and `sort_by` is
      validated against the model.)
- [x] **Provider secrets no longer leak, and can now be withheld.** Stripe, CJ,
      OpenRouter and AdminJS keys are `SecretStr` and optional, unwrapped only
      at the point of use through accessors that fail loudly by name when a
      service was started without a secret it turns out to need. They no longer
      render in a log line, a traceback, or a settings dump — verified:
      `repr()` shows `SecretStr('**********')` and `model_dump()` no longer
      contains the key.

**Still open in §4 — one item, and it is an infrastructure decision:**
- **Every service is still *given* every secret.** All 33 compose services load
  the same blanket `.env`, so each process still receives keys it never uses.
  Making the fields optional above is the prerequisite that now makes
  withholding possible — a service that never charges a card can start without
  the Stripe key. What remains is splitting secret distribution per service
  (and choosing a secret manager: Vault, AWS Secrets Manager, SOPS...). That
  changes how the application is deployed and run, so it wants a deliberate
  choice rather than being decided in passing. The usage map is narrow:
  Stripe → payment, OpenRouter → product (+ its taskiq worker),
  CJ → supplier (+ its worker/scheduler), mail → notification (+ its worker),
  Google OAuth → user.

### 4b. Gateway auth follow-ups, generation access, background removal (2026-09-24)

Worked from the bug list below and verified live against the running stack
(anonymous / signed-in user / admin, through the gateway and directly against
the services), not only in unit tests.

- [x] **Wishlist was unusable.** `wishlist_service` read the caller from
      `request.state.current_user`, which only exists inside the gateway
      process, so every `/wishlists/me` call raised. It now reads the
      gateway-asserted `X-Authenticated-User-*` headers via
      `AuthenticatedCaller.require()`. Its tests had overridden the dependency
      wholesale, which is why they never caught it; a new test drives the real
      dependency with real headers.
- [x] **Access tokens were written to the logs.** The gateway logged every
      forwarded request's headers (Cookie, Authorization) at INFO. It now logs
      header names only.
- [x] **Public-route matching was a raw string prefix.** `startswith` made
      `/products-export`, `/login-as-admin`, `/payments/webhook/replay`,
      `/healthz`, … public. `PUBLIC_ENDPOINTS` is replaced by
      `api_gateway/middleware/public_routes.py`: `PublicRoute` value objects
      with an `EXACT` / `TREE` / `CHILDREN` scope matched on segment
      boundaries, plus a `protected` carve-out list that overrides the trees.
- [x] **Admin-only response replayed to anonymous users.** `/shipping/methods/all`
      is admin-guarded in its route, but it sat under the public
      `/shipping/methods` tree — and the gateway caches public GETs for every
      caller, so an admin's response was served from cache to anyone. It is
      now a protected carve-out. See the open cache item below.
- [x] **Image generation is signed-in only.** It spends paid provider credit and
      was open to anonymous callers. Gateway and product-service both require
      a caller; the quota is per user (`PRODUCT_IMAGE_GENERATION_LIMIT` /
      `_WINDOW_HOURS`), and a job is visible only to its owner (another user
      gets 404, so job ids cannot be probed). The guest cookie/quota code and
      `UserContextResolver` are gone — the resolver had the same
      `request.state` bug, so even signed-in users were counted as guests.
      Response field `guest_limit` → `generation_limit`. The frontend shows
      "Sign in to generate" to guests and sends the token on status polls.
- [x] **AdminJS schemas are admin-only.** They were public at the gateway, and
      only user-service checked the role. Gateway, product-service (products,
      categories, images, reviews) and order-service now all require an
      admin; `/admin/schema/products` did not exist and was added. admin-js
      loads the schemas with the admin's token right after login
      (`schema-registry.ts`) and re-decorates each resource, falling back to
      the first data request for sessions that outlive a restart.
- [x] **Nobody could be an admin.** `users.ck_users_role` allows only
      `user`/`admin`, but every check compared against `SECRET_ROLE`, set to
      something else. Resolved by `SECRET_ROLE=admin`; `TEST_ADMIN_ROLE`
      (which had the old value hardcoded in `shared/settings.py`) is `admin`.
- [x] **Login was case-sensitive.** Registration stores emails lowercased;
      login compared them verbatim, so a differently-cased email read as a
      wrong password. `authenticate_user` now normalises the same way.
- [x] **Generated artwork kept its backdrop.** Image models ignore
      transparency requests, so designs printed as a solid rectangle. A
      `BackgroundRemover` step (rembg, `isnet-general-use`) now cuts the design
      out between the provider and storage; the job fails rather than store an
      empty or resized cutout. The model is set explicitly because rembg's
      default, `bria-rmbg`, is non-commercial. Verified live: 4096×4096 RGBA
      at 300 DPI with a transparent backdrop. OpenRouter model switched to
      `google/gemini-3.1-flash-image-preview`, the flash model that supports
      the 4K size the print minimum requires.

- [x] **Gateway cache is opt-in per route.** The cache key ignores the caller,
      and every public GET used to be cached — so any public route whose answer
      depends on the caller would leak the way `/shipping/methods/all` did.
      Caching now requires `PublicRoute(cacheable=True)` (products, categories,
      customization pricing, shipping methods); new public routes are not
      cached by default. The dead "cache unauthenticated protected GETs"
      branch is gone. Verified live: pricing is cached and served from cache,
      admin/per-user routes never reach the cache.
- [x] **Failed generations give their quota back.** The quota is spent at
      submit; a job that ends `failed` now refunds its owner through an atomic
      Redis script that never goes below zero and keeps the window's TTL.
      Verified against real Redis, not a mock.
- [x] **rembg model baked into `Dockerfile.worker`.** `isnet-general-use`
      (~170 MB, md5-checked) is downloaded at build time into
      `U2NET_HOME=/opt/rembg`, so the first job no longer pays for it. The
      `REMBG_MODEL` build arg must match `PRODUCT_IMAGE_BG_REMOVAL_MODEL`.

**Still open from this pass:**
- **admin-js** runs under `dev.sh` now (2026-09-28, `./local/dev.sh up admin-js`,
  :3001). It checks its configuration at startup: `backend/.env` was missing
  `COOKIE_SECRET`, `ADMINJS_SERVICE_REDIS_DB` and `ADMINJS_SERVICE_REDIS_PREFIX`,
  so it could not have worked under compose either. Its token refresh is
  done since 2026-10-10 (§8.4).

### 5. Payments & tax/legal
- [x] Partial refunds (2026-09-25). `POST /admin/orders/{id}/refunds` refunds
  chosen lines and optionally shipping, never above what was captured. Before
  capture the card is simply charged less (`amount_to_capture`); after capture
  a Stripe refund is keyed on the refund id, so a redelivery never refunds twice.
- [x] Disputes (2026-09-25). `charge.dispute.created/updated/closed` are stored in
  `payment_disputes`, the order gets a `dispute_status`, and `ADMIN_ALERT_EMAIL`
  is emailed. Nothing is decided automatically: evidence goes in through the
  Stripe dashboard.
- [x] Stripe Tax (2026-09-26), behind `STRIPE_TAX_ENABLED` (default off).
  order-service prices the lines + shipping, then asks payment-service
  (`POST /payments/tax/calculate`, order-service's signature only) for a Tax
  Calculation; the tax is added on top (prices are tax-exclusive) and the
  calculation id is stored on the order and the payment. At capture
  payment-service records the sale transaction, reversing whatever was taken off
  before capture; every refund after capture records a flat-amount reversal. A
  partial refund gives back the refunded part's share of the tax, and the last
  refund takes whatever tax is left, so rounding never strands a cent. Recording
  failures never undo money movement: they are logged `TAX RECORD REQUIRED`.
  Migrations: order `d4a9c6e1f305`, payment `c5e2a8d4b716`.
  **Before switching it on:** add the tax registrations in the Stripe dashboard
  (Stripe only taxes where you are registered; every calculation is billed) and
  set `STRIPE_TAX_PRODUCT_TAX_CODE` (t-shirts: `txcd_30011000`). The shipping
  address needs `country_code` whenever tax is on.
  **Not covered:** a lost dispute records no tax reversal (record it in the
  dashboard); VAT / customs on non-Canadian destinations.
- [x] Partial refunds reach payment-service (2026-09-26). order-service had no
  outbox route for `payment.refund.requested`, so every partial refund since
  2026-09-25 sat in the outbox, retried and never sent. Routed now; a guard test
  checks every event type written to the outbox has a route.
- [x] Customer returns (2026-09-26, backend only). A customer asks for delivered
  units back (`POST /orders/{id}/returns`, multipart: a JSON `request` field plus
  up to 5 photos, JPEG/PNG/WebP checked from their bytes); an admin approves,
  receives or rejects (`/admin/returns`). Rules, under the order's saga lock:
  owner only, confirmed order, delivered line, within `RETURN_WINDOW_DAYS` (30)
  of that line's `delivered_at`, and each unit at most once (refunded units and
  units in an open return are taken). The reason decides the fault: the seller's
  (defective / damaged / wrong item / misprint) needs a photo and refunds the
  order's shipping once; a change of mind (changed mind / does not fit) does not.
  Per fulfilment type: custom prints only for the seller's fault and never sent
  back; CJ defects not sent back (claim from CJ by hand), CJ change of mind sent
  back to the local address; catalog items always sent back. Returnless lines
  are refunded on approval, the rest on receipt, always through
  `OrderRefundService`, so its caps hold. The admin is emailed about each request
  (`ADMIN_ALERT_EMAIL`); the customer is emailed the decision with
  `RETURN_ADDRESS` when goods must come back. Photos are private
  (`RETURN_EVIDENCE_ROOT`, never under `MEDIA_ROOT`), admin-only to view.
  Email templates are now autoescaped. Migration: order `e7b3c1f9a482`.
  **Before going live:** set `RETURN_ADDRESS` and `ADMIN_ALERT_EMAIL`; publish the
  returns policy page (below) with the same rules.
  **Not covered:** the frontend (return form, admin queue, regenerated types);
  prepaid return labels; store credit; restocking a received catalog item
  (adjust stock by hand); photos of a request that fails to commit stay in
  storage. (S3 for the photos: done in §8.3.)
- [x] Refund and cancellation fixes (2026-10-05 to 2026-10-07), all found by
  running the paths live; details in §5a:
  - **PR #12:** the `charge.refund.updated` webhook marked the whole payment
    refunded on any refund, so after one partial refund the customer was told
    the payment was refunded and every later refund was refused. The app's own
    refunds now carry Stripe metadata (`refund_origin=payment-service`) and are
    left alone; a refund made in the Stripe dashboard is recorded once, by
    Stripe refund id (`StripeRefundWebhookService`). payment-service's outbox
    also had no route for `payment.refund_failed` (a refused refund stayed
    `requested` in order-service) or for `payment.dispute_opened` / `_closed`
    (no dispute alert was ever sent); all routed, with a guard test like
    order-service's.
  - **PR #13:** a payment refunded down to zero after a pre-capture reduction
    stayed `succeeded`; it is now `refunded` once `refundable_cents` is 0.
  - **PR #15:** every `payment.refunded` carries a `refund_scope` (part / rest /
    whole), so the customer reads "Part of your payment...", "The rest of your
    payment..." or "...refunded in full" instead of "Part of" for everything.
    The order-cancelled email (`order_cancelled.html`) was a heading and a
    footer under the subject "Refund Initiated"; it now gives the reason and
    what happens to the money, with a separate wording when goods were already
    made or posted.
- Terms / privacy / returns policy pages
- GDPR data export + delete, audit logging, data retention (checklist §13 fully unchecked)
- AI-print content moderation — you physically print user designs, so IP / trademark / NSFW
  screening is genuine liability, not optional

### 5a. Refund and cancellation paths — verified live (2026-10-05, 2026-10-07)

Every path below was run against Stripe test mode and the CJ sandbox, through
the gateway, as a real customer and admin; the bugs the runs found are the
fixes listed in §5 and §3. The flows are drawn in
`docs/refund-and-cancellation-flows.excalidraw` (one row per path, trigger to
outcome, coloured by service).

- **Cancellations:** before paying (intent cancelled); after authorization
  (hold voided, stock released); an order CJ was paid for (409); the 24-hour
  stall sweep (cancel + void); cancel and confirm out of order (no CJ order).
- **Refunds:** admin refund before capture (card charged less: 2874 of 4873)
  and after capture; over-refund attempts (422); a refund payment-service
  refuses (`payment.refund_failed`); a refund made in the Stripe dashboard; a
  custom line cancelled before printing (line + shipping refunded, customer
  emailed).
- **Returns and disputes:** a defect (returnless, unit + shipping refunded on
  approval); a change of mind (sent back to `RETURN_ADDRESS`, refunded on
  receipt); a dispute opened and closed won (recorded, order flagged, admin
  alerted, nothing refunded automatically).
- **Supplier-side:** CJ rejecting an address before any CJ call
  (`cj.order.failed` -> cancel -> void).

**Not exercised:** fully refunding an already-charged order by cancelling it
(`PaymentService.handle_payment_refund` on a succeeded payment) needs a product
sold from local stock; only CJ products exist locally.

**Open follow-ups:**
- `cj_api_client` has no shared limiter for CJ's one-request-per-second limit:
  handlers calling CJ at the same moment get 429s (the cancellation-race order
  on 2026-10-05 failed its create this way). PR #12 makes such a create recover
  on retry, but each 429 still costs a retry.
- 10 old messages sit in `taskiq.notifications.dead_letter` (from before
  PR #11); replay or discard them.
- After any change to `shared/contracts/events.py`, restart every process of
  the publishing service, outbox worker included: it rebuilds each event from
  the contract before publishing, and a stale one drops new fields silently
  (seen with `refund_scope` on 2026-10-07).

### 6. Frontend completeness
- No user account/profile page, address book, order-tracking detail page
- No wishlist UI (the service exists, no page)
- The "designer" is a single Hero panel — a sellable product likely needs real placement /
  sizing / per-variant (color) mockups
- Loading/error states, mobile polish

### 7. Testing & docs
- All ten service suites pass (1,621 tests on 2026-10-10: gateway 228, user 174,
  product 321, supplier 230, order 282, payment 134, cart 62, wishlist 27,
  shipping 44, notification 119; `shared` 50), but **nothing runs them**: there is no CI, so
  every PR so far was merged with only GitGuardian checking it.
- The suites no longer depend on the local configuration: order-service's
  tests pin `STRIPE_TAX_ENABLED=false` in `tests/conftest.py` (with Stripe Tax
  on locally, 69 of them used to fail). Tax pricing keeps its own tests with
  explicit settings in `test_order_pricing_service.py`.
- No coverage reports, no inter-service contract tests
- No *automated* end-to-end buy-flow test (manual live runs passed — see §3b, §5a),
  no security testing (OWASP ZAP etc.)
- No per-service READMEs, no overall architecture diagram (the refund and
  cancellation flows are drawn, §5a), OpenAPI not curated/published

### 8. Planned next (added 2026-10-07)

Worked one at a time, in this order. Each entry says what exists today and the
approach; decisions are recorded here as they are made.

1. **Secrets in HashiCorp Vault.** Today every process reads the same single
   configuration file, so each one is given every secret (§4, last item).
   Approach: Vault's KV v2 engine with one path per service
   (`secret/ecommerce/<service>`) and a policy per service; each service signs
   in to Vault with its own AppRole at startup and can read only its own path.
   `shared/settings.py` gains a Vault settings source that takes precedence
   over the file. Locally, `dev.sh` runs Vault like Postgres and Redis. This
   also unblocks bug list #19: Vault's database secrets engine can issue each
   service its own short-lived Postgres user.
   **Status: live since 2026-10-08.** The owner ran the import (17 secrets, plus
   the two observability ones) and restarted the stack; verified: all 36
   processes up and ready, each Python process holding only its Vault identity
   (no secret in its environment), admin-js only its two keys, all ten suites
   and `shared`'s passing through `dev.sh test`, and a live checkout (login,
   card authorization, CJ sandbox order, capture, emails) on Vault-held secrets.
   Decisions:
   a persistent local Vault run by `dev.sh` (file storage under
   `backend/local/data/vault`; unseal key and root token in
   `backend/local/run/vault/init.json`); static secrets now, per-service
   Postgres users as the next step; the import is a script the owner runs
   (`./local/dev.sh vault import`), so values never pass through anyone else;
   Vault only, with no fallback to the file.
   - `shared.vault`: `VaultClient` (AppRole sign-in, KV v2 reads) and
     `VaultSettingsSource`, which `Settings` reads after real environment
     variables and before the file. Per-service secrets became optional
     fields, each raising a named error where it is used; only the three
     infra passwords stay required.
   - `dev.sh`: `vault up|down|status|import`; the infra commands read the
     infra passwords from Vault; every Python process (services, workers,
     migrations, the dlq and cj-sandbox tools, and `dev.sh test`) gets its own
     AppRole; admin-js (Node) gets its secrets exported by `dev.sh`.
   - Paths: `shared-infra` (Postgres/Redis/RabbitMQ passwords), then one per
     service (signing keys, Stripe, CJ, OpenRouter, mail, artwork secret;
     `COOKIE_SECRET` for admin-js). A role reading another service's path
     gets 403 (checked against the real Vault).
   - Two more paths, read by no local process (root token only): `tooling`
     (pgAdmin, an unused AdminJS token) and `observability` (Alertmanager's
     Telegram token, Grafana's secret key). `Settings` hides its input in
     validation errors, which would otherwise print part of it, secrets included.
   - Not covered yet: compose (its containers would need Vault Agent), the
     frontend's own secrets, and Redis/RabbitMQ users per service. All three
     infra passwords sit in one path that every service may read, until the
     per-service database users step.
2. **CJ stock webhook.** §3a listed it as "Later": CJ's STOCK webhook pushes
   stock changes instead of the hourly refresh pulling them.
   **Status: live locally since 2026-10-09** (branch `feature/cj-stock-webhook`).
   Decisions: the openId CJ signs with is a Vault secret
   (`CJ_DROPSHIPPING_OPEN_ID`, supplier-service's path), not fetched at runtime;
   locally a cloudflared quick tunnel; PRODUCT/VARIANT pushes are acknowledged
   and logged only; the hourly refresh stays as the backstop.
   - What CJ offers (docs, 2026-10): `POST /webhook/set` registers one public
     HTTPS URL per topic (product, stock, order and logistics are required in
     every call); STOCK pushes come only for products subscribed one by one
     (`/webhook/product/subscribe`, 100 per call, 1,000 at account level 1;
     subscribe-all was withdrawn in July 2026), and subscribing needs the
     product topic on. Each push carries `sign` = Base64(HMAC-SHA256(openId,
     raw body)). CJ wants a 200 within 3 s and switches a topic off after two
     hours below 80% success.
   - Gateway: public `POST /api/v1/cjdropshipping/webhook`, body forwarded byte
     for byte (as for Stripe). supplier-service verifies `sign` (401 otherwise),
     then a STOCK push becomes the same `supplier.stock.updated` event the
     refresh sends: China rows only, buffer held back, variants mapped to their
     product. A variant with no China row is left alone, not zeroed. Any push
     that verifies is answered 200, even one we cannot read, so CJ never
     switches the topic off over it.
   - Subscriptions: `cj_stock_subscriptions` + `cj_stock_subscription_variants`
     (supplier migration `b8e3f1a6c274`), kept equal to what product-service
     sells by the hourly `reconcile_cj_stock_subscriptions` task (at :30, clear
     of the refresh).
   - `dev.sh cj-webhook tunnel | tunnel-stop | store-open-id | subscribe | status`.
     A quick-tunnel URL changes every run: re-run `tunnel` after a restart.
   - **Verified live (2026-10-09):** CJ's registration sends one signed test
     push per topic; all four verified and the STOCK one parsed. 26 products
     subscribed. A STOCK push through the public tunnel reached product-service
     (`1 updated`). Subscribing a product twice is a success at CJ, not the
     failure its docs suggest. CJ names the logistics topic `LOGISTIC`.
   - Found on the way: the first `store-open-id` captured the tool's stdout,
     log lines included, and stored them in Vault around the openId (every push
     then got 401). The openId now goes only into a private file dev.sh
     creates, and must be digits.
   - **Before production:** register the real public gateway URL
     (`cj-webhook enable https://<domain>`); a genuine stock change has not
     been seen yet, only CJ's test pushes and ours. CJ also answered the failed
     registration with code `1600300`, which the client maps to "order not
     found": that mapping holds only for order calls.
   - Not covered: acting on PRODUCT/VARIANT pushes (delisting, off sale);
     deduplication by `messageId` (levels are absolute, so a repeat is
     harmless, but a late retry can briefly overwrite a newer level until the
     next push or refresh).
3. **S3 for images.** Generated designs could already be stored in S3
   (`ARTWORK_STORAGE_BACKEND=s3`) but ran on local disk; CJ product images
   were hotlinked from CJ's CDN, so a CJ change or outage broke the catalogue;
   return photos, admin uploads and category icons were on local disk (uploads
   stored as absolute file paths).
   **Status: live locally since 2026-10-09** (branch `feature/s3-images`).
   Decisions: SeaweedFS as the local S3 server, run by `dev.sh` (Homebrew's
   `minio` is deprecated, its upstream archived); two buckets, never mixed
   (public-read catalogue; private for designs and return photos); the
   database stores catalogue *keys* and responses add the public origin; all
   four kinds of image in scope.
   - Settings: `OBJECT_STORAGE_BACKEND` (old name `ARTWORK_STORAGE_BACKEND`
     still read), `AWS_S3_CATALOGUE_BUCKET`, `AWS_S3_CATALOGUE_PUBLIC_BASE_URL`,
     `AWS_S3_PRIVATE_BUCKET` (old name `AWS_S3_ARTWORK_BUCKET`), and
     `AWS_S3_ACCESS_KEY_ID` / `AWS_S3_SECRET_ACCESS_KEY` for S3-compatible
     servers only (Vault, per service; AWS uses the workload role).
   - product-service: `storage/` is the only place boto3 is built
     (`ObjectStore` with S3 and local adapters, `ObjectStorageProvider`,
     `CatalogueImageUrl` for response schemas). Generated designs, print-file
     downloads and admin uploads go through it; uploads are typed from their
     bytes (JPEG/PNG/WebP), size-capped, and stored under fresh keys.
     `utils/image_processing.py` is gone (it also stored the first character
     of the path as a category's icon on update).
   - CJ images: `catalogue_image_mirrors` (product migration `c2f8a4d1e7b9`);
     a 15-minute task on a new `product-taskiq-scheduler` copies every CJ URL
     still in use and rewrites `products.image_url`, `product_images` and
     `product_variants.variant_image` to the copy's key, in the transaction
     that records it; the supplier sync translates CJ URLs through the table,
     so a re-sync keeps the keys. Fetches are HTTPS on `*.cjdropshipping.com`
     only, no redirects, size-capped (SSRF). A failure keeps the CJ URL, is
     retried 15 min, 30 min, ... up to a day apart and given up on after 10.
     `dev.sh images mirror` runs it now.
   - order-service: `S3ReturnEvidenceStorage` under `return-evidence/`. The
     admin photo route keeps streaming the bytes rather than handing out
     presigned links, unlike the approach above: a link works for anyone it
     is forwarded to, the route checks the admin every time.
   - `dev.sh`: SeaweedFS in `infra up/down/status` (S3 on :8333); keys for
     product- and order-service, the admin pair and the at-rest encryption key
     are generated into Vault on first start, and each service's key may touch
     only its bucket or prefix. `storage status | import-local`. Test suites use
     their own `-test` buckets.
   - Frontend: `next.config.js` allows the S3 origin (`CATALOGUE_IMAGE_HOST`
     for the CDN) and lifts Next 16's private-IP image guard in development
     only.
   - **Verified live (2026-10-09):** all 126 CJ images copied (~58 s), no CJ URL
     left in the catalogue, the storefront loads every image from :8333 and
     none from CJ; a re-sync keeps the keys; the 4 existing designs and 1
     return photo copied in by `import-local`, and a stored design downloads
     through a presigned link (SHA-256 matches its manifest; unsigned GET 403).
     All ten suites and `shared` pass (1,627 tests), with the new storage tests
     against the real SeaweedFS (private bucket not public, cross-service keys
     refused, wrong checksum refused).
   - Not exercised live: a new design generation (spends provider credit) and
     an admin upload through the UI (needs an admin session); both paths are
     covered by tests against the stores.
   - **Before production:** create the two buckets and roles as in
     `product_service/ARTWORK_STORAGE.md`, put CloudFront in front of the
     catalogue bucket and set `AWS_S3_CATALOGUE_PUBLIC_BASE_URL` and the
     frontend's `CATALOGUE_IMAGE_HOST`; compose has none of the new settings.
   - Not covered: deleting catalogue objects no product uses any more (keys
     are shared between products, so it needs a reference sweep); the local
     media files are left in place until you delete them.
4. **AdminJS: token, security, coverage.** AdminJS signed in with the
   admin's password alone and kept only the 20-minute access token in a 1-hour
   session (it stopped working part-way through), and managed only users,
   products, categories, images, reviews and orders.
   **Status: live locally since 2026-10-10** (branch `feature/adminjs-passkeys`).
   Decisions: the second factor is a **passkey (WebAuthn)**, checked by
   user-service and required for every admin login by any route; **AdminJS is
   the one back office** (the Next.js `/admin` pages are removed); every
   resource listed is covered; admin-js is **private only** (never routed
   publicly); the first passkey comes from an **owner-run one-time link**, which
   is also the recovery path.
   - **Passkeys (user-service).** `webauthn_credentials` (user migration
     `a3d7f2c9e614`; public keys only), py_webauthn. Sign-in is password, then
     passkey: `POST /login/passkey/options` checks the password and issues a
     single-use challenge; `/login/passkey/verify` checks the signature, origin,
     RP id, user verification (PIN/biometric) and the sign counter (a clone is
     refused) before any token exists. Enrolment: `./local/dev.sh admin enrol
     <email>` prints a 15-minute link (token in the URL fragment, spent only on
     success); `admin list`, `admin revoke <email> <id>` (also ends every
     session). Settings: `WEBAUTHN_RP_ID` (default `localhost`),
     `WEBAUTHN_ORIGINS`, `ADMIN_PANEL_URL`.
   - **No admin token without a passkey.** `SessionIssuer` is now the one place
     user tokens are minted, and stamps `amr` (`pwd`, `google`, `webauthn`),
     carried through every refresh. Password and Google sign-in refuse admin
     accounts (403); a refresh never mints an admin token for a session that
     lacks `webauthn` (also covers a user promoted while signed in); the gateway
     refuses any admin-role token without it, which covers every service.
   - **Gateway `/refresh` and `/logout` fixed.** Both set or cleared their
     cookies on FastAPI's injected `response` and then returned a new one, so
     FastAPI dropped them: `/refresh` set no cookie and put the rotated refresh
     token in the body (the next refresh then read as theft and ended every
     session), `/logout` cleared nothing. One `_signed_in_response` now builds
     every sign-in response; the refresh token is cookie-only.
   - **admin-js.** Tokens never reach the browser: AdminJS renders
     `currentAdmin` into every page (`window.REDUX_STATE`), and the access token
     used to be in it. They live in Redis (`AdminTokenStore`) under an opaque
     `sessionRef`, refreshed two minutes before expiry, serialised in-process and
     by a Redis lock (two requests refreshing with one rotating token would look
     like theft). A gateway 401 ends the session. Session cookie HttpOnly +
     SameSite=Strict, rolling 30-minute idle and 8-hour absolute limit
     (`ADMIN_JS_SESSION_IDLE_MINUTES` / `_MAX_HOURS`), new session id at
     sign-in, `frame-ancestors 'none'` and related headers, no-store, listens on
     127.0.0.1 (`ADMIN_JS_LISTEN_HOST`). No more logging of request params,
     records or tokens. Unused TypeORM/pg dependencies removed.
   - **Coverage.** `shared.admin.admin_tables` builds paged, filterable,
     admin-only list/detail/field-schema routes from a response schema; used for
     payments, payment refunds, disputes (payment-service), orders, order items,
     refunds (order-service), CJ orders, supplier syncs, supplier configs
     (supplier-service, plus a narrow PATCH: active, interval, name, category),
     shipments, notifications; the gateway maps each to its service
     (`routes/admin_table_routes.py`). AdminJS resources for all of them, in
     Orders / Payments / Catalogue / Suppliers / Customers. Money and fulfilment
     rows are read-only; they change only through workflow actions that call
     the services' own endpoints: refund (lines, quantities, shipping), cancel
     order, approve / receive / reject a return, every print-queue step
     (start, printed, ship with tracking, delivered, hold, resume, cancel),
     sync a supplier now. Views: print file (preview, download), printable
     packing slip, return photos (streamed through admin-js per request; no
     shareable link).
   - **Found on the way:** the artwork route also required the caller's IP to
     start with `10.`/`172.`/`192.168.` (Docker's network), so since the move to
     native dev every print-file request from order-service was refused; the
     signed order-service assertion is the check now, and the IP test is gone.
     `GET /images` took no paging and returned the first 50 of every product's
     images on every page; it takes `limit`/`offset` now (newest first).
   - **Verified live (2026-10-10)** in Chromium with a CDP virtual authenticator
     (user verification on): enrolment by link (link spent; cross-origin post
     refused), wrong password stops before any prompt, passkey sign-in, no JWT
     anywhere in the page, two concurrent near-expiry requests made exactly one
     refresh (rotated, `amr` kept), `admin revoke` ended the open session at its
     next request, password-only admin login 403 at the gateway, logout revoked
     the refresh token. Every resource lists; the refund form loads the order's
     lines and shows the service's refusal; supplier interval edited and
     restored; return photo and print file render; Images pages by 10. Tests: +44 (passkeys over
     HTTP with a software authenticator that signs with a real P-256 key,
     gateway cookies and the passkey rule, admin tables, supplier config PATCH,
     image list paging).
   - **Not exercised live:** a refund, return decision or print step that
     moves money or goods (the forms and refusals were; the endpoints have their
     own tests and live runs, §2, §5a); a real (non-virtual) authenticator.
   - **Before production:** set `WEBAUTHN_RP_ID` / `WEBAUTHN_ORIGINS` /
     `ADMIN_PANEL_URL` to the host admin-js is reached on (with an SSH tunnel,
     `localhost:3001` works as is), enrol each admin with `dev.sh admin enrol`
     (or the same tool in the user-service image), keep admin-js off Traefik
     (compose now publishes it on 127.0.0.1 only, production included).
   - Not covered: no automated tests for admin-js itself (no runner); no full
     CSP (AdminJS needs inline scripts); the frontend's `npm run lint` is broken (`next lint` is gone in
     Next 16, and there is no ESLint config).
5. **Remove `shared/`.** It holds 83 modules, installed into every service as
   an editable path dependency and imported from about 405 files. Deliverable
   first: a plan saying where each part moves. Code used by one service goes
   into that service. Event contracts become a small versioned package, or each
   consumer keeps its own copy. The infrastructure layers (messaging, outbox,
   database base classes, settings) are placed case by case.

---

## Rough priority order

1. CI/CD + automated migrations + backups (CI first: the suites are green and
   self-contained, so a workflow only has to run them)
2. ~~In-house production-queue admin tooling~~ (done — see §2)
3. ~~HTTPS / CORS / rate-limit hardening~~ (done — see §4); secret
   *distribution* per service + a secret manager is the one §4 item left
4. ~~CJ shipping quotes + tracking + failure handling~~ (done — see §3)
5. AI content moderation (design generation works end to end, so unscreened
   designs can reach the printer), legal pages, GDPR. Tax is wired in (§5);
   it needs the Stripe registrations before going live
6. Frontend account / tracking / designer polish (checkout shipping options
   are done — see §3b)
7. ~~Finish gateway auth (bug list 1, 2b/5/6, 4, 9) and the reliability items
   (12–20) below~~ (done — only #19, per-service Postgres roles, is left)
8. Refund and cancellation paths (done and verified live — see §5a); the CJ
   rate limiter is the open follow-up

## Bug list — triage (2026-09-24)

Backend:

| # | Question | Status |
|---|---|---|
| 1 | Is the token decoded twice (gateway `AuthMiddleware` and user-service)? | **Done (2026-09-24).** Only the gateway decodes it; user-service reads the gateway's signed caller assertion and checks the account row |
| 2 | Gateway strips auth and injects identity headers? | **Done (2026-09-24).** `Authorization` and `Cookie` stop at the gateway; identity travels only as the signed assertion |
| 2b | Signing key out of the gateway, like Google login? | **Done (2026-09-24).** User tokens are EdDSA, private key in user-service only; the gateway signs 60s method+path-bound caller assertions (`X-Caller-Assertion`) that services verify with its public key |
| 3 | `@public` decorator? | Superseded: `PublicRouteRegistry` (§4b). Secure-by-default router-level dependencies would remove the middleware entirely |
| 4 | `self_or_admin` in the services? | **Done (2026-09-24).** `shared.auth.route_guards` on every non-public route; also closed payment/shipment reads by any user and an unguarded `GET /payments` |
| 5 | Only the gateway may call services (`INTERNAL_HMAC_SECRET`, Vault)? | **Done (2026-09-25).** Only the gateway can assert a user; the three routes order-service calls directly (`/artwork/download-link`, `/products/order-quote`, `/cjdropshipping/freight/quote`) now accept only a request order-service signed with its own Ed25519 key (`X-Service-Assertion`, method+path bound, 60s). Anonymous, forged and user callers get 401 |
| 6 | Signed header downstream; drop `oauth2_scheme` + `get_current_user()`? | **Done (2026-09-24)** |
| 7 | Remove service ports from compose? | **Done (2026-09-25).** Worse than listed: Postgres, Redis, RabbitMQ, pgAdmin and the observability stack published on 0.0.0.0. The base file now binds every host port to 127.0.0.1 (`INTERNAL_BIND_HOST`) except Traefik's 80/443; `docker-compose.prod.yml` publishes nothing but Traefik |
| 8 | NetworkPolicy? | **Done for compose (2026-09-25).** `usernet` split into `edge` (Traefik, socket-proxy + gateway/admin-js/Grafana/Prometheus) and `backend` (everything else); Traefik routes over `edge` and has no route to the databases. NetworkPolicy once on Kubernetes |
| 9 | Token purposes? | **Done (2026-09-24).** `purpose`, `iss`, `aud`, `iat`, `jti` are required; only user-service holds the signing key (Ed25519) |
| 10 | Remove `PUBLIC_ENDPOINTS` completely? | Done (§4b) |
| 11 | OpenAPI → TypeScript? | **Done (2026-09-25).** `npm run gen:api` (frontend) writes `types/api/<service>.ts` from each running service's `/openapi.json` via openapi-typescript. Regenerate after a backend schema change; migrating the hand-written frontend types onto them is frontend work |
| 12 | Order saga frozen while waiting on CJ stock? | **Done (2026-09-25).** The timeout worker only covered *pending* sagas; a confirmed order CJ never took on sat until the card hold lapsed. It is now cancelled after `ORDER_SUPPLIER_STALL_HOURS` (24h, hold released). A CJ outage during the stock check is retried, no longer an instant cancel + refund |
| 13 | Session/transaction held open while awaiting services or queues? | **Done (2026-09-25).** Audited every external call. Fixed: production artwork download (read txn held across a 10s HTTP call — proven idle-in-transaction on Postgres), wishlist add (uncommitted INSERT across HTTP), image replace (rows deleted before uploads were written), notification emails enqueued before the row committed (duplicate emails on retry). `BaseRepository.end_read_phase()` for the read → remote → write pattern payment-service already used. Also fixed a lost update on concurrent add-to-cart (row lock) |
| 14 | Value objects (frozen dataclasses)? | **Assessed, not adopted (2026-09-25).** Money is already exact where it is computed (Decimal, integer cents to Stripe, `to_cents` via `str`). `orders.amount` and `order_items.price` moved from float to `Numeric(10,2)` together with partial refunds (2026-09-25) |
| 15 | Unit of Work? | **Assessed, not needed (2026-09-25).** The session is the unit of work and `database.transaction()` is its boundary: one per request, one per consumed event, outbox rows in the same transaction. A wrapper class would add a layer without adding safety. What *was* unsafe is fixed: the request's commit ran after the response was sent (a failed commit lost a write the client was told succeeded) — now `scope="function"` everywhere, with a guard test. Deliberate splits (payment read -> Stripe -> write, sync checkpoints) use named repository methods |
| 16 | Circuit breaker / retries for CJ? | **Done (2026-09-25).** Per-service breakers in the gateway (503 + Retry-After); CJ reads retry with backoff, writes never do; a process-wide CJ breaker; 429/5xx are 'unavailable', not a rejection |
| 17 | Process isolation: API, task queue, consumers, DB? | **Already in place.** Every service runs API, consumer, outbox worker, taskiq worker and scheduler as separate processes (dev.sh) / containers (compose), each with its own database. The single Postgres instance is #19 |
| 18 | RabbitMQ ack policy + DLX? | **Done (2026-09-24).** Worse than open: every queue dead-lettered to a `dlx` exchange nothing declared, so RabbitMQ dropped every failed message. `shared.messaging.ConsumerTopology` now declares `dlx`, one DLQ per queue and 5s/30s/120s retry queues before consuming; `RetryDispatcher` retries transient failures and dead-letters payload errors at once. All 20 queues in 8 consumers, verified on the live broker |
| 19 | One Postgres instance, one superuser? | Open — per-service least-privilege roles |
| 19b | taskiq DLX? | **Done for notifications (2026-09-24).** taskiq acks a failed task (its result is saved), so its DLQ never saw one. `DeadLetteringRetryMiddleware` retries emails with backoff and jitter, then parks them in `taskiq.notifications.dead_letter`. Image generation (refunds quota) and the supplier cron jobs (next run is the retry) deliberately do not retry. Parked messages replay with `./local/dev.sh dlq list` / `dlq replay <queue>` |
| 20 | `autoflush` / `expire_on_commit`; UoW transaction boundaries? | **Done (2026-09-25).** `expire_on_commit=False` is right for async; with `autoflush=False` the gap was deletes: they never flushed, so later reads saw deleted rows and constraint violations surfaced at commit as bare 500s. Deletes now flush; `IntegrityError` renders as 409. Deleting a category silently deleted all its products (ORM cascade) — now refused with 409 |

Frontend:
/order/orderid is open for anyone?
signout() doesn't clear the localstorage?
SessionManager() should not be a singleton?
money calculations is inconsistent?
useCart mutates the state in place?
ProductDetails and Addreview returned early before the hooks?
useCart() re-render the entire provider subtree twice on every cart change?
is checkout client stripe memorized? do clicking the size/color/qty re-render the panel?
9. Cookie-based session, not a JWT in localStorage. Your gateway already sets HttpOnly — trust it and stop carrying tokens in JS? Removing NextAuth Dumb frontend, cookies are the session?
10. TanStack Query for any client-side caching / refetch / optimistic UI. Not Redux.?


