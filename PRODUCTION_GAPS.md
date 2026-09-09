# Production Readiness — Remaining Gaps

Context: business goal is (1) users create AI print designs on t-shirts that you
produce at home and ship yourself, and (2) users buy t-shirts sourced from
CJDropshipping (products pre-fetched and stored in your DB).

Assessment date: 2026-09-03. The hard architectural + integration work is
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
      start/print/ship/deliver/hold/cancel controls.

Tests: `tests/unit_tests/test_production_queue_service.py` (state machine +
aggregator) and `tests/integration_tests/test_production_routes.py` (16 tests
covering the full queued→printed→shipped→delivered path against a real
database, plus the cancellation guards). Verified live on a clean stack: a
custom order confirmed by a real `payment.succeeded` event, printed and posted
from the queue, moved the order to `dispatched`.

**Still open here:** a partial refund for a single cancelled custom line in a
multi-line order. Cancelling one job records the loss and flags it for
reconciliation, but refunding part of an order is §5 work.

### 3. CJ dropshipping order lifecycle completeness — DONE (2026-09-08)
- [x] Checkout-time shipping quote from CJ (`freightCalculate`)
  - `cj_api_client.calculate_freight` + `CJFreightQuoteService` (resolves local
    product/variant -> CJ vid, TTL-cached per ASGI process, cheapest option first)
  - `POST /api/v1/cjdropshipping/freight/quote`, proxied by api_gateway behind
    `get_current_user` (each call costs one live CJ request)
  - **Remaining**: the React checkout still has to call it and add the chosen
    option to the order total — that is frontend work (§6).
- [x] Tracking polling from CJ -> customer notification
  - `CJOrderTrackingService` + `poll_cj_order_tracking` taskiq job (every 5 min,
    each order re-queried at most every `CJ_DROPSHIPPING_TRACKING_POLL_INTERVAL_MINUTES`)
  - Leases rows by stamping `last_polled_at` inside a short transaction, then
    calls CJ with no session or lock held
  - New `cj.order.shipped` / `cj.order.delivered` events written to the outbox in
    the same transaction as the state change; order_service moves the order to
    dispatched/delivered, notification_service emails the customer their tracking
    number (new `notification.cj.order.events.queue`, bound on `cj.order.#`)
  - CJ publishes no webhook, so polling is the only option available.
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

Schema: `supplier_service` migration `c4a7f1d2e9b8` adds the tracking columns
(it also creates `cj_order_attempts` when absent, since that table had only ever
been bootstrapped by `create_all`).

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

### 5. Payments & tax/legal
- Refunds / partial refunds, Stripe webhook signature verification, dispute handling
- Sales tax / VAT / customs — selling physical goods worldwide (esp. via CJ) is a real
  obligation; consider Stripe Tax
- Terms / privacy / returns policy pages
- GDPR data export + delete, audit logging, data retention (checklist §13 fully unchecked)
- AI-print content moderation — you physically print user designs, so IP / trademark / NSFW
  screening is genuine liability, not optional

### 6. Frontend completeness
- No user account/profile page, address book, order-tracking detail page
- No wishlist UI (the service exists, no page)
- The "designer" is a single Hero panel — a sellable product likely needs real placement /
  sizing / per-variant (color) mockups
- Loading/error states, mobile polish

### 7. Testing & docs
- No coverage reports, no inter-service contract tests
- No end-to-end buy-flow test, no security testing (OWASP ZAP etc.)
- No per-service READMEs, no architecture diagram, OpenAPI not curated/published

---

## Rough priority order

1. CI/CD + automated migrations + backups
2. ~~In-house production-queue admin tooling~~ (done — see §2)
3. ~~HTTPS / CORS / rate-limit hardening~~ (done — see §4); secret
   *distribution* per service + a secret manager is the one §4 item left
4. ~~CJ shipping quotes + tracking + failure handling~~ (done — see §3)
5. Tax, legal pages, GDPR, AI content moderation
6. Frontend account / tracking / designer polish (incl. calling the new CJ
   freight-quote endpoint from checkout)
