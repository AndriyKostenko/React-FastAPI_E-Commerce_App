# Flows & Diagrams

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                    USER REGISTRATION FLOW                                                     │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────┐     ┌────────────────────────────────────────┐     ┌──────────────────┐     ┌──────────────┐     ┌─────────────┐     ┌─────────────┐
│  CLIENT  │     │             API-GATEWAY :8000          │     │  USER-SERVICE    │     │   RABBITMQ   │     │NOTIFICATION │     │  MAILSERVER │
│          │     │                                        │     │  :8001           │     │              │     │  -CONSUMER  │     │             │
└────┬─────┘     └────────────────────┬───────────────────┘     └────────┬─────────┘     └──────┬───────┘     └──────┬──────┘     └──────┬──────┘
     │                                │                                  │                      │                    │                   │
     │                                │                                  │                      │                    │                   │
     │                                │                                  │                      │                    │                   │
     │─────────────────────────────────────────── PHASE 1: REGISTRATION ──────────────────────────────────────────────────────────────────────────
     │                                │                                  │                      │                    │                   │
     │  POST :8000/api/v1/register    │                                  │                      │                    │                   │
     │  { name, email, password,      │                                  │                      │                    │                   │
     │    role }                      │                                  │                      │                    │                   │
     │──────────────────────────────> │                                  │                      │                    │                   │
     │                                │                                  │                      │                    │                   │
     │                      ┌─────────┴─────────────────┐                │                      │                    │                   │
     │                      │   MIDDLEWARE CHAIN         │               │                      │                    │                   │
     │                      │                            │               │                      │                    │                   │
     │                      │  1. AuthMiddleware         │               │                      │                    │                   │
     │                      │     path="/api/v1/register"│               │                      │                    │                   │
     │                      │     is_public_endpoint()?  │               │                      │                    │                   │
     │                      │     ✅ YES (POST in whitelist)             │                      │                    │                   │
     │                      │     → skip JWT validation  │               │                      │                    │                   │
     │                      │                            │               │                      │                    │                   │
     │                      │  2. GatewayMiddleware      │               │                      │                    │                   │
     │                      │     global rate limit check│               │                      │                    │                   │
     │                      │     max 1000 req/60s       │               │                      │                    │                   │
     │                      │     → 429 if exceeded      │               │                      │                    │                   │
     │                      └─────────┬─────────────────┘                │                      │                    │                   │
     │                                │                                  │                      │                    │                   │
     │                      ┌─────────┴─────────────────┐                │                      │                    │                   │
     │                      │  register_user()           │               │                      │                    │                   │
     │                      │  → api_gateway_manager     │               │                      │                    │                   │
     │                      │    .forward_request(       │               │                      │                    │                   │
     │                      │      "user-service")       │               │                      │                    │                   │
     │                      │                            │               │                      │                    │                   │
     │                      │  ApiGateway internals:     │               │                      │                    │                   │
     │                      │  1. extract_service_path() │               │                      │                    │                   │
     │                      │     /api/v1/register       │               │                      │                    │                   │
     │                      │     → /register            │               │                      │                    │                   │
     │                      │  2. build_url()            │               │                      │                    │                   │
     │                      │     random instance pick   │               │                      │                    │                   │
     │                      │     (load balancing ready) │               │                      │                    │                   │
     │                      │     → http://user-service: │               │                      │                    │                   │
     │                      │       8001/api/v1/register │               │                      │                    │                   │
     │                      │  3. detect body type       │               │                      │                    │                   │
     │                      │     application/json       │               │                      │                    │                   │
     │                      │  4. strip headers          │               │                      │                    │                   │
     │                      │     (host, content-length) │               │                      │                    │                   │
     │                      │  5. @circuit breaker guard │               │                      │                    │                   │
     │                      │     (5 failures → open 30s)│               │                      │                    │                   │
     │                      └─────────┬─────────────────┘                │                      │                    │                   │
     │                                │                                  │                      │                    │                   │
     │                                │  httpx POST                      │                      │                    │                   │
     │                                │  /api/v1/register                │                      │                    │                   │
     │                                │  { name, email, password, role } │                      │                    │                   │
     │                                │─────────────────────────────────>│                      │                    │                   │
     │                                │                                  │                      │                    │                   │
     │                                │                         ┌────────┴──────────────────┐   │                    │                   │
     │                                │                         │  RATE LIMIT               │   │                    │                   │
     │                                │                         │  5 req / 1hr per IP       │   │                    │                   │
     │                                │                         └────────┬──────────────────┘   │                    │                   │
     │                                │                                  │                      │                    │                   │
     │                                │                         ┌────────┴──────────────────┐   │                    │                   │
     │                                │                         │  UserService.create_user()│   │                    │                   │
     │                                │                         │                           │   │                    │                   │
     │                                │                         │  1. check email duplicate │   │                    │                   │
     │                                │                         │     → 409 if exists       │   │                    │                   │
     │                                │                         │  2. bcrypt hash password  │   │                    │                   │
     │                                │                         │  3. INSERT user to DB     │   │                    │                   │
     │                                │                         │     is_verified = False   │   │                    │                   │
     │                                │                         │  4. create JWT token      │   │                    │                   │
     │                                │                         │     purpose=              │   │                    │                   │
     │                                │                         │     "email_verification"  │   │                    │                   │
     │                                │                         └────────┬──────────────────┘   │                    │                   │
     │                                │                                  │                      │                    │                   │
     │                                │                                  │  publish             │                    │                   │
     │                                │                                  │  "user.registered"   │                    │                   │
     │                                │                                  │  { event_id, ts,     │                    │                   │
     │                                │                                  │    user_email,       │                    │                   │
     │                                │                                  │    token }           │                    │                   │
     │                                │                                  │────────────────────> │                    │                   │
     │                                │                                  │                      │  user.events       │                   │
     │                                │                         HTTP 201 │                      │───────────────────>│                   │
     │                                │<─────────────────────────────────│                      │                    │                   │
     │                                │  { id, name, email,              │                      │  json.loads(body)  │                   │
     │                                │    is_verified: false, ... }     │                      │  "user.registered" │                   │
     │  HTTP 201                      │                                  │                      │                    │                   │
     │  { id, name, email,            │                                  │                      │   send_verification│                   │
     │    is_verified: false }        │                                  │                      │   _email(event)    │                   │
     │<───────────────────────────────│                                  │                      │───────────────────────────────────────>│
     │                                │                                  │                      │                    │  📧 "Verify Email"│
     │                                │                                  │                      │                    │  [activate_url    │
     │                                │                                  │                      │                    │   /api/v1/activate│
     │                                │                                  │                      │                    │   /{JWT}]         │
     │                                │                                  │                      │                    │                   │
     │                                │                                  │                      │                    │                   │
     │─────────────────────────────────────────── PHASE 2: EMAIL VERIFICATION ───────────────────────────────────────────────────────────────────
     │                                │                                  │                      │                    │                   │
     │  User clicks email link        │                                  │                      │                    │                   │
     │  POST :8000/api/v1/activate    │                                  │                      │                    │                   │
     │       /{JWT_token}             │                                  │                      │                    │                   │
     │──────────────────────────────>│                                  │                      │                    │                   │
     │                                │                                  │                      │                    │                   │
     │                      ┌─────────┴─────────────────┐               │                      │                    │                   │
     │                      │   MIDDLEWARE CHAIN         │               │                      │                    │                   │
     │                      │                            │               │                      │                    │                   │
     │                      │  1. AuthMiddleware         │               │                      │                    │                   │
     │                      │     path="/api/v1/activate/│               │                      │                    │                   │
     │                      │     is_public_endpoint()?  │               │                      │                    │                   │
     │                      │     ✅ YES (prefix match)  │               │                      │                    │                   │
     │                      │     → skip JWT validation  │               │                      │                    │                   │
     │                      │                            │               │                      │                    │                   │
     │                      │  2. GatewayMiddleware      │               │                      │                    │                   │
     │                      │     global rate limit check│               │                      │                    │                   │
     │                      └─────────┬─────────────────┘               │                      │                    │                   │
     │                                │                                  │                      │                    │                   │
     │                                │  httpx POST                      │                      │                    │                   │
     │                                │  /api/v1/activate/{token}        │                      │                    │                   │
     │                                │─────────────────────────────────>│                      │                    │                   │
     │                                │                                  │                      │                    │                   │
     │                                │                         ┌────────┴──────────────────┐   │                    │                   │
     │                                │                         │  RATE LIMIT               │   │                    │                   │
     │                                │                         │  5 req / 1hr per IP       │   │                    │                   │
     │                                │                         └────────┬──────────────────┘   │                    │                   │
     │                                │                                  │                      │                    │                   │
     │                                │                         ┌────────┴──────────────────┐   │                    │                   │
     │                                │                         │ UserService.verify_email()│   │                    │                   │
     │                                │                         │                           │   │                    │                   │
     │                                │                         │  1. decode JWT            │   │                    │                   │
     │                                │                         │     validate purpose=     │   │                    │                   │
     │                                │                         │     "email_verification"  │   │                    │                   │
     │                                │                         │     → 401 if invalid/exp  │   │                    │                   │
     │                                │                         │  2. UPDATE user           │   │                    │                   │
     │                                │                         │     is_verified = True    │   │                    │                   │
     │                                │                         └────────┬──────────────────┘   │                    │                   │
     │                                │                                  │                      │                    │                   │
     │                                │                                  │  publish             │                    │                   │
     │                                │                                  │  "user.email.        │                    │                   │
     │                                │                                  │   verified"          │                    │                   │
     │                                │                                  │  { event_id, ts,     │                    │                   │
     │                                │                                  │    user_email }      │                    │                   │
     │                                │                                  │────────────────────> │                    │                   │
     │                                │                                  │                      │  user.events       │                   │
     │                                │                         HTTP 200 │                      │───────────────────>│                   │
     │                                │<─────────────────────────────────│                      │                    │                   │
     │                                │  { detail: "Email verified",     │                      │  "user.email.      │                   │
     │                                │    email, verified: true }       │                      │   verified"        │                   │
     │  HTTP 200                      │                                  │                      │                    │                   │
     │  { detail: "Email verified",   │                                  │                      │  send_email_       │                   │
     │    email, verified: true }     │                                  │                      │  verified_         │                   │
     │<───────────────────────────────│                                  │                      │  notification(event│                   │
     │                                │                                  │                      │───────────────────────────────────────>│
     │                                │                                  │                      │                    │  📧 "You're All   │
     │                                │                                  │                      │                    │  Set! ✅"         │
     │                                │                                  │                      │                    │  [Go to Login]    │

```

Every request through the gateway passes this chain in order:
```
┌─────────────────────────────────────────────────────────────────┐
│                    MIDDLEWARE EXECUTION ORDER                    │
│                                                                 │
│  1. AuthMiddleware                                              │
│     ├── is_public_endpoint(path, method)?                       │
│     │    ├── YES → pass through (register, activate, login...)  │
│     │    └── NO  → extract Bearer token from Authorization      │
│     │              → token_manager.decode_token()               │
│     │              → attach user to request.state.current_user  │
│     │              → 401 if missing / invalid / expired         │
│     │                                                           │
│  2. GatewayMiddleware                                           │
│     └── global rate limit: 1000 req / 60s (Redis)              │
│         → 429 if exceeded                                       │
│                                                                 │
│  3. Route handler (e.g. register_user)                          │
│     └── ApiGateway.forward_request("user-service")             │
│          ├── extract_service_path()  strip /api/v1 prefix       │
│          ├── build_url()             random instance pick       │
│          ├── _detect_and_prepare_body()  JSON/form/multipart    │
│          ├── _prepare_headers()      strip host, content-length │
│          ├── @circuit(5 fail → open 30s)                        │
│          └── httpx.request() → downstream service              │
└─────────────────────────────────────────────────────────────────┘
```

## RabbitMQ Queue Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            RabbitMQ Queu                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────┐                                               │
│  │  order.events.queue      │◄──── OrderService (publishes)                │
│  │  (DLQ: order.events.dlq) │     - OrderCreatedEvent                       │
│  └──────────────────────────┘     - OrderConfirmedEvent                     │
│           │                       - OrderCancelledEvent                     │
│           │                                                                │
│           ▼                                                                │
│  ┌──────────────────────────┐                                               │
│  │  Notification Service    │     Handles email notifications               │
│  └──────────────────────────┘                                               │
│                                                                             │
│  ┌──────────────────────────┐                                               │
│  │  product.inventory.events│◄──── OrderService (publishes)                │
│  │  (DLQ: ...events.dlq)    │     - InventoryReserveRequested               │
│  └──────────────────────────┘     - InventoryReleaseRequested               │
│           │                                                                │
│           ▼                                                                │
│  ┌──────────────────────────┐                                               │
│  │  Product Service         │     Reserves/releases inventory               │
│  └──────────────────────────┘                                               │
│                                                                             │
│  ┌──────────────────────────┐                                               │
│  │  order.saga.response     │◄──── Product Service (publishes)             │
│  │  (DLQ: ...response.dlq)  │     - InventoryReserveSucceeded               │
│  └──────────────────────────┘     - InventoryReserveFailed                  │
│           │                                                                │
│           ▼                                                                │
│  ┌──────────────────────────┐                                               │
│  │  Order Service (Consumer)│     Confirms/cancels order                    │
│  └──────────────────────────┘                                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```



## Checkout, Payment & CJ Fulfillment Flow

The card is **authorized** at checkout and **captured** only once the goods are
secured, so a failed fulfillment voids a hold instead of refunding a charge.
The order is created *before* the PaymentIntent, and the intent's amount is
read from that order; the client never states an amount.

### 1. Price the cart for an address

```
┌──────────┐        ┌──────────────┐        ┌───────────────┐        ┌─────────────────┐   ┌──────────────────┐
│  CLIENT  │        │ API-GATEWAY  │        │ ORDER-SERVICE │        │ PRODUCT-SERVICE │   │ SUPPLIER-SERVICE │
└────┬─────┘        └──────┬───────┘        └───────┬───────┘        └────────┬────────┘   └────────┬─────────┘
     │ POST /checkout/quote │                        │                         │                     │
     │ {products, address,  │                        │                         │                     │
     │  shipping_logistic_  │                        │                         │                     │
     │  name?}              │                        │                         │                     │
     │─────────────────────>│ POST /orders/quote     │                         │                     │
     │                      │───────────────────────>│ POST /products/         │                     │
     │                      │                        │   order-quote           │                     │
     │                      │                        │────────────────────────>│ CAD retail prices   │
     │                      │                        │<────────────────────────│                     │
     │                      │                        │ POST /cjdropshipping/freight/quote (CJ lines)  │
     │                      │                        │───────────────────────────────────────────────>│ CJ freightCalculate
     │                      │                        │<───────────────────────────────────────────────│ USD options
     │                      │                        │ shipping = CJ option (USD x buffer x FX)       │
     │                      │                        │          + flat domestic rate (custom/catalog) │
     │  {subtotal, shipping,│                        │                         │                     │
     │   tax=0, amount,     │<───────────────────────│                         │                     │
     │   shipping_options}  │                        │                         │                     │
     │<─────────────────────│                        │                         │                     │
```

### 2. Place the order and authorize the card

```
┌──────────┐        ┌──────────────┐        ┌───────────────┐        ┌─────────────────┐        ┌──────────┐
│  CLIENT  │        │ API-GATEWAY  │        │ ORDER-SERVICE │        │ PAYMENT-SERVICE │        │  STRIPE  │
└────┬─────┘        └──────┬───────┘        └───────┬───────┘        └────────┬────────┘        └────┬─────┘
     │ POST /checkout       │                        │                         │                      │
     │ {products, address,  │                        │                         │                      │
     │  shipping_logistic_  │ POST /orders           │                         │                      │
     │  name}               │ (user from token)      │                         │                      │
     │─────────────────────>│───────────────────────>│ re-quote server-side    │                      │
     │                      │                        │ INSERT order PENDING    │                      │
     │                      │                        │ saga{payment: pending}  │                      │
     │                      │                        │ outbox: order.created,  │                      │
     │                      │                        │  inventory.reserve.requested                   │
     │                      │<───────────────────────│ {id, amount_cents, ...} │                      │
     │                      │ POST /payments/create-intent (amount = order.amount_cents)              │
     │                      │─────────────────────────────────────────────────>│ PaymentIntent        │
     │                      │                        │                         │ capture_method=manual│
     │                      │                        │                         │─────────────────────>│
     │  {order_id,          │<─────────────────────────────────────────────────│ client_secret        │
     │   client_secret}     │                        │                         │                      │
     │<─────────────────────│                        │                         │                      │
     │ stripe.confirmPayment ──────────────────────────────────────────────────────────────────────>│ card AUTHORIZED
     │ (decline → retry the same order; POST /checkout {order_id} resumes it)                         │ (held, not charged)
     │                      │                        │                         │  webhook             │
     │                      │                        │                         │  amount_capturable_  │
     │                      │                        │                         │  updated             │
     │                      │                        │  payment.authorized     │<─────────────────────│
     │                      │                        │<────────────────────────│ status AUTHORIZED    │
     │                      │                        │ validate user/amount/   │                      │
     │                      │                        │ currency vs order       │                      │
     │                      │                        │ saga.payment=authorized │                      │
     │                      │                        │ + inventory reserved →  │                      │
     │                      │                        │ CONFIRMED, order.confirmed                     │
```

### 3. Secure fulfillment, then capture

```
┌───────────────┐        ┌──────────────────┐        ┌───────┐        ┌─────────────────┐        ┌──────────┐
│ ORDER-SERVICE │        │ SUPPLIER-SERVICE │        │  CJ   │        │ PAYMENT-SERVICE │        │  STRIPE  │
└───────┬───────┘        └────────┬─────────┘        └───┬───┘        └────────┬────────┘        └────┬─────┘
        │ no CJ lines: outbox payment.capture.requested right away ───────────>│                      │
        │                         │                      │                      │                      │
        │ order.confirmed         │                      │                      │                      │
        │ (CJ lines)              │                      │                      │                      │
        │────────────────────────>│ createOrderV2        │                      │                      │
        │                         │ payType=3,           │                      │                      │
        │                         │ customer's logistic  │                      │                      │
        │                         │─────────────────────>│ CREATED              │                      │
        │                         │ confirmOrder         │                      │                      │
        │                         │─────────────────────>│ UNPAID               │                      │
        │                         │ getOrderDetail: orderAmount <= expected max?│                      │
        │                         │ getBalance >= orderAmount?                  │                      │
        │                         │   no → AWAITING_FUNDS, CRITICAL log, retried every 5 min           │
        │                         │ payBalance           │                      │                      │
        │                         │─────────────────────>│ PAID (CJ ships)      │                      │
        │ cj.order.paid           │                      │                      │                      │
        │<────────────────────────│                      │                      │                      │
        │ CJ lines → SUBMITTED    │                      │                      │                      │
        │ (blocks self-cancel)    │                      │                      │                      │
        │ payment.capture.requested ──────────────────────────────────────────>│ capture (idempotent) │
        │                         │                      │                      │─────────────────────>│ CHARGED
        │                         │                      │  payment.succeeded   │                      │
        │<─────────────────────────────────────────────────────────────────────│                      │
        │ saga.payment=captured   │                      │                      │                      │
        │                         │ tracking poller: shipped / delivered → cj.order.shipped/delivered  │
```

### Failure paths

| When | What happens to the money |
|---|---|
| Card declined | Nothing: the order stays PENDING and the customer retries. The Saga timeout cancels abandoned orders. |
| Inventory reservation fails, CJ rejects, or CJ can't be paid within `CJ_PAYMENT_MAX_WAIT_HOURS` | `order.cancelled` → payment-service **voids** the authorization (no charge, no refund, no Stripe fee). |
| CJ bills above the expected maximum | CJ payment withheld (`reconciliation_required`); order stays confirmed and uncaptured for a human. |
| Card authorized for an unknown or cancelled order | order-service sends `payment.release.requested` → void. |
| Authorization lapses after CJ was paid | Order kept and flagged for reconciliation. The saga timeout worker alerts after `PAYMENT_CAPTURE_ALERT_HOURS` so capture can happen first. |
| Cancelled after capture | Refund, unless goods were already made or paid for (held for a human). |

### Key events

| Event | Publisher | Consumers | Purpose |
|---|---|---|---|
| `inventory.reserve.requested` / `.succeeded` / `.failed` | Order / Product | Product / Order | Stock gate |
| `payment.authorized` | Payment | Order | Card held for exactly the order total |
| `order.confirmed` | Order | Supplier, Notification, Shipping, Cart | Payment + stock gates passed |
| `cj.order.created` / `cj.order.paid` / `cj.order.failed` | Supplier | Order, Notification | CJ purchase lifecycle |
| `payment.capture.requested` | Order (order exchange) | Payment | Goods secured: charge the card |
| `payment.release.requested` | Order (order exchange) | Payment | Void/refund money held for an unfulfillable order |
| `payment.succeeded` | Payment | Order, Notification | Card captured |
| `payment.cancelled` / `payment.refunded` | Payment | Order, Notification | Hold voided / charge refunded |
| `order.cancelled` | Order | Payment, Supplier, Notification, … | Compensation |


[FastAPI Services]
    ↓
[FastStream (RabbitMQ)]
    → domain events

[Taskiq + aio-pika]
    → background tasks (same RabbitMQ)

[Redis]
    → cache / rate limit / idempotency only

## Login Flow

```
┌──────────┐     ┌──────────────────────┐     ┌──────────────────┐     ┌───────┐
│  CLIENT  │     │   API-GATEWAY :8000  │     │  USER-SERVICE    │     │ REDIS │
└────┬─────┘     └──────────┬───────────┘     └────────┬─────────┘     └───┬───┘
     │                        │                        │                   │
     │  POST /login           │                        │                   │
     │  username=email        │                        │                   │
     │  password=***          │                        │                   │
     │───────────────────────>│                        │                   │
     │                        │  AuthMiddleware:       │                   │
     │                        │  /login is public      │                   │
     │                        │  → skip JWT check      │                   │
     │                        │                        │                   │
     │                        │  GatewayMiddleware:    │                   │
     │                        │  rate limit 5/60s      │                   │
     │                        │                        │                   │
     │                        │  httpx POST /login     │                   │
     │                        │  OAuth2 form           │                   │
     │                        │───────────────────────>│                   │
     │                        │                        │                   │
     │                        │                        │  1. fetch user     │
     │                        │                        │  2. bcrypt verify  │
     │                        │                        │  3. generate       │
     │                        │                        │     access token   │
     │                        │                        │  4. generate       │
     │                        │                        │     refresh token  │
     │                        │                        │                   │
     │                        │                        │  store refresh     │
     │                        │                        │  token in Redis    │
     │                        │                        │──────────────────>│
     │                        │                        │                   │
     │                        │  HTTP 200              │                   │
     │                        │  { access_token,       │                   │
     │                        │    refresh_token, ...} │                   │
     │                        │<───────────────────────│                   │
     │                        │                        │                   │
     │                        │  set HttpOnly cookies: │                   │
     │                        │  - access_token        │                   │
     │                        │  - refresh_token       │                   │
     │                        │  (body keeps access    │                    │
     │                        │   for NextAuth)        │                   │
     │  HTTP 200 + cookies    │                        │                   │
     │<───────────────────────│                        │                   │
```

## Token Refresh Flow

```
┌──────────┐     ┌──────────────────────┐     ┌──────────────────┐     ┌───────┐
│  CLIENT  │     │   API-GATEWAY :8000  │     │  USER-SERVICE    │     │ REDIS │
└────┬─────┘     └──────────┬───────────┘     └────────┬─────────┘     └───┬───┘
     │                        │                        │                   │
     │  POST /refresh         │                        │                   │
     │  (refresh_token cookie)│                        │                   │
     │───────────────────────>│                        │                   │
     │                        │                        │                   │
     │                        │  read refresh cookie   │                   │
     │                        │  forward {refresh_token}│                  │
     │                        │───────────────────────>│                   │
     │                        │                        │                   │
     │                        │                        │  validate token   │
     │                        │                        │  check blacklist  │
     │                        │                        │  in Redis         │
     │                        │                        │─────────────────>│
     │                        │                        │<─────────────────│
     │                        │                        │                   │
     │                        │                        │  issue new access │
     │                        │  HTTP 200 {access_token│                   │
     │                        │   token_expiry}        │                   │
     │                        │<───────────────────────│                   │
     │                        │                        │                   │
     │                        │  set new access_token  │                   │
     │                        │  HttpOnly cookie       │                   │
     │  HTTP 200 + cookie     │                        │                   │
     │<───────────────────────│                        │                   │
```

## Logout Flow

```
┌──────────┐     ┌──────────────────────┐     ┌──────────────────┐     ┌───────┐
│  CLIENT  │     │   API-GATEWAY :8000  │     │  USER-SERVICE    │     │ REDIS │
└────┬─────┘     └──────────┬───────────┘     └────────┬─────────┘     └───┬───┘
     │                        │                        │                   │
     │  POST /logout          │                        │                   │
     │  (refresh_token cookie)│                        │                   │
     │───────────────────────>│                        │                   │
     │                        │                        │                   │
     │                        │  clear auth cookies    │                   │
     │                        │  immediately           │                   │
     │                        │                        │                   │
     │                        │  forward refresh token │                   │
     │                        │  to user-service       │                   │
     │                        │───────────────────────>│                   │
     │                        │                        │                   │
     │                        │                        │  add refresh token│
     │                        │                        │  to Redis blacklist│
     │                        │                        │─────────────────>│
     │                        │  HTTP 200              │                   │
     │                        │<───────────────────────│                   │
     │  HTTP 200              │                        │                   │
     │  cookies cleared       │                        │                   │
     │<───────────────────────│                        │                   │
```

## Password Reset Flow

### Request reset
```
┌──────────┐     ┌──────────────────────┐     ┌──────────────────┐     ┌─────────┐     ┌─────────────┐
│  CLIENT  │     │   API-GATEWAY :8000  │     │  USER-SERVICE    │     │ RABBITMQ│     │NOTIFICATION │
└────┬─────┘     └──────────┬───────────┘     └────────┬─────────┘     └────┬────┘     └──────┬──────┘
     │                        │                        │                    │                 │
     │ POST /forgot-password  │                        │                    │                 │
     │ { email }              │                        │                    │                 │
     │───────────────────────>│                        │                    │                 │
     │                        │ forward to user-service│                    │                 │
     │                        │───────────────────────>│                    │                 │
     │                        │                        │  generate reset    │                 │
     │                        │                        │  token             │                 │
     │                        │                        │                    │                 │
     │                        │                        │ publish            │                 │
     │                        │                        │ "user.password.    │                 │
     │                        │                        │  reset.requested"  │                 │
     │                        │                        │───────────────────>│                 │
     │                        │                        │                    │  consume event  │
     │                        │                        │                    │────────────────>│
     │                        │                        │                    │                 │
     │  HTTP 200              │                        │                    │                 │
     │  { email }             │                        │                    │                 │
     │<───────────────────────│                        │                    │                 │
     │                        │                        │                    │                 │  📧 reset email
```

### Confirm reset
```
┌──────────┐     ┌──────────────────────┐     ┌──────────────────┐     ┌─────────┐     ┌─────────────┐
│  CLIENT  │     │   API-GATEWAY :8000  │     │  USER-SERVICE    │     │ RABBITMQ│     │NOTIFICATION │
└────┬─────┘     └──────────┬───────────┘     └────────┬─────────┘     └────┬────┘     └──────┬──────┘
     │                        │                        │                    │                 │
     │ POST /password-reset/  │                        │                    │                 │
     │ {token}                │                        │                    │                 │
     │ { new_password }       │                        │                    │                 │
     │───────────────────────>│                        │                    │                 │
     │                        │ forward to user-service│                    │                 │
     │                        │───────────────────────>│                    │                 │
     │                        │                        │  validate token    │                 │
     │                        │                        │  bcrypt new pass   │                 │
     │                        │                        │  UPDATE user       │                 │
     │                        │                        │                    │                 │
     │                        │                        │ publish            │                 │
     │                        │                        │ "user.password.    │                 │
     │                        │                        │  reset.success"    │                 │
     │                        │                        │───────────────────>│                 │
     │                        │                        │                    │  send success   │
     │                        │                        │                    │  email          │
     │  HTTP 200              │                        │                    │                 │
     │<───────────────────────│                        │                    │                 │
```

## Google OAuth Login / Register Flow

```
┌──────────┐     ┌──────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│  CLIENT  │     │  GOOGLE IDP  │     │   API-GATEWAY :8000  │     │  USER-SERVICE    │
└────┬─────┘     └──────┬───────┘     └──────────┬───────────┘     └────────┬─────────┘
     │                  │                        │                        │
     │  Google Sign-In  │                        │                        │
     │  → get ID token  │                        │                        │
     │─────────────────>│                        │                        │
     │                  │                        │                        │
     │  ID token        │                        │                        │
     │<─────────────────│                        │                        │
     │                  │                        │                        │
     │  POST /google-login│                      │                        │
     │  { id_token }    │                        │                        │
     │─────────────────────────────────────────>│                        │
     │                  │                        │ forward to user-service│
     │                  │                        │───────────────────────>│
     │                  │                        │                        │
     │                  │                        │                        │  verify ID token
     │                  │                        │                        │  with Google
     │                  │                        │                        │
     │                  │                        │                        │  if new user:
     │                  │                        │                        │    create user
     │                  │                        │                        │  else:
     │                  │                        │                        │    fetch existing
     │                  │                        │                        │
     │                  │                        │                        │  generate tokens
     │                  │                        │                        │  store refresh
     │                  │                        │  HTTP 200 tokens       │
     │                  │                        │<───────────────────────│
     │                  │                        │                        │
     │                  │                        │  set HttpOnly cookies  │
     │                  │                        │                        │
     │  HTTP 200 + cookies                      │                        │
     │<─────────────────────────────────────────│                        │
```
```
User Service (publisher)
     │
     │ publish UserRegisteredEvent
     │ exchange: user.events.exchange
     │ routing key: user.registered
     ▼
┌─────────────────────────┐
│  user.events.exchange   │  <-- TOPIC exchange (router)
│      (one exchange)     │
└─────────────────────────┘
     │                 │
     │                 │
     ▼                 ▼
user.events.queue   wishlist.events.queue
routing key: user.#   routing key: user.deleted
     │                 │
     │                 │
     ▼                 ▼
Notification         Wishlist
Consumer             Consumer
```

## Order Cancellation Flow

```
┌──────────┐     ┌──────────────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  CLIENT  │     │   API-GATEWAY :8000  │     │  ORDER-SERVICE   │     │ PRODUCT-SERVICE  │     │ PAYMENT-SERVICE  │     │NOTIFICATION │
└────┬─────┘     └──────────┬───────────┘     └────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘     └──────┬──────┘
     │                        │                        │                        │                        │                 │
     │ PATCH /orders/{id}/    │                        │                        │                        │                 │
     │   cancel               │                        │                        │                        │                 │
     │───────────────────────>│                        │                        │                        │                 │
     │                        │  AuthMiddleware +      │                        │                        │                 │
     │                        │  RBAC check            │                        │                        │                 │
     │                        │                        │                        │                        │                 │
     │                        │  forward PATCH         │                        │                        │                 │
     │                        │───────────────────────>│                        │                        │                 │
     │                        │                        │                        │                        │                 │
     │                        │                        │  fetch order           │                        │                 │
     │                        │                        │  validate status       │                        │                 │
     │                        │                        │  is CANCELLABLE        │                        │                 │
     │                        │                        │                        │                        │                 │
     │                        │                        │  UPDATE order          │                        │                 │
     │                        │                        │  status=CANCELLED      │                        │                 │
     │                        │                        │                        │                        │                 │
     │                        │                        │  publish               │                        │                 │
     │                        │                        │  "order.cancelled"     │                        │                 │
     │                        │                        │─────────────────────────────────────────────────>│                 │
     │                        │                        │                        │                        │                 │
     │                        │                        │  if was CONFIRMED:     │                        │                 │
     │                        │                        │  publish               │                        │                 │
     │                        │                        │  "inventory.release.   │                        │                 │
     │                        │                        │   requested"           │                        │                 │
     │                        │                        │───────────────────────>│                        │                 │
     │                        │                        │                        │  restore stock         │                 │
     │                        │                        │                        │  invalidate cache      │                 │
     │                        │                        │                        │                        │                 │
     │                        │                        │                        │                        │  process refund  │
     │                        │                        │                        │                        │  if paid         │
     │                        │                        │                        │                        │                  │
     │                        │                        │                        │                        │  publish         │
     │                        │                        │                        │                        │  "payment.       │
     │                        │                        │                        │                        │   refunded"      │
     │                        │                        │───────────────────────────────────────────────────────────────────────>│
     │                        │                        │                        │                        │                  │
     │  HTTP 200              │                        │                        │                        │                  │
     │  { status: CANCELLED } │                        │                        │                        │                  │
     │<───────────────────────│                        │                        │                        │                  │
```

## Stripe Payment Flow

See [Checkout, Payment & CJ Fulfillment Flow](#checkout-payment--cj-fulfillment-flow). Webhooks handled by
`POST /payments/webhook` (signature-verified, idempotent per Stripe event id):

| Stripe event | Effect |
|---|---|
| `payment_intent.amount_capturable_updated` | Payment AUTHORIZED → `payment.authorized` |
| `payment_intent.succeeded` | Payment SUCCEEDED (no-op when `capture_payment` already recorded it) |
| `payment_intent.payment_failed` | Decline reason recorded; payment stays open for a retry |
| `payment_intent.canceled` | Payment CANCELLED → `payment.cancelled` |
| `charge.refund.updated` | Payment REFUNDED → `payment.refunded` |

## Inventory Release / Compensation Flow

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  ORDER-SERVICE   │     │ PRODUCT-SERVICE  │     │  API-GATEWAY     │
└────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                        │                        │
         │  "inventory.release.   │                        │
         │   requested"           │                        │
         │  { order_id, items }   │                        │
         │───────────────────────>│                        │
         │                        │                        │
         │                        │  idempotency check     │
         │                        │                        │
         │                        │  BEGIN transaction     │
         │                        │  restore quantities    │
         │                        │  COMMIT                │
         │                        │                        │
         │                        │  invalidate product    │
         │                        │  cache namespace       │
         │                        │                        │
         │                        │  mark event processed  │
         │                        │                        │
         │  (no reply needed)     │                        │
         │                        │                        │
         │                        │                        │  subsequent GET /products
         │                        │                        │  → cache miss → fresh data
         │                        │<───────────────────────│
```

## Custom Image Generation Flow

```
┌──────────┐     ┌──────────────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  CLIENT  │     │   API-GATEWAY :8000  │     │ PRODUCT-SERVICE  │     │  TASKIQ WORKER   │     │  AI PROVIDER │
└────┬─────┘     └──────────┬───────────┘     └────────┬─────────┘     └────────┬─────────┘     └──────┬───────┘
     │                        │                        │                        │                    │
     │ POST /images/generations│                       │                        │                    │
     │ { prompt, style, ... } │                        │                        │                    │
     │ (auth cookie or guest) │                        │                        │                    │
     │───────────────────────>│                        │                        │                    │
     │                        │ forward to product     │                        │                    │
     │                        │───────────────────────>│                        │                    │
     │                        │                        │                        │                    │
     │                        │                        │  resolve user/guest    │                    │
     │                        │                        │  check generation quota│                    │
     │                        │                        │  create job record     │                    │
     │                        │                        │  status=PENDING        │                    │
     │                        │                        │                        │                    │
     │                        │                        │  enqueue TaskiQ job    │                    │
     │                        │                        │───────────────────────>│                    │
     │                        │                        │                        │                    │
     │                        │  HTTP 202 Accepted     │                        │                    │
     │                        │  { job_id, status:     │                        │                    │
     │                        │    pending, remaining }│                        │                    │
     │                        │<───────────────────────│                        │                    │
     │  HTTP 202              │                        │                        │                    │
     │  Location: /.../status │                        │                        │                    │
     │<───────────────────────│                        │                        │                    │
     │                        │                        │                        │                    │
     │  GET /images/generations│                       │                        │                    │
     │  /{job_id}/status      │                        │                        │                    │
     │───────────────────────>│                        │                        │                    │
     │                        │ forward to product     │                        │                    │
     │                        │───────────────────────>│                        │                    │
     │                        │                        │  read job from Redis/DB│                    │
     │                        │  HTTP 200 { status }   │                        │                    │
     │                        │<───────────────────────│                        │                    │
     │  HTTP 200              │                        │                        │                    │
     │<───────────────────────│                        │                        │                    │
     │                        │                        │                        │                    │
     │                        │                        │                        │  generate image    │
     │                        │                        │                        │  (async)           │
     │                        │                        │                        │───────────────────>│
     │                        │                        │                        │                    │
     │                        │                        │                        │  image URL         │
     │                        │                        │                        │<───────────────────│
     │                        │                        │                        │                    │
     │                        │                        │                        │  update job        │
     │                        │                        │                        │  status=COMPLETED  │
```

## Product Creation with Image Upload Flow

```
┌──────────┐     ┌──────────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  CLIENT  │     │   API-GATEWAY :8000  │     │ PRODUCT-SERVICE  │     │  POSTGRES    │
└────┬─────┘     └──────────┬───────────┘     └────────┬─────────┘     └──────┬───────┘
     │                        │                        │                    │
     │ JSON endpoint:         │                        │                    │
     │ POST /products         │                        │                    │
     │ { name, price, qty...} │                        │                    │
     │ (admin only)           │                        │                    │
     │───────────────────────>│                        │                    │
     │                        │ forward JSON           │                    │
     │                        │───────────────────────>│                    │
     │                        │                        │                    │
     │                        │                        │  INSERT product    │
     │                        │                        │  INSERT images     │
     │                        │                        │  (if URLs provided)│
     │                        │                        │                    │
     │                        │  HTTP 201 product      │                    │
     │                        │<───────────────────────│                    │
     │  HTTP 201              │                        │                    │
     │<───────────────────────│                        │                    │
     │                        │                        │                    │
     │ FormData endpoint:     │                        │                    │
     │ POST /products/upload  │                        │                    │
     │ multipart/form-data    │                        │                    │
     │ + image files          │                        │                    │
     │ (admin only)           │                        │                    │
     │───────────────────────>│                        │                    │
     │                        │ forward FormData       │                    │
     │                        │───────────────────────>│                    │
     │                        │                        │                    │
     │                        │                        │  save uploaded     │
     │                        │                        │  files to volume   │
     │                        │                        │  INSERT product +  │
     │                        │                        │  product_image rows│
     │                        │                        │                    │
     │                        │  HTTP 201 product      │                    │
     │                        │<───────────────────────│                    │
     │  HTTP 201              │                        │                    │
     │<───────────────────────│                        │                    │
```

## Review CRUD Flow

```
┌──────────┐     ┌──────────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  CLIENT  │     │   API-GATEWAY :8000  │     │ PRODUCT-SERVICE  │     │  POSTGRES    │
└────┬─────┘     └──────────┬───────────┘     └────────┬─────────┘     └──────┬───────┘
     │                        │                        │                    │
     │ POST /products/{pid}/  │                        │                    │
     │   users/{uid}/reviews  │                        │                    │
     │ { rating, comment }    │                        │                    │
     │ (auth required)        │                        │                    │
     │───────────────────────>│                        │                    │
     │                        │  AuthMiddleware:       │                    │
     │                        │  require_user_or_admin │                    │
     │                        │                        │                    │
     │                        │  forward to product    │                    │
     │                        │───────────────────────>│                    │
     │                        │                        │                    │
     │                        │                        │  validate user     │
     │                        │                        │  owns review       │
     │                        │                        │  INSERT review     │
     │                        │                        │                    │
     │                        │  HTTP 201 review       │                    │
     │                        │<───────────────────────│                    │
     │  HTTP 201              │                        │                    │
     │<───────────────────────│                        │                    │
     │                        │                        │                    │
     │ GET /products/{pid}/   │                        │                    │
     │   reviews              │                        │                    │
     │ (public)               │                        │                    │
     │───────────────────────>│                        │                    │
     │                        │  no auth required      │                    │
     │                        │  forward               │                    │
     │                        │───────────────────────>│                    │
     │                        │                        │  fetch reviews     │
     │                        │                        │  (cached in Redis) │
     │                        │  HTTP 200 reviews      │                    │
     │                        │<───────────────────────│                    │
     │  HTTP 200              │                        │                    │
     │<───────────────────────│                        │                    │
```

## Notification Consumer Flow

```
┌─────────────┐     ┌─────────────────────────┐     ┌────────────────────┐     ┌─────────────┐     ┌─────────────┐
│   RABBITMQ  │     │ NOTIFICATION-CONSUMER   │     │  IDEMPOTENCY SVC   │     │   TASKIQ    │     │  MAILSERVER │
└──────┬──────┘     └───────────┬─────────────┘     └──────────┬─────────┘     └──────┬──────┘     └──────┬──────┘
       │                        │                            │                        │                   │
       │  user.registered       │                            │                    │                 │
       │  order.confirmed        │                            │                        │                    │
       │  payment.failed etc.   │                            │                        │                 │
       │───────────────────────>│                            │                        │                 │
       │                        │                            │                        │                 │
       │                        │  try_claim_event(event_id, event_type)              |                 │
       │                        │───────────────────────────>│                        │                 │
       │                        │                            │                        │                 │
       │                        │  already processed?        │                        │                 │
       │                        │  YES → skip                │                    │                 │
       │                        │  NO  → proceed             │                    │                 │
       │                        │                            │                    │                 │
       │                        │  match event type:         │                    │                 │
       │                        │  - user.registered         │                    │                 │
       │                        │    → enqueue verification   │                    │                 │
       │                        │      email task            │                    │                 │
       │                        │───────────────────────────────────────────────> │                    │
       │                        │  - order.confirmed          │                    │                 │
       │                        │    → enqueue confirmation   │                    │                 │
       │                        │      email task            │                    │                 │
       │                        │───────────────────────────────────────────────> │                    │
       │                        │                            │                    │                 │
       │                        │  save in-app notification   │                    │                 │
       │                        │  (notification DB)          │                    │                 │
       │                        │                            │                    │                 │
       │                        │  mark_event_as_processed() │                    │                 │
       │                        │───────────────────────────>│                    │                 │
       │                        │                            │                    │                 │
       │                        │                            │                    │  worker sends email│
       │                        │                            │                    │─────────────────>│
```

## In-App Notification Flow

```
┌──────────┐     ┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────┐
│  CLIENT  │     │   API-GATEWAY :8000  │     │ NOTIFICATION-SERVICE │     │  POSTGRES    │
└────┬─────┘     └──────────┬───────────┘     └──────────┬───────────┘     └──────┬───────┘
     │                        │                            │                    │
     │ GET /notifications/    │                            │                    │
     │   users/{user_id}      │                            │                    │
     │ (auth: self or admin)  │                            │                    │
     │───────────────────────>│                            │                    │
     │                        │  AuthMiddleware + RBAC     │                    │
     │                        │  forward                   │                    │
     │                        │───────────────────────────>│                    │
     │                        │                            │  query with filters│
     │                        │                            │  limit/offset      │
     │                        │  HTTP 200 notifications    │                    │
     │                        │<───────────────────────────│                    │
     │  HTTP 200              │                            │                    │
     │<───────────────────────│                            │                    │
     │                        │                            │                    │
     │ PATCH /notifications/  │                            │                    │
     │   {id}/read            │                            │                    │
     │───────────────────────>│                            │                    │
     │                        │  forward                   │                    │
     │                        │───────────────────────────>│                    │
     │                        │                            │  UPDATE is_read    │
     │                        │  HTTP 200 notification     │                    │
     │                        │<───────────────────────────│                    │
     │  HTTP 200              │                            │                    │
     │<───────────────────────│                            │                    │
```

## AdminJS Integration Flow

```
┌──────────────┐     ┌─────────────┐     ┌──────────────────────┐     ┌────────────────────┐
│  ADMIN USER  │     │   TRAEFIK   │     │   ADMIN-JS-SERVICE   │     │  BACKEND SERVICES  │
└──────┬───────┘     └──────┬──────┘     └───────────┬──────────┘     └──────────┬─────────┘
       │                    │                        │                           │
       │  admin.domain.com  │                        │                           │
       │  (private IP only) │                        │                           │
       │───────────────────>│                        │                           │
       │                    │  admin-ip-allowlist    │                           │
       │                    │  middleware            │                           │
       │                    │                        │                           │
       │                    │  proxy to :3000        │                           │
       │                    │───────────────────────>│                           │
       │                    │                        │                           │
       │                    │                        │  load schema             │
       │                    │                        │  GET /admin/schema/users │
       │                    │                        │  GET /admin/schema/...   │
       │                    │                        │──────────────────────────>│
       │                    │                        │                           │
       │                    │                        │  return model fields     │
       │                    │                        │<──────────────────────────│
       │                    │                        │                           │
       │  React Admin UI     │                        │                           │
       │  rendered            │                        │                           │
       │<─────────────────────│                        │                           │
       │                    │                        │                           │
       │  CRUD operations     │                        │                           │
       │  via AdminJS         │                        │                           │
       │─────────────────────>│                        │                           │
       │                    │                        │  forward to API-Gateway  │
       │                    │                        │  or call DB directly     │
       │                    │                        │  (TypeORM)               │
       │                    │                        │──────────────────────────>│
```


## Supplier Service Flow

### Manual supplier sync (admin triggered)

```
┌──────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│  ADMIN USER  │     │   API-GATEWAY :8000  │     │  SUPPLIER-SERVICE   │
│              │     │                      │     │      :8010          │
└──────┬───────┘     └──────────┬───────────┘     └──────────┬──────────┘
       │                        │                            │
       │ POST /cjdropshipping/  │                            │
       │   sync (admin only)    │                            │
       │───────────────────────>│                            │
       │                        │ forward to supplier-service│
       │                        │───────────────────────────>│
       │                        │                            │
       │                        │        ┌───────────────────┴───────────────────┐
       │                        │        │ 1. SupplierSyncOrchestrator.run_sync() │
       │                        │        │ 2. load SupplierConfig                 │
       │                        │        │ 3. create SupplierSyncState (running)  │
       │                        │        │ 4. CJDropshippingProductProvider       │
       │                        │        │    → CJ API: search + details          │
       │                        │        │ 5. CJToSupplierMapper                  │
       │                        │        │    → GenericSupplierProduct[]          │
       │                        │        │ 6. OutboxEventService                  │
       │                        │        │    → persist SupplierProductsFetched   │
       │                        │        │ 7. update sync state (completed)       │
       │                        │        └───────────────────┬───────────────────┘
       │                        │                            │
       │                        │  HTTP 202 Accepted         │
       │                        │  { supplier_id, fetch_id,  │
       │                        │    products_fetched, ... } │
       │                        │<───────────────────────────│
       │  HTTP 202              │                            │
       │<───────────────────────│                            │
```

### Scheduled supplier sync (TaskIQ)

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  TASKIQ SCHEDULER   │     │   TASKIQ BROKER     │     │   TASKIQ WORKER     │
│  (supplier_service) │     │  (RabbitMQ backend) │     │  (supplier_service) │
└──────────┬──────────┘     └──────────┬──────────┘     └──────────┬──────────┘
           │                           │                            │
           │ cron: every 10 min        │                            │
           │ scheduled_supplier_sync() │                            │
           │──────────────────────────>│                            │
           │                           │ enqueue task               │
           │                           │───────────────────────────>│
           │                           │                            │
           │                           │                            │ loop active configs
           │                           │                            │ call run_sync() for each
           │                           │                            │ (same flow as manual sync)
```

### Direct CJ Dropshipping product search

```
┌──────────────┐     ┌──────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│    CLIENT    │     │   API-GATEWAY :8000  │     │  SUPPLIER-SERVICE   │     │  CJ DROPSHIPPING    │
│              │     │                      │     │      :8010          │     │       API           │
└──────┬───────┘     └──────────┬───────────┘     └──────────┬──────────┘     └──────────┬──────────┘
       │                        │                            │                         │
       │ GET /cjdropshipping/   │                            │                         │
       │   products?keyword=... │                            │                         │
       │───────────────────────>│                            │                         │
       │                        │ forward                    │                         │
       │                        │───────────────────────────>│                         │
       │                        │                            │  ensure access token    │
       │                        │                            │  GET /product/listV2    │
       │                        │                            │─────────────────────────>│
       │                        │                            │  product list JSON      │
       │                        │                            │<─────────────────────────│
       │                        │                            │  CJToSupplierMapper     │
       │                        │                            │  → list[CJProductPreview]│
       │                        │  HTTP 200 products         │                         │
       │                        │<───────────────────────────│                         │
       │  HTTP 200              │                            │                         │
       │<───────────────────────│                            │                         │
```

### Outbox publishing (background)

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  OUTBOX POLLER      │     │       POSTGRES      │     │      RABBITMQ       │
│  (supplier_service) │     │    outbox_events    │     │  supplier.exchange  │
└──────────┬──────────┘     └──────────┬──────────┘     └──────────┬──────────┘
           │                           │                            │
           │  SELECT unprocessed       │                            │
           │  processed = false        │                            │
           │──────────────────────────>│                            │
           │                           │                            │
           │  list of events           │                            │
           │<──────────────────────────│                            │
           │                           │                            │
           │  publish supplier.        │                            │
           │  products.fetched         │                            │
           │───────────────────────────────────────────────────────>│
           │                           │                            │
           │  UPDATE processed = true  │                            │
           │──────────────────────────>│                            │
```

### Downstream import + feedback loop

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│      RABBITMQ       │     │   PRODUCT-SERVICE   │     │      RABBITMQ       │
│  supplier.exchange  │     │       :8002         │     │  supplier.exchange  │
└──────────┬──────────┘     └──────────┬──────────┘     └──────────┬──────────┘
           │                           │                            │
           │ supplier.products.fetched │                            │
           │──────────────────────────>│                            │
           │                           │  SupplierProductMapper     │
           │                           │  bulk_upsert_products()    │
           │                           │  invalidate product cache  │
           │                           │                            │
           │                           │ supplier.product.import.   │
           │                           │ succeeded / failed         │
           │                           │───────────────────────────>│
           │                           │                            │
           │                           │                            │─────┐
           │                           │                            │     └───────────────► SUPPLIER-CONSUMER
           │                           │                            │                         (log feedback)
```

### Supplier Service key events

| Event                               | Publisher              | Consumers                 | Purpose                                   |
|-------------------------------------|------------------------|---------------------------|-------------------------------------------|
| `supplier.products.fetched`         | Supplier Service       | Product Service           | Emit fetched supplier products for import |
| `supplier.product.import.succeeded` | Product Service        | Supplier Service Consumer | Acknowledge successful product import     |
| `supplier.product.import.failed`    | Product Service        | Supplier Service Consumer | Report failed product import              |
