# Design Patterns Catalogue

Where each pattern applies in this store (print-on-demand apparel: CJ dropshipping +
in-house printing, AI-generated artwork, Stripe payments, event-driven microservices).

**Status legend**
- **IN USE** — already in the codebase; follow it, don't reinvent it.
- **APPLY** — a concrete spot in this codebase where the pattern fits and is not yet used.
- **WATCH** — fits only if the requirement appears; don't add speculatively.

**Rules of thumb**
1. Reach for a pattern only when it removes a real `if/elif` ladder, duplicated
   code, or a hard dependency on a third party. Three similar lines beat a premature abstraction.
2. Every pattern must be typed: no `Any`; use `Generic[T]`, `Protocol`, PEP 695 syntax
   (`class Foo[T]:`) on the backend, TS generics on the frontend.
3. Layering is fixed: `routes → service_layer → database_layer → models`. Patterns live
   *inside* a layer or at its boundary; they never let a lower layer import a higher one.

---

# Backend

## 1. Architectural / distributed patterns

| Pattern | Status | Where | Notes |
| --- | --- | --- | --- |
| **Transactional Outbox** | IN USE | `shared/outbox/relay.py`, `shared/outbox/worker.py`, per-service `outbox_worker.py`, `models/outbox_models.py` | Events are written in the same DB transaction as the state change, then relayed at-least-once. Every new event MUST go through the outbox — never publish to RabbitMQ directly from a request handler. |
| **Saga (orchestrated/choreographed)** | IN USE | `order_service/saga_timeout_worker.py`, `order_service/events_consumer/`, `payment_service`, `product_service` (inventory reservation) | Checkout = order → reserve stock → authorize payment → pay CJ → capture. Each step needs a compensating action (release stock, void auth, cancel order). Add new steps as event handlers + compensations, never as synchronous cross-service calls. |
| **Idempotent Consumer** | IN USE | `shared/idempotency/idempotency_service.py` | Required on every consumer because the outbox is at-least-once. Key = event id. |
| **API Gateway / Facade** | IN USE | `api_gateway/gateway/apigateway.py`, `routes/*` | Frontend talks only to the gateway. Aggregation endpoints (e.g. checkout) belong here, not in the frontend. |
| **Repository** | IN USE | every `database_layer/*_repository.py`, `shared/database_layer/database_layer.py` | Only repositories touch SQLAlchemy sessions. Services never build queries. |
| **Unit of Work** | IN USE | `shared/managers/database_session_manager.py` (`transaction()` context) | One transaction per use case; outbox row + business row commit together. |
| **Service Layer** | IN USE | every `service_layer/` | Use-case orchestration, no HTTP and no SQL. |
| **Competing Consumers / Work Queue** | IN USE | Taskiq `tasks/broker.py` (notification, product image tasks) | Use for slow or retryable side effects: email, image processing. |
| **Circuit Breaker + Retry w/ backoff** | APPLY | Outbound clients: CJ API (`supplier_service`), Stripe (`payment_service`), `OpenRouterClient`, `artwork_asset_client.py` | Wrap each third-party client so a CJ/OpenRouter outage fails fast and the saga compensates instead of hanging requests. Backoff already exists in `OutboxRelay`; extract a reusable decorator/class. |
| **CQRS-lite (read models)** | WATCH | Product listing / admin graphs (`getGraphData`) | Only if list/search queries start hurting. Today a repository read method is enough. |
| **Event Sourcing** | WATCH | — | Do not adopt; the outbox + status enums cover the audit need. |
| **Anti-Corruption Layer** | APPLY | `SupplierProductMapper`, CJ payloads | Keep CJ's field names/currency (USD) confined to the supplier service; translate to our contracts in `shared/contracts/`. Applies to Stripe objects in `payment_service` too. |

## 2. Creational patterns

| Pattern | Status | Where | Notes |
| --- | --- | --- | --- |
| **Dependency Injection** | IN USE | `*/dependencies/dependencies.py` (FastAPI `Depends`) | Constructor injection of repositories/clients into services; never instantiate clients inside a method. |
| **Factory / Factory Method** | APPLY | (a) `dependencies.py` builders; (b) supplier/fulfillment selection per order line (CJ vs local warehouse vs in-house print); (c) payment provider by name | One `FulfillmentStrategyFactory.for_line(line) -> FulfillmentStrategy` instead of branching in `OrderService`. |
| **Abstract Factory** | WATCH | Per-environment client families (real vs sandbox Stripe+CJ) | Only if sandbox/prod switching grows beyond settings. |
| **Builder** | APPLY | Building the CJ order payload, Stripe PaymentIntent params, order confirmation emails, filter/query specs (`filter_parser.py`) | Use where an object has many optional parts and validation at `build()`. |
| **Singleton (via DI, not module globals)** | IN USE | `resources.py` per service holds long-lived Redis/DB/broker managers | Owned by app lifespan and injected. Never `global` state or `__new__` singletons. |
| **Prototype** | — | — | Not needed. |

