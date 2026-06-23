# Flows & Diagrams

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



Every request through the gateway passes this chain in order:

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


## RabbitMQ Queue Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            RabbitMQ Que                                      │
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



## Order Creation Flow

### Happy path (inventory available + payment succeeds)

```
┌──────────┐     ┌────────────────────────────────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  CLIENT  │     │          API-GATEWAY :8000             │     │  ORDER-SERVICE   │     │ PRODUCT-SERVICE  │     │  PAYMENT-SERVICE │
│          │     │                                        │     │     :8005        │     │     :8002        │     │     :8006        │
└────┬─────┘     └────────────────────┬───────────────────┘     └────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘
     │                                │                                  │                      │                      │
     │  POST /api/v1/orders           │                                  │                      │                      │
     │  { items[], shipping_address } │                                  │                      │                      │
     │───────────────────────────────>│                                  │                      │                      │
     │                                │  AuthMiddleware + GatewayMiddleware + rate limit         │                      │
     │                                │                                  │                      │                      │
     │                                │  httpx POST /api/v1/orders       │                      │                      │
     │                                │  { items[], user_id, user_email }│                      │                      │
     │                                │─────────────────────────────────>│                      │                      │
     │                                │                                  │                      │                      │
     │                                │                                  │  1. validate items   │                      │
     │                                │                                  │  2. calculate total  │                      │
     │                                │                                  │  3. INSERT order     │                      │
     │                                │                                  │     status=PENDING   │                      │
     │                                │                                  │                      │                      │
     │                                │                                  │  publish             │                      │
     │                                │                                  │  "inventory.reserve. │                      │
     │                                │                                  │   requested"         │                      │
     │                                │                                  │  { order_id, items,  │                      │
     │                                │                                  │    user_id, email }  │                      │
     │                                │                                  │─────────────────────>│                      │
     │                                │                                  │                      │  reserve inventory   │
     │                                │                                  │                      │  (SELECT FOR UPDATE) │
     │                                │                                  │                      │                      │
     │                                │                                  │  publish             │                      │
     │                                │                                  │  "inventory.reserve. │                      │
     │                                │                                  │   succeeded"         │                      │
     │                                │                                  │<─────────────────────│                      │
     │                                │                                  │                      │                      │
     │                                │                                  │  UPDATE order        │                      │
     │                                │                                  │  status=CONFIRMED    │                      │
     │                                │                                  │                      │                      │
     │                                │                                  │  publish             │                      │
     │                                │                                  │  "order.confirmed"   │                      │
     │                                │                                  │  { order_id, total } │                      │
     │                                │                                  │                      │                      │
     │  HTTP 201                      │                                  │                      │                      │
     │  { order_id, status: PENDING   │                                  │                      │                      │
     │    ← immediate response }      │                                  │                      │                      │
     │<───────────────────────────────│                                  │                      │                      │
     │                                │                                  │                      │                      │
     │  POST /api/v1/payments/create- │                                  │                      │                      │
     │  intent { order_id, amount }   │                                  │                      │                      │
     │───────────────────────────────>│                                  │                      │                      │
     │                                │  forward to payment-service      │                      │                      │
     │                                │─────────────────────────────────────────────────────────────────────────────────>│
     │                                │                                  │                      │                      │
     │                                │                                  │                      │                      │  Stripe PaymentIntent
     │                                │                                  │                      │                      │  client_secret returned
     │                                │                                  │                      │                      │
     │  HTTP 200 { client_secret }    │                                  │                      │                      │
     │<───────────────────────────────│<──────────────────────────────────────────────────────────────────────────────────│
     │                                │                                  │                      │                      │
     │  [Client confirms with Stripe] │                                  │                      │                      │
     │                                │                                  │                      │                      │
     │                                │  Stripe webhook POST /payments/webhook                   │                      │
     │                                │─────────────────────────────────────────────────────────────────────────────────>│
     │                                │                                  │                      │                      │
     │                                │                                  │                      │                      │  verify signature
     │                                │                                  │                      │                      │  update payment=succeeded
     │                                │                                  │                      │                      │  publish "payment.succeeded"
     │                                │                                  │                      │                      │
     │                                │                                  │<──────────────────────────────────────────────────│
     │                                │                                  │  confirm order again │                      │
     │                                │                                  │  (idempotent)        │                      │
     │                                │                                  │                      │                      │
     │                                │                                  │  publish             │                      │
     │                                │                                  │  "order.confirmed"   │                      │
     │                                │                                  │─────┐                │                      │
     │                                │                                  │     │                │                      │
     │                                │                                  │     └───────────────►│  RABBITMQ            │
     │                                │                                  │                      │  order.events.exchange│
     │                                │                                  │                      │  payment.events      │
     │                                │                                  │                      │                      │
     │                                │                                  │                      │─────┐                │
     │                                │                                  │                      │     │                │
     │                                │                                  │                      │     └───────────────►│  NOTIFICATION-CONSUMER
     │                                │                                  │                      │                      │  send_order_confirmed
     │                                │                                  │                      │                      │  _email(event)
     │                                │                                  │                      │                      │
     │                                │                                  │                      │                      │──────────────────────> MAILSERVER
     │                                │                                  │                      │                      │  📧 "Order Confirmed"│
```

