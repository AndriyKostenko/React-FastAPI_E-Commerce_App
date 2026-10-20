# Production Readiness — Remaining Gaps

Context: business goal is (1) users create AI print designs on t-shirts that you
produce at home and ship yourself, and (2) users buy t-shirts sourced from
CJDropshipping (products pre-fetched and stored in your DB).

Assessment date: 2026-09-03. Last updated 2026-10-13 (status review; before
that CI on pull requests, §1 phase 1, 2026-10-12; the deployment plan, §1;
connection pools, §8.6; `shared/` removed, §8.5; AdminJS, §8.4; S3 for images,
§8.3; the CJ stock webhook, §8.2; Vault, §8.1; the refund and cancellation
paths, PRs #12-#16, §5a). The hard architectural + integration work is done
(CJ integration, AI generation, order saga, artwork storage, in-house
fulfilment, secrets per service). What remains is deployment, a few
hardening items, and legal/compliance work — no re-architecting required.

## Next session: open items (saved 2026-10-15)

Start here. Everything below is still open; everything else in this file is done
or recorded as decided. Merged so far: PR #41 (readiness, phases 2–5) and PR #42
(frontend session isolation, token off the browser, rate limits, lint, race test).

**Needs you (infrastructure and account)**

- Apply the Terraform change: `cd infra && tofu apply tfplan-phase5` (the plan is
  not saved any more; run `tofu plan -out=tfplan-phase5` first). It adds the build
  role and trims the deploy role.
- Move the Vault recovery keys and root token off the host: `/root/vault-init.json`.
  Mandatory before production.
- Root account: turn on MFA, create an admin identity other than root, delete root
  access keys. Terraform has been running as root.
- Create `/etc/ecommerce/production.env` on the host (non-secret settings, plus the
  Postgres superuser, Redis and RabbitMQ passwords the infrastructure containers read
  from the environment, a deliberate exception to the Vault rule).
- Set the repository variables `DOMAIN`, `NEXT_PUBLIC_APP_URL`,
  `NEXT_PUBLIC_STRIPE_TEST_PUBLISHABLE_KEY` and `CATALOGUE_IMAGE_HOST`. The build fails
  without `NEXT_PUBLIC_APP_URL` and the Stripe key. `AWS_BUILD_ROLE_ARN`,
  `AWS_DEPLOY_ROLE_ARN`, `ECR_REGISTRY` and `HOST_INSTANCE_ID` are already set.
  `DEPLOY_ENABLED` stays unset until go-live.
- Provide a domain: Route 53 zone, `images.` CDN, external uptime check, and the
  registrar's name servers. Also set `alert_email` for alarms and the budget warning.

**Phase 6 (go-live), not started**

- Import production secrets into Vault (shared-infra and each service's path), and
  move the three service keys (product-, order-, user-service) out of Terraform state into
  Vault. `tofu apply` first: the user-service IAM user (avatars/ only) is new.
- First real deploy through the workflow (approval, health gate, rollback), then the
  external checks: the full stack under compose with real secrets, Traefik routing
  live, and memory limits measured with `docker stats` (they are first-cut ceilings).
- Stripe and CJ webhooks to the production URL; the Stripe Tax registrations if tax is
  switched on; RETURN_ADDRESS and ADMIN_ALERT_EMAIL; a runbook
  (deploy, rollback, restore, rotate a secret).
- **Sign-up protection (Turnstile captcha, email checks; built 2026-10-17).** Before go-live:
  1. In the Cloudflare dashboard (Turnstile, free plan), add a widget in **Managed** mode
     for the storefront's production hostname(s) only. Cloudflare then refuses tokens
     from any other site.
  2. Put the widget's **secret key** in the production Vault, user-service's path, as
     `TURNSTILE_SECRET_KEY`. user-service refuses to start without one. (The always-pass
     test secret is written only by `dev.sh` into the local Vault.)
  3. Set the repository variable `NEXT_PUBLIC_TURNSTILE_SITE_KEY` (GitHub → Settings →
     Variables) to the widget's **site key**. `deploy.yml` passes it to the image build;
     without it `next build` fails on purpose. A site key is public, so a variable is fine.
  4. After the first deploy, check with the real keys: sign up, sign in and request a
     reset in a browser, and confirm that a request with the test token
     `XXXX.DUMMY.TOKEN.XXXX` gets a 400 (a real secret refuses it; the test secret lets
     everything through).
  5. The live test scripts under `frontend/tests/` send the dummy token. They pass only
     against a stack with the test secret, so never point them at production.
  6. Decide what an outage should do: today, if Cloudflare cannot be reached, sign-up,
     sign-in and forgot-password answer 503 (fail closed), so nobody can sign in until
     Cloudflare is back. Letting sign-in alone through on an outage is a small change in
     `TurnstileHumanCheck`.
  7. Check the email side once with real mail: registering again with an existing
     address sends "someone tried to create an account with your email" (at most once
     an hour per address); an unverified account gets a fresh verification link.
  8. If a Content-Security-Policy is added later, it must allow
     `https://challenges.cloudflare.com` for scripts and frames.
  9. Known gap, not fixed: someone can register a victim's email first, with a password
     they know; if the victim then clicks the verification link, the account is theirs
     but the password is the attacker's. The fix is to choose the password after the
     email is verified.
- Vault still serves plain HTTP on the Docker bridges; TLS is a later step.
- admin-js is behind the `admin` profile until it reads Vault itself.

**Backend and platform (decided, not started)**

- Per-service Redis and RabbitMQ users (postponed in favour of deploying first).
- Dependency upgrades (the 35–169 advisories per service, and the critical `proxy-addr`
  in admin-js); then make the audit blocking.
- AI content moderation, GDPR and retention (see §5 and §8). The legal pages are done
  (2026-10-18, below), pending a lawyer's review.

**Frontend**

- Storefront content (2026-10-18): the fake newsletter form and the invented testimonials
  are gone; the home page shows real reviews (4+ stars with a comment, newest first) and
  hides the section when there are none. The gateway now serves `GET /reviews` publicly.
  Writing a review never worked before this (stale `/review/product/` URL, and the
  delivered check read an `items` field the orders list does not have); both fixed.
  Footer links all go somewhere real. Social links read `NEXT_PUBLIC_INSTAGRAM_URL` and
  `NEXT_PUBLIC_FACEBOOK_URL` (repository variables for the deploy build) and stay hidden
  until set. Still placeholder, by decision: the community gallery (invented handles and
  stock images) until it shows the owner's own generated designs. Still open: `GET /reviews`
  returns every review (fine now, needs paging or a featured endpoint later).
- Best Sellers (2026-10-19): real sales now. order-service `GET /best-sellers` ranks
  products by units in confirmed orders of the last 30 days, less units refunded (returns
  included; a failed refund does not count), custom designs left out; the gateway's public,
  cached `GET /best-sellers` joins the ranking to the products (a deleted product is
  dropped, any other product lookup failure fails the answer so a short list is never
  cached). The shop tabs are All, Best Sellers, Top Rated (the old rating-based
  "Trending"), New Arrivals; Best Sellers shows up to 8, topped up with top rated when
  fewer have sold. The open tab lives in the URL (`?collection=`, old `trending` links
  open Best Sellers), so the header link always opens it; it used to look dead when
  clicked again after picking another tab, or from another tab under the same `#shop`.
  The process steps no longer claim 240gsm organic cotton, carbon-neutral packaging, a
  material-weight choice or a "bespoke AI engine".
- Section 6 is done (2026-10-15), see §6. The header avatar now comes from the stored
  profile (2026-10-17: `fetchHeaderUser`, cached per user for a minute and cleared by the
  proxy route on any write under `users/`), so a new picture shows at once. Left over: a
  local `stripe listen` is needed for a browser checkout to move past "Order placed".
  `next build` was not run (it shares `.next` with the running dev server).
- The live session suite (`npm run test:session`) still runs only locally: it needs the
  whole stack. CI's frontend job gates on `npm run lint -- --max-warnings=0` and runs
  `npm run test:race` since 2026-10-15.
- Browser sign-in, checkout (Stripe test card, CJ sandbox) and the new pages were checked
  in Playwright at 390px and 1280px on 2026-10-15. The Chrome extension was still not
  connected.
- Open design question: the gateway limits authenticated calls per user, but the
  proxy's anonymous calls depend on the forwarded address. Confirm this in production
  behind Traefik before go-live.

**Planned next (added 2026-10-19)**

Catalogue size first: the CJ sync keeps 200 T-shirts (`CJ_DROPSHIPPING_SYNC_MAX_PRODUCTS`,
hourly sync, about 19% of the CJ call budget). Grow it by syncing less often, not by
fetching more per run.

Frontend:

1. **Load more products as the shopper scrolls. Done 2026-10-19.** The shop shows 20
   products, then 20 more each time the shopper nears the end of the list, 3 times (80),
   then a "Load more" button adds 20 at a time (`hooks/useIncrementalReveal.ts`).
   - The home page loads every product at once from a new light listing,
     `GET /products/cards` (product-service and gateway). It carries what a card, the
     tabs and the filters read: about 1.7 KB a product, 350 KB for all 207, where the
     detailed list took 420 KB for 20. Tabs, filters and sort cover the whole catalogue.
   - Quick Add on a single-variant card reads the full product first.
   - Card images now get a `sizes` hint, and cards show the product's main image.
   - Fixed on the way: search and category did nothing. The page sent `searchTerm` and
     `category` where product-service reads `search_term` and `category_id`, and
     product-service never passed its search fields to the query. Search now matches
     name, description and brand; the search bar asks for 3 to 50 characters and lands
     on the shop section.
   - Fixed on the way: `get_all` (every service's copy of `repository_mixins.py`) now
     orders by primary key after any sort, so pages of one query never repeat or skip
     a row.
2. **Show at most 100 as a product's quantity. Done 2026-10-20.** The product page shows
   the selected variant's stock (the product's, without variants), at most 100, and the
   quantity stepper stops there too (`shownStock` in `utils/productVariants.ts`).
3. **Variant selection must follow what exists. Done 2026-10-20.** The page split every
   variant key as `Color-Size`, but CJ sends `Size-Color` (`M-Red`), colour only
   (`Black`), three parts (`Brown-XS-1pcs`) and more, so sizes showed as colours and
   packs as colours. CJ names the parts in `productKeyEn` ("Size-Color"): supplier-service
   now maps it into the product contract (`variant_option_names`, both copies),
   product-service stores it (`products.variant_option_names`, migration `d4a7e2c9b1f8`)
   and returns it on the detailed product. The page (`VariantMatrix`,
   `VariantOptionPicker`) shows one row of buttons per named option, colour first:
   - a value with no variant, or none in stock, stays visible but disabled, judged
     against the options above it (a colour is never blocked by the chosen size);
     picking a colour moves to the nearest real variant, keeping the size if it can;
   - an option with one value across the product is hidden; an empty key part shows
     as "Default";
   - without names, or when keys do not split into one part per name, the whole key is
     the single "Option", so every variant stays buyable.
   Names fill on each product's next hourly sync. Tests: `npm run test:variants` (in CI).
   Not changed: the shop filters still read colour and size from the key by keyword,
   so a `Size-Color` product's colours count as colours but its sizes are missed.
4. **Input sanitising and the other browser-side protections that apply to us**: every
   form and query parameter, what is rendered from API data (product names and
   descriptions from CJ, reviews), the content security policy and the other security
   headers.
5. **Measure and improve performance with the standard browser tools** (Lighthouse,
   Chrome DevTools Performance, Core Web Vitals): measure first, then fix what the
   measurements show (images, bundle size, render-blocking work).
6. **End-to-end tests with Playwright**, plus any other frontend tests that fit (unit
   and component tests). There is no frontend test runner yet; today CI runs only the
   lint and `test:race`.

Backend:

1. **Protection against the attacks that apply to this project**: SQL injection,
   header manipulation (Host, forwarded headers, CRLF), and the rest of the relevant
   OWASP Top 10 across the gateway and every service.
2. **Store users' emails encoded, not in plain text.** Look for a very small, fast
   library to encode and decode them, so that only the encoded email is in the
   database. Login, password reset and "email already registered" still need to find
   a user by email, so lookups need a deterministic part (for example a keyed hash
   stored beside the encrypted value).
3. **An AI check between fetching a CJ product and storing it.** A new class runs
   before the import writes a product. It asks an OpenRouter model whether the product
   image clearly shows what is printed on the T-shirt. If not, the image is not stored
   in our store; if it is, the model writes a description from the image, which
   replaces CJ's. The OpenRouter client already exists in product-service.
4. **Limits on every database model**: maximum lengths and sizes, how many rows or
   items are accepted, and any other restriction that makes sense, in every service.
5. **Limits on every Pydantic model**: types, lengths, ranges and how many items are
   accepted, so that every API input and event payload is bounded.

**Decisions taken (recorded so they are not re-opened)**

- Deploy workflow off until `DEPLOY_ENABLED=true`; approval through the `production`
  environment; two roles (build from `main`, deploy from `production` only).
- Storefront same-origin on the apex; gateway owns `/api/`, `/media/`, `/health`, `/docs`.
- Token never reaches the browser; browser calls go through the proxy route.
- Race test uses the approved seam (dependency injection), verified by mutation.

**CJ sync paging fixed (2026-10-19).** Every hourly CJ sync fetched only page 1
(10 products): the mapper read `totalRecords`/`totalPages` from `content[0].page`, where
CJ's listV2 has none (they are on `data`), so the sync treated page 1 as the last. With
paging working, CJ's keyword search reports 6,000 T-shirts (its ceiling, not a count),
so a run is now capped: `CJ_DROPSHIPPING_SYNC_MAX_PRODUCTS` (default 200), overridable
per supplier with `"max_products"` in `supplier_configs.config`. The cap fixes the run's
batch count up front, since completion is counted against `total_batches`.

## Open backend items (2026-10-13)

Code work:

- **Per-service Redis / RabbitMQ users**: every service still reads the
  Redis and RabbitMQ passwords from one Vault path (§8.1). Postgres is done
  (§8.7).
- **AI content moderation**: none; unscreened designs can reach the printer (§5).
- **GDPR / audit / retention**: only account deletion exists (§5).
- **Dependency vulnerabilities**: 35–169 advisories in 8–16 packages per
  service (pip-audit); admin-js 69 (npm, one critical, `proxy-addr`); CI
  reports them as warnings until an upgrade PR lands (§1).
- **Deployment phases 2–6**, which include backups / DR and automatic rollback
  (§1).

Smaller, listed under their sections as "not covered": CJ PRODUCT / VARIANT
pushes and `messageId` dedup (§8.2), unused catalogue objects and compose's
S3 / Vault settings (§8.1, §8.3), return labels / store credit / restocking
(§5), tax reversal on a lost dispute (§5), a live stock check at the checkout
quote (§3a), coverage / contract / automated e2e / security tests (§7).

**Before production, secure the Vault keys (owner, mandatory):** the Vault recovery keys and root token sit in `/root/vault-init.json` on the host. Move that file off the host to an offline store (password manager or sealed envelope), delete it from the host, then confirm the copy works. Until it is moved, anyone with root on the host can take over Vault and every secret in it. Do not go live before this is done.

Owner actions: rotate the keys from the committed `.env` files and turn on
GitHub secret scanning (§1); replay or discard the old notification
dead letters (§5a); the "Before going live" settings in §3b, §5, §8.2–§8.4.

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

- CI on pull requests: **done (2026-10-12), phase 1 below.** Image
  build/publish and deploy are phases 2 and 5.
- **Secrets in the public git history — rotate (found 2026-10-12).** A
  one-off gitleaks scan of every commit found `backend/.env` and
  `frontend/.env` committed in the past (2024-04-24 to 2026-01-12, last in
  `ec7ca1471c`), with a Stripe secret key and other API keys among them. The
  repository is public, so they are exposed whatever happens to the files
  now: rewriting history does not undo it. **Rotate every key those files
  held** (Stripe first; then CJ, OpenRouter, Google OAuth, mail, JWT /
  signing secrets, database / Redis / RabbitMQ passwords), and turn on
  GitHub secret scanning with push protection (free for public repos). CI
  now runs gitleaks on every pull request's new commits.
- **Known vulnerabilities in the dependencies (found 2026-10-12, counted
  2026-10-14 from the CI audit).** Every service's lock file has 8–16
  vulnerable packages (pip-audit), 35–169 advisories between them: api_gateway
  39 in 8 packages, payment 35 in 9, user 42 in 10, notification 56 in 10,
  cart / shipping / wishlist 128 in 10 each, supplier 157 in 11, order 53 in
  13, product 169 in 16. Among them `starlette`, `anyio`, `python-multipart`,
  `cryptography`, `aiohttp`, `pillow`, `aiosmtplib` (3 → 5, through
  fastapi-mail), several behind exact pins in `pyproject.toml`. npm
  (production dependencies): admin-js 69 (2 low, 43 moderate, 23 high, 1
  critical, `proxy-addr` through express); the frontend 1 moderate (`qs`),
  its critical `next` advisory gone with the Dependabot bump (#28). The CI
  audit job reports them as warnings and stays green until an upgrade PR
  lands; then `AUDIT_BLOCKING: "true"` in `ci.yml` makes it fail on them.
- **Plan decided (2026-10-12): see "Deployment plan" at the end of this section.**
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
      Every service had been bolting Alembic beside `create_all`, and _not one of
      them could rebuild its database from migrations_:
  - `user_service` and `product_service` migrations altered tables (`users`,
    `products`) that no migration ever created, so `alembic upgrade head`
    failed outright. Their chains could not run, so each was squashed to a
    baseline generated from the models; the originals are kept under
    `<service>/alembic_archive/` and in git history.
  - `cart`, `shipping`, `wishlist` and `notification` had **no migrations at
    all** — an `alembic/` directory with an empty `versions/`. Each got a
    baseline.
  - `payment` was missing the outbox retry columns; `supplier` created a unique
    _constraint_ where the model declares a unique _index_. Each got a
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
- No backups / DR for the 9 Postgres DBs yet: planned below (pg_dump every
  6 h, EBS snapshots, monthly restore drill), built in phase 4 (connection
  pooling: done, §8.6)
- No auto-rollback on deploy failure yet: planned below, phase 5 (no
  blue/green or canary, by choice: one host)

#### Deployment plan (decided 2026-10-12)

One maintainer, so no Kubernetes or ECS: one EC2 host runs the existing
compose stack, GitHub Actions tests, builds and deploys, Terraform describes
the AWS side. Choices made: **Postgres, Vault, the frontend and a slim
monitoring stack all run on the host** (not RDS / SSM / Amplify / CloudWatch).

- **AWS shape.**
  - Region `ca-central-1` (selling in Canada only).
  - One host, 2 vCPU / 8 GB (`t4g.large`, or `m7g.large` to avoid burst
    credits), encrypted gp3 EBS, Elastic IP, Route 53. Security group opens
    80/443 only; no SSH: Session Manager for a shell and for port forwarding
    (AdminJS on `localhost:3001`, so its passkey rpID stays `localhost`;
    Grafana the same way).
  - IMDSv2 required with hop limit 1: containers cannot use the host's role.
  - ECR, one repository per image, tagged with the git SHA, last 20 kept.
  - S3: catalogue bucket private behind CloudFront (Origin Access Control),
    private bucket SSE-KMS (presigned URLs only), a backups bucket (versioned,
    KMS, lifecycle). Product and order keep their own narrow IAM keys, held in
    Vault (the code already supports `AWS_S3_ACCESS_KEY_ID`).
  - Mail through SES (SMTP) or the current provider.
  - Account baseline: root MFA and unused, an MFA'd Identity Center user,
    CloudTrail, GuardDuty, a budget alarm.
- **Memory budget** (8 GB): Python processes ~3.5 GB, Postgres ~0.7–1 GB,
  monitoring ~0.9–1.3 GB (with cAdvisor, without tracing), RabbitMQ / Redis /
  Traefik / Vault / frontend ~0.6 GB: about 6–6.5 GB (~0.4 GB more while
  tracing is on). Add 2–4 GB swap and a `mem_limit` per container so
  an image-processing spike cannot get Postgres OOM-killed; move to 16 GB if
  swap is used under normal load.
- **Postgres on the host:** `max_connections=100` (budget in §8.6). Backups:
  - `pg_dump -Fc` of each of the 9 databases every 6 h to the backups bucket
    (RPO ≤ 6 h; the databases are small), kept 30 days;
  - daily EBS snapshots (Data Lifecycle Manager), kept 7 days;
  - a scripted restore into a scratch instance, run monthly, and before
    go-live.
  - Later, if 6 h is too much to lose: pgBackRest with WAL archiving to S3
    (point-in-time restore).
- **Vault on the host** as a systemd service (like Homebrew locally), not a
  container: integrated (raft) storage on EBS, AWS KMS auto-unseal through the
  host role (which containers cannot reach), audit log on, UI not exposed.
  AppRole per service exactly as locally; each container gets only its own
  role-id / secret-id files. Raft snapshot nightly to the backups bucket.
  Secrets are imported once by the owner, as locally. Each service's own
  Postgres login (§8.7) is created on the host as locally, with
  `db/service-role.sql`.
- **Frontend** as a container on the host behind Traefik: a Dockerfile with
  Next's standalone output; `NEXT_PUBLIC_*` values are build-time, so CI builds
  the production image with production values.
- **Monitoring, slim:** Prometheus, Alertmanager, Grafana, Loki, promtail and
  cAdvisor stay (cAdvisor feeds the HighContainerMemory, HighContainerCPU and
  ContainerRestarted alerts and the per-container dashboard panels, which
  matter more once every container has a `mem_limit`; a longer housekeeping
  interval trims its CPU), plus node-exporter for host disk / memory / CPU.
  Tracing is opt-in: Tempo and otel-collector move to a `tracing` compose
  profile and services run with `OTEL_TRACES_DISABLED=true`; turning it on
  while chasing a problem is that flag plus `--profile tracing up` (saves
  ~0.3–0.4 GB and per-request CPU day to day; traces cover HTTP, SQL and
  Redis, not the RabbitMQ saga). Alertmanager keeps sending to Telegram. An
  external Route 53 health check on `/health` alarms by email when the whole
  host is down, which on-host monitoring cannot report.
- **CI on every pull request:**
  - each service's suite in parallel against real Postgres / Redis / RabbitMQ
    service containers (needs a committed CI config file of non-secret test
    values, since CI has no `backend/.env` and no Vault);
  - `alembic check` per service, ruff, `pool-budget`, `docker compose config`;
  - frontend `tsc` and `next build` (ESLint once it is configured again);
  - gitleaks, `pip-audit` / `npm audit`, CodeQL, Trivy on the built images.
- **Deploy on merge to `main`:**
  1. build every image, tag with the git SHA, push to ECR;
  2. the `production` GitHub environment waits for the owner's approval; the
     job assumes an AWS role through OIDC (no stored keys; the role trusts
     only this repo's `production` environment);
  3. if a migration changed, `pg_dump` the affected databases first;
  4. a deploy script on the host (run through SSM) pulls the tag and restarts
     in order: migrations (the entrypoints), consumers and workers, APIs,
     gateway, frontend;
  5. health gate on every service; if one stays unhealthy, redeploy the
     previous SHA automatically and fail the run;
  6. recorded as a GitHub deployment (the audit trail).
- **Release rules:** migrations expand then contract (the previous release
  must run on the new schema; rollback never downgrades the database); events
  additive only (as in §8.5); the gateway and frontend can restart without a
  gap with `docker rollout` (two copies briefly) if a few seconds of restart
  matter. No permanent staging: local covers the CJ sandbox and Stripe test
  mode; Terraform can raise a short-lived copy for a risky change.
- **Host security:** unattended OS security updates, Docker from the official
  repository, containers non-root, `no-new-privileges`, Trivy before deploy,
  Dependabot, branch protection with required checks.
- **Rough cost** (list prices, an estimate): $65–90 / month.
- **Phases, one PR each:**
  1. CI on pull requests (repo only, no AWS). **Done (2026-10-12).**
     `.github/workflows/ci.yml` on every pull request and push to `main`:
     - each service's suite in parallel (Python 3.12, pinned for cart and
       wishlist too) against Postgres, Redis, RabbitMQ and SeaweedFS
       containers, then `alembic upgrade head` + `alembic check`.
       `backend/ci/prepare.sh` generates every password and a throwaway
       Ed25519 key per signing role for the run (masked), renders the S3
       identities with the unchanged `local/s3_local.py` against a
       throwaway Vault dev server, and hands the suite
       `backend/ci/test-settings.conf` (non-secret test values; CI has no
       `backend/.env` and no Vault);
     - repository checks: ruff for syntax errors and undefined names (the
       SQLAlchemy relationship names got `TYPE_CHECKING` imports),
       `backend/ci/check_copies.py` (copied modules identical in every
       service, apart from the two trimmed on purpose), `pool-budget`, and
       both compose files resolving;
     - frontend type check and production build, admin-js type check;
     - gitleaks on the commits a change adds; pip-audit and `npm audit`
       (report-only, see above);
     - `.github/workflows/codeql.yml`: CodeQL for Python and TypeScript on
       pull requests, `main` and weekly; `.github/dependabot.yml`: weekly,
       grouped updates for actions, the ten uv projects and both npm apps.
       Rehearsed off GitHub with the same script, from a copy of `backend/`
       without the env file and with a clean environment per service: all ten
       suites and migration checks pass (1,983 tests). The rehearsal caught
       tests that only passed with the owner's local config, now independent
       of it: the T-shirt price test reads the configured price, the CJ
       open-id tool tests set their own API key, and payment's route tests
       run with test Stripe secrets (the client is mocked); cart and
       wishlist got a `.python-version` (3.12, as the images) instead of
       whatever Python is newest.
       Left to the owner: make these checks required on `main` (branch
       protection) once the first run is green.
  2. production images and compose: frontend image, slim monitoring (tracing
     profile), `mem_limit`s, images from ECR by tag, non-root checks.
     **Done (2026-10-14), not yet deployed:**
     - `frontend/Dockerfile` (Next standalone, `node` user, NEXT_PUBLIC_* as
       build args; the build fails without the publishable Stripe key, by
       design) and `.dockerignore` files that keep `.env*` out of every image.
     - `admin-js-service/Dockerfile` is now multi-stage with production
       dependencies only and runs as `node`; it also ships `src/`, which
       AdminJS compiles at startup.
     - Compose: 30 built services are tagged `${IMAGE_REGISTRY}/ecommerce-<svc>:
${IMAGE_TAG}` (ECR-ready; `local/…:dev` by default); every service has
       a `mem_limit` (ceilings, not yet measured under load: tune from
       `docker stats` on the host); `OTEL_TRACES_DISABLED` defaults to `true`;
       Tempo and the OTEL collector sit in the `tracing` profile; node-exporter
       joins Prometheus.
     - Storefront routing, same origin: the gateway owns `/api/`, `/media/`,
       `/health`, `/docs`, `/openapi.json` on the apex; the frontend takes the
       rest (lower priority). No CORS or cookie-domain change.
     - Verified: all 30 images build with `docker compose build`; the frontend
       and admin-js images run as uid 1000, the frontend serves 200 and reports
       healthy; every Python image runs as a non-root uid, the two taskiq
       workers after `gosu` (their entrypoint starts as root to fix the media
       volume's ownership). Not verified yet: the full stack under compose
       (needs Vault and the production secrets), Traefik routing live, and
       memory use under load.
  3. Terraform: network, host, IAM / OIDC, KMS, S3 + CloudFront, ECR,
     Route 53, account baseline;
  4. Terraform: network, host, IAM / OIDC, KMS, S3 + CloudFront, ECR,
     Route 53, account baseline. **Done (2026-10-14), applied to account
     008897528825 in ca-central-1.** Code in `infra/` (`bootstrap/` made the
     state bucket). Created: VPC and public subnet, one `m7g.large` host with
     IMDSv2 hop limit 1 and no key pair, Elastic IP, 80 GB encrypted root with
     daily snapshots (7 kept), two KMS keys, catalogue / private / backups
     buckets, 31 immutable ECR repositories (20 kept), GitHub OIDC deploy role
     for the `production` environment, CloudTrail, GuardDuty, EBS encryption by
     default, host and budget alarms. Not created yet, waiting on a domain:
     Route 53 zone, `images.` CloudFront, and the uptime check. Owner actions:
     root MFA, an admin identity other than root, and the registrar's name
     servers once a domain exists. The product and order service keys sit in
     Terraform state; move them to Vault in phase 6.
  5. host bootstrap: **Done (2026-10-14), run on the host through SSM**
     (`infra/host/bootstrap-host.sh`, idempotent). 4 GB swap (swappiness 10);
     security-only dnf-automatic; Docker with live-restore and bounded logs,
     no `no-new-privileges` (the taskiq workers need gosu); Compose v5.5.0
     and Vault 2.1.2, both checksum-verified; Vault as a systemd service on
     integrated storage with AWS KMS auto-unseal, plain HTTP on 8200 that the
     `vault-firewall` unit allows only from loopback and the Docker bridges.
     Backups: `ecommerce-backup-postgres` (pg_dump -Fc of the nine production
     databases every 6 h, with a MANIFEST written last), `ecommerce-backup-vault`
     (raft snapshot nightly, read-only token), `ecommerce-restore-drill`
     (monthly). First drill passed against a scratch Postgres with the nine
     database names: all nine restored, table counts match the dumps. Postgres
     runs in its compose container on the host, so the backup timer stays
     disabled until the stack runs (phase 5). **Owner action:** Vault's recovery
     keys and root token are in `/root/vault-init.json` on the host. Move them
     to an offline store and delete the file.
  6. deploy workflow: build / push, approval, SSM deploy, health gate,
     automatic rollback;
  7. deploy workflow: **Built (2026-10-15), not run yet.** `.github/workflows/deploy.yml`
     runs after a green CI on main. The build job (arm64 runner, the host is
     Graviton) builds all images, pushes them to ECR tagged with the commit SHA,
     and assumes the build role, which can only push images and is trusted from
     `main`. The deploy job waits for approval through the `production`
     environment (required reviewer set; deployments from main only), assumes
     the deploy role (SSM only, trusted from that environment alone), and runs
     `infra/host/deploy.sh <sha>` on the host through SSM. The script backs up
     the databases first (aborting on failure), pulls, runs `compose up --wait`
     (migrations run in each entrypoint; `--wait` fails on an unhealthy
     container), and on failure brings the previous SHA back. The host
     `vault-identities.sh` created one AppRole per service, with credentials in
     `/etc/ecommerce/vault/<service>/` mounted read-only into that service only.
     Compose changes: 29 Python services read Vault (no more database or Redis
     URLs with passwords in their environment); admin-js sits behind the `admin`
     profile until it reads Vault. Checked: actionlint and shellcheck clean,
     compose resolves. **Not run:** no deploy yet, since the services need the
     secrets imported (phase 6). **Owner actions before the first deploy:**
     apply `infra/tfplan-phase5` (creates the build role, trims the deploy role);
     create `/etc/ecommerce/production.env` on the host (non-secret settings, and
     the Postgres superuser, Redis and RabbitMQ passwords that the infrastructure
     containers still take from the environment); set the repository variables
     `DOMAIN`, `NEXT_PUBLIC_APP_URL`, `NEXT_PUBLIC_STRIPE_TEST_PUBLISHABLE_KEY`
     and `CATALOGUE_IMAGE_HOST`; add the required reviewer to `production` (done
     for you, as the only reviewer).
     The workflow is switched off: both jobs run only when the repository
     variable `DEPLOY_ENABLED` is `true`, which is set at go-live.
  8. go-live: owner imports production secrets into Vault, DNS, Stripe and CJ
     webhooks to the production URL, external health check, runbook (deploy,
     rollback, restore, rotate a secret).
- **Later, if the shop outgrows one host:** ECS on Fargate (a role and
  injected secrets per service, built-in rollback) at roughly 3–4× the cost;
  RDS when database operations take more time than they are worth.

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
  every CJ product _we sell_ (product-service's `GET /products/stock-keys/{supplier}`,
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
allows one request per second per account; the CJ client spaces the helper's
calls like every other (§5a).

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
      _authentication_. Now behind an ownership check (403 verified).
- [x] **Review impersonation.** `POST /products/{id}/users/{user_id}/reviews`
      was unguarded, so any authenticated user could post a review attributed
      to someone else. Now ownership-checked (403 verified).
- [x] **Authorization sourced from attacker-controlled input.** The review
      `PUT`/`DELETE` routes used `Depends(require_user_or_admin)`, but that
      helper takes the caller as its _first argument_: FastAPI therefore
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
      request that never reaches user-service — only _decoded_ the token, so a
      password reset left stolen access tokens working for their remaining
      20-minute lifetime. A shared `SessionRegistry` (its own Redis DB, written
      by user-service, read by the gateway) now carries the current session
      generation. Verified live: after a reset the old token is refused on
      `/me`, `/notifications/...` and `/wishlists/me`, while a fresh login
      works. Refresh-token _reuse_ — the signature of a stolen token — now also
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

**Resolved locally by §8.1 (Vault, 2026-10-08); compose still to do:**

- ~~**Every service is still _given_ every secret.**~~ Since 2026-10-08 every
  process `dev.sh` starts reads only its own Vault path. Compose still loads
  the blanket `.env` (its containers would need Vault Agent); the deployment
  plan (§1) gives each container only its own AppRole. Original note: All 33
  compose services load
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

**Closed since:**

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
      **Frontend (2026-10-18):** the order page (`/order/[id]`) lists the order's returns (with Withdraw while undecided) and has the request form: lines and units from `/returns/eligibility`, reasons narrowed to what every chosen line allows, photos required for the seller's fault, multipart through the proxy (`lib/returns-api.ts`, rules in `lib/return-draft.ts`). The admin queue is AdminJS. Types are hand-written (`types/returns.ts`), not regenerated.
      **Not covered:**
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
- ~~Terms / privacy / returns policy pages~~ DONE (2026-10-18): `/terms`, `/privacy`,
  `/returns`, `/shipping`, with the business details in `frontend/lib/business.ts`. The
  wording follows the code (30-day per-unit returns, custom prints defects only, card
  hold then capture, Canada only, CJ ships from China) and needs a lawyer's review.
  Open: whether import duties on parcels from China are paid by us or the customer
  (not stated anywhere yet), GST/HST once tax is switched on.
- GDPR data export, audit logging, data retention (checklist §13). Deletion
  exists only in part: `UserService.delete_user_by_id` anonymises the account
  (name, email, phone, image, password), ends its sessions and publishes
  `user.deleted`, which only wishlist-service consumes; orders, addresses,
  reviews, notifications and stored designs keep their data. No export.
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

**CJ rate limiter — done (2026-10-14).** CJ allows one request per second per
account at our level (Free / sales level 0–1; more at higher levels) and
answers more with HTTP 429, code `1600200`. Nothing coordinated the calls:
the API, consumer, taskiq worker (up to 5 tasks at once), scheduler and CLI
tools each paced only their own loop, with hand-placed 1.1 s sleeps, so the
logs held ~480 such 429s (the cancellation-race order on 2026-10-05 failed
its create this way).

- Every CJ call now takes a slot from one budget in supplier-service's Redis
  (`RedisRequestPacer`, `infrastructure/resilience/request_pacer.py`): a Lua
  script reserves the next free slot on Redis's clock, one
  `CJ_DROPSHIPPING_REQUEST_INTERVAL_SECONDS` (1.1) after the last. Each
  attempt, retries included, waits for a slot before the breaker is asked.
- Who waits how long: the API process (a customer is waiting, e.g. the
  checkout freight quote) queues for up to
  `CJ_DROPSHIPPING_INTERACTIVE_MAX_WAIT_SECONDS` (3); background work
  (consumer, tasks, tools) waits up to `..._BACKGROUND_MAX_WAIT_SECONDS` (30)
  but takes a slot only when about one interval is queued ahead, so it never
  stands in front of a customer for long. One wait covers a call's retries.
  Past it the call is not sent: `CJDropshippingRateLimitedError`, a kind of
  "CJ unavailable", so callers retry later and an order is never failed or
  refunded over it. `1600200` in a 200 body reads as busy too.
- Redis unreachable: the process paces its own calls (one warning per
  outage) and CJ calls go on.
- The hand-placed sleeps are gone (stock refresh, subscriptions, catalogue
  sync, `cj-sandbox`). `CJ_DROPSHIPPING_RATE_LIMIT_ENABLED=false` switches
  pacing off (the test suite does; tests that cover pacing inject a pacer).
- Verified: unit tests on a controllable clock, integration tests against
  the real Redis (two pacers share one budget, a customer-facing call goes
  ahead of queued background work, the per-process fallback), and live
  against CJ: unpaced, 2 of 3 concurrent balance reads got a 429; paced,
  24 of 24 from eight clients at once succeeded, sent 1.1 s apart.
- Not covered: the CJ MCP server (`cj-mcp`) and anything else using the
  same CJ account outside supplier-service draw on the same CJ budget
  without seeing ours; their calls can still cause 429s, which the existing
  retries absorb. If 429s keep appearing, raise the interval (e.g. 1.2).

**Open follow-ups:**

- 10 old messages sit in `taskiq.notifications.dead_letter` (from before
  PR #11); replay or discard them.
- After any change to an event in a service's `contracts/events.py`, restart every process of
  the publishing service, outbox worker included: it rebuilds each event from
  the contract before publishing, and a stale one drops new fields silently
  (seen with `refund_scope` on 2026-10-07).

### 6. Frontend completeness

DONE (2026-10-15):

- `/account`: profile (name, phone), avatar (user-service re-encodes to a metadata-free
  WebP under `avatars/` in the catalogue bucket, its own S3 key), password change (ends
  every session, sends the "password changed" email), account deletion (addresses and
  avatar go too) and an address book (user-service `user_addresses`, one default per
  user, Canada only); checkout prefills the default address.
- `/wishlist` and a heart on the product page.
- `/order/[id]`: lines, per-line status and parcel tracking for every channel (CJ, local
  warehouse, in-house) from order-service's new `GET /orders/{id}/details`; `/orders` is a
  customer list instead of an admin grid.
- Designer: white + black kept; every placement drawn at its true print size (mirrors
  order-service's `PRINT_AREAS_INCHES`), front/back toggle, fabric texture, print blend
  per garment colour.
- Loading skeletons, `error.tsx`, `global-error.tsx`, `not-found.tsx`; tighter mobile
  padding; product cards, featured grid and gallery fixed at phone width; Quick Add
  really adds (or opens the product to choose a size).

### 7. Testing & docs

- All ten service suites pass (1,983 tests in the CI rehearsal, 2026-10-12;
  `shared/` and its suite are gone, §8.5), and **CI runs them on every pull
  request since 2026-10-12** (§1, phase 1), with `alembic check`, ruff,
  gitleaks, audits and CodeQL. Left to the owner: make the checks required on
  `main` once the first run is green.
- The suites no longer depend on the local configuration: order-service's
  tests pin `STRIPE_TAX_ENABLED=false` in `tests/conftest.py` (with Stripe Tax
  on locally, 69 of them used to fail). Tax pricing keeps its own tests with
  explicit settings in `test_order_pricing_service.py`.
- No coverage reports, no inter-service contract tests
- No _automated_ end-to-end buy-flow test (manual live runs passed — see §3b, §5a),
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
     frontend's own secrets, and Redis/RabbitMQ users per service. The Redis
     and RabbitMQ passwords sit in one path that every service may read; the
     Postgres superuser's moved to `postgres-admin` with §8.7.
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
   database stores catalogue _keys_ and responses add the public origin; all
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
5. **Remove `shared/`.** It held 83 modules, imported from 441 files.
   **Done (2026-10-11): `shared/` is gone; all five phases below are complete.**
   **Decided (2026-10-10): no shared library of any kind.** Every service
   carries its own copy of what it uses; nothing is published or installed
   from a common path.
   - **Layout in each service.**
     - `infrastructure/`: copies of the infrastructure modules the service
       reaches (its own imports plus what those import), under the same
       sub-paths as in `shared/` (`infrastructure/app/builder.py`,
       `infrastructure/messaging/…`). `from shared.x` becomes
       `from infrastructure.x`, and two services' copies compare with a plain
       `diff -r`. Nesting avoids clashes with the services' own `exceptions/`,
       `database_layer/`, `managers/`, `utils/`, `models/`.
     - `contracts/`: only the events the service publishes or consumes (with
       their base classes), its members of the queue/event enums, and the DTOs
       it sends or receives. Publishers add fields only; consumers already
       ignore unknown ones (Pydantic's default), and `schema_version` stays on
       every event.
     - `settings.py`: its own `Settings` / `TestSettings` holding only the
       fields it and its infrastructure read; `config.py` keeps exporting
       `settings`. Field names do not change, so `backend/.env` and the Vault
       paths stay as they are.
   - **Where each part goes.**

     | `shared/`                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Goes to                                                                                                                                                                 | Phase |
     | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- |
     | `email_service/` (+ `email_links`), `templates/`                                                                                                                                                                                                                                                                                                                                                                                                                       | notification-service                                                                                                                                                    | 1     |
     | `messaging/task_dead_letter.py`                                                                                                                                                                                                                                                                                                                                                                                                                                        | notification-service                                                                                                                                                    | 1     |
     | `managers/password_manager.py`                                                                                                                                                                                                                                                                                                                                                                                                                                         | user-service                                                                                                                                                            | 1     |
     | `utils/filter_parser.py`                                                                                                                                                                                                                                                                                                                                                                                                                                               | product-service                                                                                                                                                         | 1     |
     | `contracts/product.py`                                                                                                                                                                                                                                                                                                                                                                                                                                                 | supplier-service                                                                                                                                                        | 1     |
     | `enums/auth_enums.py` (`AuthCookies`)                                                                                                                                                                                                                                                                                                                                                                                                                                  | gateway                                                                                                                                                                 | 1     |
     | `logs/app.log`, `=0.27.0`, `shared_service_issues.txt`, `enums/supplier_service.py` (unused)                                                                                                                                                                                                                                                                                                                                                                           | deleted                                                                                                                                                                 | 1     |
     | `settings.py`                                                                                                                                                                                                                                                                                                                                                                                                                                                          | each service's `settings.py`; the 23 fields nothing reads are dropped                                                                                                   | 2     |
     | `enums/status_enums.py`                                                                                                                                                                                                                                                                                                                                                                                                                                                | order statuses, line fulfilment, production job → order; `PaymentStatus` → payment; `SyncStatus` (unused) dropped. Waits for phase 2 because `settings.py` imports them | 2     |
     | `contracts/events.py`, `enums/event_enums.py`, `enums/services_enums.py`                                                                                                                                                                                                                                                                                                                                                                                               | `contracts/` of each publisher and consumer, trimmed to its events                                                                                                      | 3     |
     | `contracts/order`, `returns`, `artwork`, `supplier`, `tax`, `auth`                                                                                                                                                                                                                                                                                                                                                                                                     | `contracts/` of the services that send or receive them                                                                                                                  | 3     |
     | `contracts/shipping_region.py`                                                                                                                                                                                                                                                                                                                                                                                                                                         | order + supplier (both enforce it)                                                                                                                                      | 3     |
     | `utils/supplier_pricing.py`, `exchange_rates.py`, `money.py`                                                                                                                                                                                                                                                                                                                                                                                                           | product + order + supplier. The catalogue price and the order quote must agree, so a change lands in all three copies in one commit                                     | 3     |
     | `auth/user_tokens.py`, `managers/token_manager.py`                                                                                                                                                                                                                                                                                                                                                                                                                     | issuer + token manager → user; verifier → gateway. Waits for phase 4 because `testing/signing_keys.py` uses both                                                        | 4     |
     | `app/`, `middleware/`, `auth/` (assertions, guards, keys), `utils/authenticated_caller`, `client_ip`, `customized_json_response`, `models_mixins`, `exceptions/`, `database_layer/`, `managers/` (DB session, test DB session, Redis base, cache, rate limit, session registry, logger), `idempotency/`, `outbox/`, `models/outbox_events.py`, `events/event_publisher.py`, `messaging/`, `resilience/`, `vault/`, `telemetry.py`, `admin/admin_tables.py`, `testing/` | `infrastructure/` of each service that reaches them                                                                                                                     | 4     |
     | `messaging/dead_letter_replay.py` (the `dev.sh dlq` CLI)                                                                                                                                                                                                                                                                                                                                                                                                               | order-service, whose venv `dev.sh` already runs it from                                                                                                                 | 4     |
     | `tests/`                                                                                                                                                                                                                                                                                                                                                                                                                                                               | travel with their module into every service that carries it                                                                                                             | 4     |

   - **Phases**, one PR each, every suite green after each:
     1. Code used by one service moves into it; dead files deleted.
        **Done (2026-10-10).** The email templates now ship inside
        notification-service (`email_service/templates/`, found by the module
        itself; the `TEMPLATES_DIR` setting and the compose template mounts
        are gone). Suites green: notification 119, user 174, product 321,
        supplier 230, gateway 228, shared 50; affected processes restarted
        and healthy.
     2. Per-service settings (and the status enums).
        **Done (2026-10-11).** `shared/settings.py` (256 fields) is gone; each
        service has its own `settings.py` with `Settings`, `TestSettings`,
        `get_settings()` and `get_test_settings()`, holding only the fields it
        or the `shared/` modules it uses read (gateway 47, user 51, product 78,
        supplier 93, order 71, payment 40, cart 33, wishlist 35, shipping 34,
        notification 49). Each signing key now sits only with the services
        that sign or verify with it: the user-token private key in
        user-service, the gateway's in the gateway, each service-assertion
        private key in its caller, the public halves with the verifiers. The
        23 members nothing read are dropped (unused `*_REDIS_PREFIX`es,
        `ALGORITHM`, `TOKEN_URL`, pgAdmin, the notification-consumer URLs, a
        few CJ URLs, …); names did not change, so `backend/.env` and Vault are
        as they were. Until phase 4 copies them in, the `shared/` modules
        import the running service's top-level `settings` module (the same
        line they will have as `infrastructure/`); `shared/`'s own suite uses
        a stand-in in `shared/tests/settings.py`. The "Vault before the file"
        check moved from `shared/` into every service
        (`tests/unit_tests/test_settings.py`). Status enums:
        `order_service/enums/status_enums.py` (order, delivery, line
        fulfilment, production job) and `payment_service/enums/status_enums.py`
        (`PaymentStatus`); `SyncStatus` dropped. Suites green: gateway 229,
        user 175, product 322, supplier 231, order 283, payment 135, cart 63,
        wishlist 28, shipping 45, notification 120, shared 49; every process
        restarted through `dev.sh up` and healthy, `dlq replay` still loads
        its settings.
     3. Per-service contracts.
        **Done (2026-10-11).** Each service's `contracts/` holds only the
        events it publishes or consumes and their base classes (wishlist 3 …
        order 44), only its queue/event enums and only the members it
        references (`event_type` is a plain `str` on every event, so an
        unknown member never fails validation), `services_enums.py`, and the
        DTO modules it sends or receives. The pricing helpers
        (`supplier_pricing`, `exchange_rates`, `money`) are copied whole into
        product-, order- and supplier-service's `utils/`, with their test.
        `contracts/auth.py` waited for phase 4: the auth modules pass
        `TokenClaims` around, and two copies of that model would fail
        Pydantic validation across the boundary.
     4. Per-service infrastructure.
        **Done (2026-10-11).** Every service carries the `shared/` modules it
        reaches under `infrastructure/` (gateway 36 files … supplier and
        order 50), same sub-paths, `from infrastructure.x`. User tokens: the
        issuer, verifier and token manager are in user-service only; the
        gateway's `user_tokens.py` is the verifier alone, and its tests mint
        tokens with a test-only issuer copy
        (`infrastructure/testing/user_token_issuer.py`). Each copy of the
        test signing keys keeps only what that service's tests call. The
        tests travelled with their modules: caller assertion (all ten),
        service assertion (product, supplier, order, payment), resilience
        (gateway, supplier), the commit-before-response scan (each service
        scans itself), the RabbitMQ topology test (the eight consumers; the
        replay case only in order-service, which keeps the `dlq replay` CLI)
        and the Vault settings-source test (all ten); the Vault import-script
        test is `dev.sh` tooling and sits in order-service. `shared` was
        never an installed dependency (it was found through `PYTHONPATH` and
        pytest's `..`), so the services already declared what they import;
        added explicitly: `prometheus-client` everywhere, `cryptography`
        where the auth code imports it, `aio-pika` where a module or test
        does (the locks only gained entries).
     5. `shared/` deleted.
        **Done (2026-10-11).** Gone with it: the `[tool.uv.sources]` path
        entry and the `..` pytest/pyright paths in every `pyproject.toml`,
        the 29 + 10 `./shared` mounts in `docker-compose.yml` and
        `docker-compose.test.yml` (the resolved config is otherwise
        identical), `PYTHONPATH=backend` and the `shared-tests` identity in
        `dev.sh` (the AppRole stays in Vault, unused), the backend-root path
        hacks in payment's `alembic/env.py` and product's seed script.
        `dev.sh dlq replay` runs `infrastructure.messaging.dead_letter_replay`
        from order-service. CLAUDE.md, DESIGN_PATTERNS and the observability
        README point at the new paths. Suites green: gateway 255, user 194,
        product 358, supplier 276, order 329, payment 165, cart 87, wishlist
        52, shipping 69, notification 144 (1,929, nothing skipped); all 33
        processes restarted through `dev.sh up` and healthy. Docker images
        not built.
   - **Cost, accepted:** the same infrastructure code exists in up to ten
     services (today each service reaches 3.6k–6k lines of `shared/`, less
     once settings and contracts are trimmed), and a fix to a copied module
     has to be made in every copy.
6. **Database connection pools, sized for a 2-CPU / 8 GB host.**
   **Done (2026-10-11).** Every process was capped at 2 connections: the
   pool was derived from `2 × cpu_count + 1` workers (the APIs run one,
   `GUNICORN_WORKERS: 1`; in a container `os.cpu_count()` reports the host)
   and from `PG_MAX_CONNECTIONS = 100` while Postgres allowed 300, and the
   consumers, outbox/saga workers and taskiq workers were not budgeted at all.
   An API could run two queries at once; the rest waited and failed after 5 s.
   - Pools are now set per process, not derived: `DB_POOL_SIZE`,
     `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS` in each service's settings
     (an API's defaults, 3 + 2); compose and `dev.sh` give consumers, outbox
     and saga workers 1 + 1 and taskiq workers 1 + 0 (one engine per task).
     The supplier taskiq worker runs at most 5 tasks (`--max-async-tasks 5`);
     the product one is budgeted 2 mirror sweeps. `PoolSettingsCalculator` and
     `PG_MAX_CONNECTIONS` / `PG_RESERVED_CONNECTIONS` / `PG_DB_SERVICES_COUNT`
     are gone (stale keys in `backend/.env` are ignored).
   - Postgres `max_connections` is 100 (compose and `dev.sh`). One worker per
     API: each Python process takes ~90–120 MB (product's ~300 MB), so 2×CPU+1
     workers for ten APIs would not fit 8 GB, and 2 cores run only a handful
     of queries at once anyway.
   - `./local/dev.sh pool-budget` (`local/pool_budget.py`) adds up every
     container's worst case from `docker-compose.yml` (workers × engines ×
     pool + overflow) and fails over `max_connections − 15` reserved, or when a
     container of a database service states no pool: today 82 of 85.
   - Verified: every suite green (+6 pool tests per database service), the
     stack restarted with the new pools logged per role, 60 concurrent product
     lists through the gateway all 200 with product-service at ≤ 5
     connections. Docker images not built.
7. **Per-service Postgres logins (bug list #19).**
   **Done (2026-10-14).** Every service connected as the `postgres`
   superuser, with one password every service could read from
   `shared-infra`: any service could read, change or drop any other's data.
   Decisions: one login per service, **static** (its password in its own
   Vault path, generated once, not rotated), chosen over Vault's database
   engine (rotated or dynamic users) for simplicity; that login **owns** its
   databases (no separate migration login); Redis / RabbitMQ users are the
   next step; the unused `outbox_events_db` / `_test_db` are dropped.
   - `db/service-role.sql` (run by `dev.sh` and CI): a login named after the
     service directory (`supplier_service`, …), no superuser / createdb /
     createrole, owning `<svc>_db` and `<svc>_test_db` and every table,
     sequence, view, enum type and routine in them (the objects earlier
     migrations created as the superuser move over); `CONNECT` revoked from
     everyone else, on the maintenance databases (`postgres`, `template1`)
     too. Idempotent.
   - `dev.sh infra up` (and `init`) generates each login's password into the
     service's own Vault path as `POSTGRES_USER` / `POSTGRES_PASSWORD`, which
     the service's settings read after `shared-infra`, so no Python changed;
     it moves the superuser's password from `shared-infra` to
     `postgres-admin` (root token only). `vault import` writes it there too.
   - CI: `ci/prepare.sh` creates the job's service login the same way and
     hands the suite that login, so tests, `alembic upgrade` and
     `alembic check` run without superuser rights there as well.
   - **Verified live (2026-10-14):** 9 logins, each owning only its two
     databases, every object in all 18 owned; a second `infra up` changes
     nothing. As supplier-service's own Vault identity: its database works
     (temporary tables included); `order_service_db`, `payment_service_db`
     and `postgres` are refused; `CREATE DATABASE` is refused;
     `postgres-admin` is 403; `shared-infra` no longer holds the superuser's
     password. `dev.sh migrate` and `alembic check` clean for all nine as
     their own logins; all ten suites pass; the stack restarted healthy.
   - **Before production:** run `db/service-role.sql` for each service on the
     host with a generated password, kept in that service's Vault path
     (deployment phase 4). Compose still gives every container the
     superuser from `.env`.
   - Not covered: Redis ACL users and RabbitMQ users per service (next);
     password rotation (by hand: delete the service's `POSTGRES_PASSWORD`
     from its Vault path, `dev.sh infra up`, restart its processes).

---

## Rough priority order

1. Deployment + backups: ~~CI~~ (done 2026-10-12, §1 phase 1) and
   ~~automated migrations~~ (done, §1); deployment phases 2–6 are next, with
   the dependency-upgrade PR and the key rotation (§1)
2. ~~In-house production-queue admin tooling~~ (done — see §2)
3. ~~HTTPS / CORS / rate-limit hardening~~ (done — see §4); ~~secret
   distribution per service + a secret manager~~ (Vault, done locally, §8.1;
   compose / production in deployment phase 4)
4. ~~CJ shipping quotes + tracking + failure handling~~ (done — see §3)
5. AI content moderation (design generation works end to end, so unscreened
   designs can reach the printer), legal pages, GDPR. Tax is wired in (§5);
   it needs the Stripe registrations before going live
6. Frontend account / tracking / designer polish (checkout shipping options
   are done — see §3b)
7. ~~Finish gateway auth (bug list 1, 2b/5/6, 4, 9) and the reliability items
   (12–20) below~~ (done, #19 included: §8.7)
8. Refund and cancellation paths (done and verified live — see §5a); ~~the CJ
   rate limiter~~ (done 2026-10-14, §5a)

## Bug list — triage (2026-09-24)

Backend:

| #   | Question                                                                | Status                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| --- | ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Is the token decoded twice (gateway `AuthMiddleware` and user-service)? | **Done (2026-09-24).** Only the gateway decodes it; user-service reads the gateway's signed caller assertion and checks the account row                                                                                                                                                                                                                                                                                                                                                                                                                              |
| 2   | Gateway strips auth and injects identity headers?                       | **Done (2026-09-24).** `Authorization` and `Cookie` stop at the gateway; identity travels only as the signed assertion                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 2b  | Signing key out of the gateway, like Google login?                      | **Done (2026-09-24).** User tokens are EdDSA, private key in user-service only; the gateway signs 60s method+path-bound caller assertions (`X-Caller-Assertion`) that services verify with its public key                                                                                                                                                                                                                                                                                                                                                            |
| 3   | `@public` decorator?                                                    | Superseded: `PublicRouteRegistry` (§4b). Secure-by-default router-level dependencies would remove the middleware entirely                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| 4   | `self_or_admin` in the services?                                        | **Done (2026-09-24).** `shared.auth.route_guards` on every non-public route; also closed payment/shipment reads by any user and an unguarded `GET /payments`                                                                                                                                                                                                                                                                                                                                                                                                         |
| 5   | Only the gateway may call services (`INTERNAL_HMAC_SECRET`, Vault)?     | **Done (2026-09-25).** Only the gateway can assert a user; the three routes order-service calls directly (`/artwork/download-link`, `/products/order-quote`, `/cjdropshipping/freight/quote`) now accept only a request order-service signed with its own Ed25519 key (`X-Service-Assertion`, method+path bound, 60s). Anonymous, forged and user callers get 401                                                                                                                                                                                                    |
| 6   | Signed header downstream; drop `oauth2_scheme` + `get_current_user()`?  | **Done (2026-09-24)**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| 7   | Remove service ports from compose?                                      | **Done (2026-09-25).** Worse than listed: Postgres, Redis, RabbitMQ, pgAdmin and the observability stack published on 0.0.0.0. The base file now binds every host port to 127.0.0.1 (`INTERNAL_BIND_HOST`) except Traefik's 80/443; `docker-compose.prod.yml` publishes nothing but Traefik                                                                                                                                                                                                                                                                          |
| 8   | NetworkPolicy?                                                          | **Done for compose (2026-09-25).** `usernet` split into `edge` (Traefik, socket-proxy + gateway/admin-js/Grafana/Prometheus) and `backend` (everything else); Traefik routes over `edge` and has no route to the databases. NetworkPolicy once on Kubernetes                                                                                                                                                                                                                                                                                                         |
| 9   | Token purposes?                                                         | **Done (2026-09-24).** `purpose`, `iss`, `aud`, `iat`, `jti` are required; only user-service holds the signing key (Ed25519)                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| 10  | Remove `PUBLIC_ENDPOINTS` completely?                                   | Done (§4b)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| 11  | OpenAPI → TypeScript?                                                   | **Done (2026-09-25).** `npm run gen:api` (frontend) writes `types/api/<service>.ts` from each running service's `/openapi.json` via openapi-typescript. Regenerate after a backend schema change; migrating the hand-written frontend types onto them is frontend work                                                                                                                                                                                                                                                                                               |
| 12  | Order saga frozen while waiting on CJ stock?                            | **Done (2026-09-25).** The timeout worker only covered _pending_ sagas; a confirmed order CJ never took on sat until the card hold lapsed. It is now cancelled after `ORDER_SUPPLIER_STALL_HOURS` (24h, hold released). A CJ outage during the stock check is retried, no longer an instant cancel + refund                                                                                                                                                                                                                                                          |
| 13  | Session/transaction held open while awaiting services or queues?        | **Done (2026-09-25).** Audited every external call. Fixed: production artwork download (read txn held across a 10s HTTP call — proven idle-in-transaction on Postgres), wishlist add (uncommitted INSERT across HTTP), image replace (rows deleted before uploads were written), notification emails enqueued before the row committed (duplicate emails on retry). `BaseRepository.end_read_phase()` for the read → remote → write pattern payment-service already used. Also fixed a lost update on concurrent add-to-cart (row lock)                              |
| 14  | Value objects (frozen dataclasses)?                                     | **Assessed, not adopted (2026-09-25).** Money is already exact where it is computed (Decimal, integer cents to Stripe, `to_cents` via `str`). `orders.amount` and `order_items.price` moved from float to `Numeric(10,2)` together with partial refunds (2026-09-25)                                                                                                                                                                                                                                                                                                 |
| 15  | Unit of Work?                                                           | **Assessed, not needed (2026-09-25).** The session is the unit of work and `database.transaction()` is its boundary: one per request, one per consumed event, outbox rows in the same transaction. A wrapper class would add a layer without adding safety. What _was_ unsafe is fixed: the request's commit ran after the response was sent (a failed commit lost a write the client was told succeeded) — now `scope="function"` everywhere, with a guard test. Deliberate splits (payment read -> Stripe -> write, sync checkpoints) use named repository methods |
| 16  | Circuit breaker / retries for CJ?                                       | **Done (2026-09-25).** Per-service breakers in the gateway (503 + Retry-After); CJ reads retry with backoff, writes never do; a process-wide CJ breaker; 429/5xx are 'unavailable', not a rejection                                                                                                                                                                                                                                                                                                                                                                  |
| 17  | Process isolation: API, task queue, consumers, DB?                      | **Already in place.** Every service runs API, consumer, outbox worker, taskiq worker and scheduler as separate processes (dev.sh) / containers (compose), each with its own database. The single Postgres instance is #19                                                                                                                                                                                                                                                                                                                                            |
| 18  | RabbitMQ ack policy + DLX?                                              | **Done (2026-09-24).** Worse than open: every queue dead-lettered to a `dlx` exchange nothing declared, so RabbitMQ dropped every failed message. `shared.messaging.ConsumerTopology` now declares `dlx`, one DLQ per queue and 5s/30s/120s retry queues before consuming; `RetryDispatcher` retries transient failures and dead-letters payload errors at once. All 20 queues in 8 consumers, verified on the live broker                                                                                                                                           |
| 19  | One Postgres instance, one superuser?                                   | **Done for Postgres (2026-10-14, §8.7).** One login per service, owning only its two databases, password in its own Vault path (static, not rotated: chosen over Vault's database engine). Redis / RabbitMQ users per service are the next step                                                                                                                                                                                                                                                                                                                      |
| 19b | taskiq DLX?                                                             | **Done for notifications (2026-09-24).** taskiq acks a failed task (its result is saved), so its DLQ never saw one. `DeadLetteringRetryMiddleware` retries emails with backoff and jitter, then parks them in `taskiq.notifications.dead_letter`. Image generation (refunds quota) and the supplier cron jobs (next run is the retry) deliberately do not retry. Parked messages replay with `./local/dev.sh dlq list` / `dlq replay <queue>`                                                                                                                        |
| 20  | `autoflush` / `expire_on_commit`; UoW transaction boundaries?           | **Done (2026-09-25).** `expire_on_commit=False` is right for async; with `autoflush=False` the gap was deletes: they never flushed, so later reads saw deleted rows and constraint violations surfaced at commit as bare 500s. Deletes now flush; `IntegrityError` renders as 409. Deleting a category silently deleted all its products (ORM cascade) — now refused with 409                                                                                                                                                                                        |

Frontend, status (2026-10-15, merged in PRs #42 and #43):

- Done: the server session is per request (it was a module-level object, so
  concurrent requests could read each other's session); the order page sends the
  owner's token (it could never show an order) and asks for sign-in without one;
  sign-out and session expiry clear the user's payment intent, pending checkout and
  generation state (`utils/client-storage.ts`; the cart stays); `useCart` builds new
  state, sums in cents (`utils/money.ts`), writes storage after load, and memoizes
  its value; the hero computes its unit price once in cents, so a cart line times
  its quantity equals the price shown; `ProductDetails` and `AddReview` no longer
  return before their hooks; the generation hook no longer reads a ref during render.
- Done, bug 9: the access token no longer reaches the browser. The session endpoint
  and the rendered HTML carry no token (`/api/auth/session` returned it before).
  Browser calls for checkout, image generation and reviews go through a same-origin
  proxy (`app/api/gateway/[...path]/route.ts`), which adds the token on the server,
  allows only the versioned API, and refuses cross-site writes.
- Done, lint: `eslint-config-next` was an unrelated 0.2.4 package; it is now the
  16.x release and the config is flat (`eslint.config.mjs`). `npm run lint` runs.
  9 errors remain, all from the `set-state-in-effect` rule (storage hydration and
  prop sync in the cart, the generation hook, the checkout form, the product page,
  the colour selector, the activation page and the featured collection). Fixing them
  properly means `useSyncExternalStore` for storage-backed state; that is a design
  choice, not a mechanical fix.
- Tests: `npm run test:session` (11 tests, real stack, no mocks): two users stay
  separate, including 240 concurrent page requests; the proxy refuses anonymous
  callers and cross-site writes and keeps users to their own orders; the token is
  absent from the session endpoint and the HTML. The two token tests failed before
  the fix. The concurrency test passes on the old code too: the race did not show up
  in 480 overlapping requests here, so it is not proven by that test.
- Done, rate limits by client: the gateway already trusts `X-Forwarded-For` only from
  the private proxy networks (`TRUSTED_PROXY_NETWORKS`) and walks the chain from the
  right; the gap was on the frontend. Server-side calls and the NextAuth sign-in now
  forward the browser's address (`lib/client-address.ts`), and the proxy route passes
  it on. Signed-in users were already counted per account. Checked: sign-ins from
  eight different addresses all succeed, and the attribution test fails with the
  forwarding turned off. Production relies on the frontend being reachable only
  through Traefik; the header is trusted only from the private networks.
- Done, lint: 0 errors (8 warnings left, all existing hook-dependency notes; cleared
  2026-10-15 in PR #43, `npm run lint` now reports no issues). The
  cart, the checkout intent and the generation session are external stores
  (`lib/local-storage-store.ts`, `useSyncExternalStore`), so nothing copies storage
  into state in an effect. The other rule hits were derived during render (activation,
  checkout quote, cart membership, featured tab) or reset during render (colour
  selector). The fragment token is read through a store that remembers it per path.
- Done, deterministic race test: `npm run test:race` (6 tests). `SessionManager` takes
  its cookie reader and token decoder as dependencies (the approved seam). The test
  runs one shared instance, binds each request's cookies with AsyncLocalStorage, and
  releases the decodes in a chosen order. Mutation check: putting the old shared-state
  pattern back fails 4 of the 6 tests on every run; the fix passes all 6. The
  production decoder is loaded lazily, so the test does not pull in the auth
  configuration.
  Frontend (triage updated 2026-10-16; the work above is merged in PRs #42–#44):

| #   | Question                                                                                   | Status                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| --- | ------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `/order/[orderId]` open to anyone?                                                         | **Done (PR #42, params fix in #43).** The page reads the caller's session and asks for sign-in without one; the order is fetched with the owner's token, and the gateway proxy keeps users to their own orders (covered by `npm run test:session`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| 2   | `signOut()` doesn't clear localStorage?                                                    | **Done (PR #42).** Sign-out and session expiry clear the payment intent, pending checkout and generation state (`utils/client-storage.ts`). The cart is kept on purpose                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| 3   | `SessionManager` should not be a singleton?                                                | **Done (PR #42).** One instance is still exported (`actions/getCurrentUser.ts`), but it is stateless: every call reads and decodes its own request's cookie, nothing is stored on the object. Cookie reader and decoder are injected; `npm run test:race` fails 4 of 6 with the old shared-state pattern put back                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| 4   | Money calculations inconsistent?                                                           | **Done (PR #42).** Cart totals and the hero's unit price are summed in cents (`utils/money.ts`); checkout shows the server's quote, never a client total                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| 5   | `useCart` mutates state in place?                                                          | **Done (PR #42).** Every change writes a new array and new line objects through an external store (`lib/local-storage-store.ts`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| 6   | `ProductDetails` / `AddReview` return before their hooks?                                  | **Done (PR #42)**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| 7   | `useCart` re-renders the whole provider subtree twice per cart change?                     | **Done (PR #42/#43).** No hydration effect any more (`useSyncExternalStore`), and the context value is memoized, so a change is one render and unrelated provider renders don't reach consumers                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| 8   | Is the checkout's Stripe instance memoized? Do size/colour/qty clicks re-render the panel? | **Done (2026-10-17).** `loadStripe` runs once at module level (`lib/stripe.ts`), and the `Elements` `options` are a `useMemo` keyed on the amount, so Elements sees a new object only when the amount changes. On the product page, size/colour/qty are local state of `ProductDetails`: a click re-renders that component and its children but not the cart provider or other consumers. Not measured as a problem; leave unless profiling says otherwise |
| 9   | Cookie session instead of a JWT in JS; drop NextAuth, "dumb" frontend? | **Done as option A (2026-10-16): NextAuth kept, sessions now refresh and sign-out revokes.** Before: the token never reached the browser (PR #42), but sign-in ran server-side in `authorize()`, so the gateway's refresh cookie landed on the Next server and was dropped; every customer was signed out when the 20-minute access token expired, and sign-out revoked nothing (no code called `/refresh` or `/logout`). Now the refresh token is read from the gateway's Set-Cookie at sign-in (password and Google) and kept in the encrypted NextAuth cookie; `proxy.ts` (`SessionProxy`) refreshes the access token 2 minutes before it expires, writing the new cookie into the request being rendered and onto the response; `SessionRefresher` sends each refresh token to the gateway once (concurrent requests share one call, late ones get the same result for 120 s), because user-service treats reuse of a spent token as theft and revokes every session of the account. Its memory is per process: correct for one Next process (one host), several would need shared storage or a reuse window in user-service. Sign-out calls the gateway `/logout` (NextAuth `events.signOut`); user-service `/logout` now takes the refresh token as its own proof (it used to require a valid access token, so revoking after expiry failed silently and the gateway still answered 200; it now logs a failed revoke). The page timer ends a session at the refresh token's expiry (7 days, sliding). Tests: `npm run test:session-refresh` (13, live gateway, no mocks; the shared-refresh and request-cookie checks fail with the fixes reverted); end to end through the real frontend, a burst of 6 requests plus a late one with the old cookie made exactly one `/refresh`, and a signed-out session replayed later was refused and cleared. Sign-out racing a refresh, fixed 2026-10-17: a request that refreshed in the same moment as a sign-out used to look like reuse and end every session of the account. user-service now marks a signed-out refresh token (`refresh:signed_out:<hash>`) instead of only deleting it, and a refresh with a marked token gets a plain 401 "Session signed out"; each rotation links the spent token to the new one (`refresh:rotated:<hash>`), so a sign-out sent with a token a refresh has just spent also ends the token that refresh issued (it was left live for 7 days). Every whole-account revocation (password change or reset, Google linking, passkey revoke, theft detection) marks the tokens it ends the same way, so a tab refreshing with a pre-change token afterwards no longer bumps the generation again and ends the session the user just signed in to. Reuse of a spent token that was never signed out is still treated as theft. Tests: user-service unit and integration tests for both orders and for a sign-out landing in the middle of a refresh (fail with the fix reverted); live against the running service and real Redis, concurrent refresh + sign-out with staggered delays ended the session in every order and left the account's other session working. Removing NextAuth (gateway cookies as the session) stays possible later; not needed now |
| 10  | TanStack Query for client-side caching / refetch / optimistic UI (not Redux)? | **Decided: not now (2026-10-16).** Reads happen in server components (orders, account, addresses, wishlist, product pages); the browser reads only the checkout quote, the cart prices and the address book after an edit, and everything else is form submissions followed by `router.refresh()` or local state. TanStack would add a second client cache next to RSC + `router.refresh()` to replace two small hooks. **Adopt when** any of these appears: something polled (live order tracking, image-generation progress), the same client data in several places at once (e.g. cart prices in header, cart and checkout), client-side pagination or filtering of the catalogue, or optimistic updates with rollback in several places |
| 11  | Is the Stripe PaymentIntent flow correct?                                                  | **Done (2026-10-16).** Sound before: the gateway creates the order first and reads the intent's amount from it (`api_gateway/routes/checkout_routes.py`), so the client never states an amount; payment-service creates, captures and refunds with per-order Stripe idempotency keys and `capture_method: manual`, matching the Element's `captureMethod`; the client secret stays in memory, a reload resumes the stored order, a changed cart/address/shipping cancels the old order, a decline leaves it open for another card, and a 409 tells "already paid" from "cancelled". Fixed: (a) a ref blocks a second submit at once, and placing/resuming the order runs under a Web Lock (`withCheckoutLock`, `lib/pending-checkout.ts`) so a second tab waits and resumes the first tab's order; a confirm that Stripe refuses because another tab already paid the intent counts as placed; (b) `return_url` is now `/checkout/complete`, which reads the PaymentIntent's status from Stripe (`retrievePaymentIntent`, not `redirect_status`), clears the cart and pending checkout when placed, keeps both and links back to checkout when not, and strips the client secret from the address bar; (c) when the placed order's `amount_cents` differs from the quote, the form shows the order's amounts, updates the Element's amount and stops; the next click resumes the same order and pays it; (d) the `paymentIntent` store, its type and its storage key are gone; (e) the pending checkout is a `LocalStorageStore`. **Verified live (Chrome, Stripe test mode):** two submits in one tick made one `POST /checkout`; a quote tampered to $1 under the order showed the order's $39.25 and made no confirm call; the return page with that unpaid intent showed the failure and kept cart and pending; back at checkout the same order was resumed and paid in-page; the return page with the paid intent showed "Order placed" and cleared both. **Not exercised:** a real 3-D Secure redirect, two real tabs racing, the "already paid in another tab" confirm error. **Left as is:** the superseded-order cancel stays best effort (the saga timeout is the backstop). **Two tabs, fixed 2026-10-17:** the pending checkout was one slot, so a tab checking out to another address cancelled the order a second tab might be paying. Now one entry per fingerprint (`PendingCheckouts`, with the PaymentIntent id), and each tab holds a shared Web Lock per order it uses (`OrderClaims`, `lib/pending-checkout.ts`; the browser releases it when the tab closes). A superseded order is cancelled only when that lock can be taken exclusively, i.e. no open tab uses it; the return page forgets only the paid order's entry. Verified in Chrome with Stripe test mode: tab B (other phone) left tab A's open order pending; after A closed, a third tab's order cancelled A's and left B's (still open) alone. Fixed 2026-10-18: a tab sent to a 3-D Secure, bank or wallet page releases its claim while it is away, so another tab's checkout could cancel that order meanwhile. Before `confirmPayment` the order's pending entry is marked `awayUntil` (30 min, order-service's `ORDER_SAGA_TIMEOUT_SECONDS`), and the sweep skips marked orders; the mark is cleared when `confirmPayment` returns without a redirect and by `/checkout/complete` when the payment failed or is incomplete (kept when Stripe could not be asked). Verified in Chrome with Stripe test mode: tab A paid with Affirm (a real redirect to Affirm's sandbox, no claim left), tab B checked out with other shipping and a test card, and A's order stayed pending; with the skip taken out, the same run cancelled A. Not covered live: the return page clearing the mark after a failed redirect (closing Affirm's sandbox page hung the tab) |
| 12  | Cart page shows the price an item had when it was added? | **Done (2026-10-16).** A cart line saved `variant.retail_price ?? product.price` once and nothing refreshed it, so a catalogue reprice (e.g. the CJ price refresh) left the cart page showing an old price while checkout charged the new one. The cart page now prices its lines on the server (`useCartPricing` → public, rate-limited `POST /api/v1/cart/prices` → order-service `POST /orders/price-items`, the item half of `OrderPricingService.build_quote`, so cart and checkout cannot disagree) and saves those prices into the cart. Order-service no longer passes product-service's internal URL in a refused quote's error. **Per line since 2026-10-17:** a line that cannot be sold (product, variant or stock gone, or a custom design the image service did not sign) comes back `available: false` with the reason, the others keep their prices, and the subtotal counts only those (`OrderPricingService.price_cart_lines`: one product-service call as before; only after a refusal is each line priced alone, at most 5 at once; lines refused only together, e.g. two of one product over its stock, keep the cart-wide refusal). The cart marks the line, says why the subtotal leaves it out and disables Checkout until it is removed; the reason (it names ids) goes to the console. The checkout quote and the order stay all or nothing. Tests: `npm run test:cart-pricing` (6, live stack, no mocks: per-line marking, a forged custom design, the checkout quote still refusing) and 4 order-service unit tests. Not covered live: a correctly signed custom line (needs a real generated design; the unit tests sign one) |