## 3. Structural patterns

| Pattern | Status | Where | Notes |
| --- | --- | --- | --- |
| **Adapter** | IN USE / APPLY | `ImageGenerationInterface` (ABC) → `ImageGenerationService` → `OpenRouterClient`; APPLY to Stripe and CJ | Define a domain-facing interface (`PaymentGateway`, `SupplierGateway`, `ShippingRateProvider`), one adapter per vendor. Lets you test without mocking Stripe internals and swap vendors. |
| **Facade** | IN USE | API Gateway; `ImageGenerationService` | Hide multi-step vendor flows (CJ `confirmOrder` + `payBalance`) behind one method. |
| **Decorator** | APPLY | Caching (`cache_manager.py`), rate limiting (`ratelimit_manager.py`), idempotency, retry/circuit-breaker | Wrap a service/repository with the same interface: `CachedProductRepository(ProductRepository)`. Keeps cache logic out of business code. |
| **Proxy** | APPLY | Lazy/remote access to artwork assets; access control on internal endpoints (`internal_access_helper.py`) | Same interface as the real object, adds guard/lazy-load. |
| **Composite** | APPLY | Order = lines; a line can be catalog, CJ-dropship, or custom print (`LineFulfillmentStatus` doc-string). Cart/pricing totals | Treat single line and whole order uniformly for `total()`, `status()`, `can_cancel()`. |
| **Bridge** | WATCH | Notification channel (email/SMS/push) × notification type | Only when a second channel appears. |
| **Flyweight** | — | — | Not needed. |
| **Mixin / composition** | IN USE | `shared/database_layer/repository_mixins.py` (`LockableRepositoryMixin[ModelType]`), `models_mixins.py` | Compose repository capabilities (locking, filtering, pagination) instead of a deep inheritance tree. Per CLAUDE.md: break complex classes via inheritance/composition/decomposition. |

## 4. Behavioural patterns

| Pattern | Status | Where | Notes |
| --- | --- | --- | --- |
| **State** | IN USE (as enums) / APPLY | `OrderStatus`, `PaymentStatus`, `LineFulfillmentStatus`, `ProductionJobStatus` in `shared/enums/status_enums.py` | The enums encode `terminal()`, `blocks_cancellation()`. Next step: a transition table (`allowed_transitions: dict[Status, frozenset[Status]]`) or State classes so illegal transitions (e.g. `DELIVERED → QUEUED`, refund after capture rules) are rejected in one place. |
| **Strategy** | IN USE / APPLY | `SupplierRetailPricing` (`shared/utils/supplier_pricing.py`, uses `Protocol`); APPLY to: shipping-rate selection, tax (today `tax_amount = 0`; Stripe Tax later), discount/promo rules, image style presets, low-balance alert channel | Interface + interchangeable implementations chosen via factory/config. The tax slot is a textbook fit: `TaxStrategy` → `NoTax`, `StripeTax`. |
| **Chain of Responsibility** | APPLY | Checkout validation (stock → address → shipping option → price re-check → fraud), gateway middleware (`auth_middleware`, `cache_middleware`, logging, host validation) | Each link validates one concern and passes on; add a link without touching the others. |
| **Observer / Pub-Sub** | IN USE | RabbitMQ events; `event_publisher.py`, `*_event_consumer.py` | The event catalogue is `shared/enums/event_enums.py` + `shared/contracts/events.py`. Add events there first. |
| **Command** | APPLY | Saga steps and their compensations as objects (`ReserveStock`, `AuthorizePayment`, `PayCjOrder` each with `execute()` / `compensate()`); `CjOrderAttempt` records already model a retryable command | Makes retry, timeout and rollback uniform. |
| **Template Method** | APPLY | Event consumers (`order_event_consumer`, `supplier_event_consumer`, …): fixed skeleton *dedupe → parse → handle → ack/nack → log*, subclass supplies `handle()` | Removes the copy-pasted skeleton in the 24–32 KB consumer files. |
| **Mediator / Event Router** | IN USE | `EventRouter` callable in `shared/outbox/relay.py`; per-service routing function | Keep routing a lookup `dict[EventType, Handler]`, not an `if/elif` chain. |
| **Specification** | APPLY | Product filtering/search (`filter_parser.py`), eligibility rules (can-cancel, promo-applicable, refundable) | Composable predicates (`and_`, `or_`) that also translate to SQLAlchemy `where` clauses. |
| **Iterator / Generator** | APPLY | Paged CJ catalogue sync (`supplier_sync_state`), outbox batches | Yield pages lazily instead of loading full catalogue. |
| **Visitor** | — | — | Not needed. |
| **Memento** | WATCH | Generation-session undo (frontend), order edit history | Only if undo/history is a requirement. |
| **Null Object** | APPLY | `NoTax`, `NoDiscount`, `NoopNotifier` | Replaces `if x is None` branches (tax slot at 0 is exactly this). |

## 5. Domain-mapping cheat sheet (backend)