### Failure path (out of stock)

```
┌──────────┐     ┌────────────────────────────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  CLIENT  │     │          API-GATEWAY :8000             │     │  ORDER-SERVICE   │     │ PRODUCT-SERVICE  │
└────┬─────┘     └────────────────────┬───────────────────┘     └────────┬─────────┘     └────────┬─────────┘
     │  POST /api/v1/orders           │                                  │                      │
     │───────────────────────────────>│                                  │                      │
     │                                │  forward to order-service        │                      │
     │                                │─────────────────────────────────>│                      │
     │                                │                                  │  INSERT order        │
     │                                │                                  │  status=PENDING      │
     │                                │                                  │                      │
     │                                │                                  │  publish             │
     │                                │                                  │  "inventory.reserve. │
     │                                │                                  │   requested"         │
     │                                │                                  │─────────────────────>│
     │                                │                                  │                      │
     │                                │                                  │                      │  cannot reserve      │
     │                                │                                  │                      │  (out of stock)      │
     │                                │                                  │                      │
     │                                │                                  │  publish             │
     │                                │                                  │  "inventory.reserve. │
     │                                │                                  │   failed"            │
     │                                │                                  │<─────────────────────│
     │                                │                                  │                      │
     │                                │                                  │  UPDATE order        │
     │                                │                                  │  status=CANCELLED    │
     │                                │                                  │                      │
     │                                │                                  │  publish             │
     │                                │                                  │  "order.cancelled"   │
     │                                │                                  │                      │
     │                                │                                  │─────┐                │
     │                                │                                  │     └───────────────►│  RABBITMQ
     │                                │                                  │                      │  order.events.exchange
     │                                │                                  │                      │
     │                                │                                  │                      │─────┐
     │                                │                                  │                      │     └───────────────► NOTIFICATION-CONSUMER
     │                                │                                  │                      │                       send_order_cancelled_email
     │                                │                                  │                      │
     │  HTTP 201 { order_id,          │                                  │                      │                       ──────────────────────> MAILSERVER
     │  status: PENDING }             │                                  │                      │                       📧 "Order Cancelled"
     │<───────────────────────────────│                                  │                      │
```

### Payment failure path (inventory reserved, then payment fails)

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  ORDER-SERVICE   │     │ PRODUCT-SERVICE  │     │  PAYMENT-SERVICE │     │ NOTIFICATION-CONSUMER │
└────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                        │                        │                        │
         │  inventory.reserve.    │                        │                        │
         │  requested             │                        │                        │
         │───────────────────────>│                        │                        │
         │                        │  reserve inventory     │                        │
         │  inventory.reserve.    │                        │                        │
         │  succeeded             │                        │                        │
         │<───────────────────────│                        │                        │
         │                        │                        │                        │
         │  UPDATE order          │                        │                        │
         │  CONFIRMED             │                        │                        │
         │                        │                        │                        │
         │  [client attempts pay] │                        │                        │
         │                        │                        │  Stripe charge fails   │
         │                        │                        │                        │
         │                        │                        │  publish "payment.failed"
         │<─────────────────────────────────────────────────│                        │
         │                        │                        │                        │
         │  UPDATE order          │                        │                        │
         │  CANCELLED             │                        │                        │
         │                        │                        │                        │
         │  publish "order.cancelled"                       │                        │
         │─────────────────────────────────────────────────────────────────────────>│
         │                        │                        │                        │
         │                        │                        │  consume order.cancelled│
         │                        │                        │  refund if charged      │
         │                        │                        │  publish "payment.refunded"
         │<─────────────────────────────────────────────────│                        │
         │                        │                        │                        │
         │  publish "inventory.release.requested"           │                        │
         │───────────────────────>│                        │                        │
         │                        │  release inventory     │                        │
         │                        │                        │                        │
         │                        │  📧 cancellation email │                        │
         │                        │                        │                        │