| Business capability | Service | Patterns to use |
| --- | --- | --- |
| Checkout & order placement | order / api_gateway | Saga, Command, Chain of Responsibility, Unit of Work, Outbox |
| Payment authorize → capture → refund | payment | Adapter (`PaymentGateway`), State, Idempotent Consumer, Circuit Breaker |
| CJ order + balance payment + retry | supplier | Adapter, Command (`CjOrderAttempt`), Circuit Breaker, Template Method (consumer), Facade |
| Fulfillment routing (CJ / warehouse / in-house) | order + supplier + product | Strategy + Factory, Composite (lines), State |
| Shipping quotes (live CJ freight) | shipping | Strategy, Adapter, Decorator (cache quotes) |
| Pricing (retail markup, currency, tax, promos) | shared / order | Strategy, Null Object, Decorator (promo stacking), `shared/utils/money.py` value object |
| Inventory reservation | product | Repository + `LockableRepositoryMixin`, Saga compensation, State |
| Catalogue sync from supplier | supplier / product | Anti-Corruption Layer (`SupplierProductMapper`), Iterator, Idempotent Consumer |
| AI artwork generation | product | Adapter (`ImageGenerationInterface`), Strategy (style presets), Proxy (quota — `GenerationQuotaService`), Job store |
| Notifications (email) | notification | Observer, Template Method, Bridge (if more channels), Taskiq work queue |
| Caching / rate limiting | gateway + shared | Decorator, Proxy |
| Auth & sessions | user | Chain of Responsibility (middleware), Strategy (token vs session) |
| Wishlist / cart | wishlist / cart | Repository, Composite (line items), Memento (optional) |

## 6. Value objects & typing

- `Money` (amount + currency) as a frozen dataclass wrapping `shared/utils/money.py`;
  never pass bare `float`/`Decimal` + separate currency string. This directly prevents
  the earlier USD-sold-as-CAD bug.
- Use `Protocol` for structural ports (as `_PricingSettings` does) and `ABC` when a
  shared base implementation is needed.
- Generics with latest syntax: `class Repository[ModelT: DeclarativeBase]:`, `type EventHandler = Callable[[EventPayload], Awaitable[None]]`.

---

# Frontend (Next.js / TypeScript)

| Pattern | Status | Where | Notes |
| --- | --- | --- | --- |
| **Provider / Context (DI)** | IN USE | `providers/CartProvider.tsx`, `hooks/useCart.tsx` | Cross-cutting state. Keep one context per concern. |
| **Controller class (MVC-style)** | IN USE | `lib/generation-session-controller.ts` | Framework-free class owning session logic; components stay thin. Use for other stateful flows (checkout, production queue). |
| **Custom hook = Facade** | IN USE | `hooks/use*.ts` | Hook hides fetching + state; component consumes a small API. |
| **Server Actions / API client (Repository-like)** | IN USE | `actions/get*.ts` | Data access only; no UI logic. Promote to a typed `ApiClient<T>` class with one `request<TRes, TReq>()` method. |
| **Type guards / Validator** | IN USE | `isGeneratedDesignPayload` | Validate every boundary payload (localStorage, API) instead of casting. |
| **Adapter (DTO → view model)** | APPLY | `utils/productVariants.ts`, `formatPrice.ts`, `types/*` | Map API shapes to UI models in one place so components never see raw backend fields. |
| **Strategy** | APPLY | Price/variant display, sort/filter rules, style options | Object map keyed by type instead of `switch` in JSX. |
| **Observer (event emitter / store)** | APPLY | Cart + generation counter across tabs (`localStorage` events) | A small typed `Store<T>` with `subscribe()`; consider only if Context re-renders hurt. |
| **State machine** | APPLY | `GenerationPhase`, checkout steps, order tracking | Typed transition table (discriminated union) instead of boolean flags. |
| **Composite / Compound components** | APPLY | Product card, order line, admin tables (`components/0. Admin`) | Compose `<Card><Card.Image/><Card.Price/></Card>`. |
| **Decorator (HOC / wrapper)** | WATCH | Auth-guard, error boundary | Prefer layout/middleware guards in the App Router first. |
| **Factory** | APPLY | Building form-field configs (`types/inputs.ts`), toast/notification creation | Typed factory returning a discriminated union. |

**Frontend typing rules:** no `any` (existing `Props { [propName: string]: any }` in
`useCart.tsx` and `localStorage` `any` reads are debt to remove); use generics such as
`ApiResponse<T>`, `Store<T>`, `Result<T, E>`; use discriminated unions for states.

---

# Adding a new pattern — checklist

1. Name the concrete problem (the `if/elif` ladder, duplication, or vendor coupling).
2. Check this file: is there already an IN USE implementation? Extend it.
3. Put it in the correct layer; define the interface (Protocol/ABC/TS interface) first.
4. Fully type it, no `Any`; comment any nested logic (per CLAUDE.md).
5. Unit-test the pattern seam with a fake adapter; do not mock critical payment/saga
   scenarios — ask first (CLAUDE.md).
6. Update the status column here.