```

### Key events

| Event | Publisher | Consumers | Purpose |
|---|---|---|---|
| `inventory.reserve.requested` | Order Service | Product Service | Ask product service to reserve stock |
| `inventory.reserve.succeeded` | Product Service | Order Service | Reservation OK → order can be confirmed |
| `inventory.reserve.failed` | Product Service | Order Service | Reservation failed → cancel order |
| `inventory.release.requested` | Order Service | Product Service | Compensation: release reserved stock |
| `order.confirmed` | Order Service | Notification, Payment | Order is confirmed |
| `order.cancelled` | Order Service | Notification, Payment | Order cancelled → refund + email |
| `payment.succeeded` | Payment Service | Order Service | Stripe confirmed charge |
| `payment.failed` | Payment Service | Order Service | Charge failed → cancel order |
| `payment.refunded` | Payment Service | Order Service | Refund processed |



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

### Create PaymentIntent
```
┌──────────┐     ┌──────────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  CLIENT  │     │   API-GATEWAY :8000  │     │ PAYMENT-SERVICE  │     │    STRIPE    │
└────┬─────┘     └──────────┬───────────┘     └────────┬─────────┘     └──────┬───────┘
     │                        │                        │                    │
     │ POST /payments/create- │                        │                    │
     │   intent               │                        │                    │
     │ { order_id, amount }   │                        │                    │
     │───────────────────────>│                        │                    │
     │                        │  AuthMiddleware +      │                    │
     │                        │  rate limit            │                    │
     │                        │                        │                    │
     │                        │  forward to payment    │                    │
     │                        │  (adds user_id, email) │                    │
     │                        │───────────────────────>│                    │
     │                        │                        │                    │
     │                        │                        │  create PaymentIntent
     │                        │                        │  with order metadata │
     │                        │                        │───────────────────>│
     │                        │                        │                    │
     │                        │                        │  client_secret,    │
     │                        │                        │  payment_intent_id │
     │                        │                        │<───────────────────│
     │                        │                        │                    │
     │                        │  HTTP 201              │                    │
     │                        │  { client_secret, ...}│                    │
     │                        │<───────────────────────│                    │
     │  HTTP 201              │                        │                    │
     │<───────────────────────│                        │                    │
```

### Webhook handling
```
┌──────────────┐     ┌──────────────────────┐     ┌──────────────────┐     ┌─────────┐     ┌─────────────┐
│    STRIPE    │     │   API-GATEWAY :8000  │     │ PAYMENT-SERVICE  │     │ORDER-SERVICE│  │NOTIFICATION │
└──────┬───────┘     └──────────┬───────────┘     └────────┬─────────┘     └────┬────┘     └──────┬──────┘
       │                        │                        │                    │                 │
       │  POST /payments/webhook│                        │                    │                 │
       │  Stripe event + sig    │                        │                    │                 │
       │───────────────────────>│                        │                    │                 │
       │                        │ forward raw body       │                    │                 │
       │                        │───────────────────────>│                    │                 │
       │                        │                        │                    │                 │
       │                        │                        │  verify signature  │                    │
       │                        │                        │  idempotency check │                    │                 │
       │                        │                        │                    │                    │
       │                        │                        │  match event type: │                    │
       │                        │                        │  - succeeded →     │                    │
       │                        │                        │    publish         │                    │
       │                        │                        │    "payment.       │                    │
       │                        │                        │     succeeded"     │                    │
       │                        │                        │───────────────────>│                    │
       │                        │                        │                    │  confirm order     │
       │                        │                        │                    │  (idempotent)      │
       │                        │                        │  - failed/canceled →                  │
       │                        │                        │    publish         │                    │
       │                        │                        │    "payment.failed"│                    │
       │                        │                        │    /"payment.      │                    │
       │                        │                        │     cancelled"     │                    │
       │                        │                        │───────────────────>│                    │
       │                        │                        │                    │  cancel order      │
       │                        │                        │                    │                    │
       │                        │                        │                    │  publish           │
       │                        │                        │                    │  "order.cancelled" │
       │                        │                        │                    │───────────────────>│
       │                        │                        │                    │                    │  send email
       │                        │  HTTP 200 ack          │                    │                    │
       │                        │<───────────────────────│                    │                    │
       │  HTTP 200 ack          │                        │                    │                    │
       │<───────────────────────│                        │                    │                    │
```

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
       │                        │                            │                    │                 │
       │  user.registered       │                            │                    │                 │
       │  order.confirmed       │                            │                    │                 │
       │  payment.failed etc.   │                            │                    │                 │
       │───────────────────────>│                            │                    │                 │
       │                        │                            │                    │                 │
       │                        │  try_claim_event(event_id, event_type)            │                 │
       │                        │───────────────────────────>│                    │                 │
       │                        │                            │                    │                 │
       │                        │  already processed?        │                    │                 │
       │                        │  YES → skip                │                    │                 │
       │                        │  NO  → proceed             │                    │                 │
       │                        │                            │                    │                 │
       │                        │  match event type:         │                    │                 │
       │                        │  - user.registered         │                    │                 │
       │                        │    → enqueue verification  │                    │                 │
       │                        │      email task            │                    │                 │
       │                        │───────────────────────────────────────────────>│                    │
       │                        │  - order.confirmed         │                    │                 │
       │                        │    → enqueue confirmation  │                    │                 │
       │                        │      email task            │                    │                 │
       │                        │───────────────────────────────────────────────>│                    │
       │                        │                            │                    │                 │
       │                        │  save in-app notification  │                    │                 │
       │                        │  (notification DB)         │                    │                 │
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
