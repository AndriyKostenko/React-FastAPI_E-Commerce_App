## Getting Started

## Alembic migrations

- Initialize Alembic (if you haven’t):
  `alembic init alembic`

- Generate a new migration file:
  `alembic revision --autogenerate -m "Your migration message"`

- Review and clean up the migration: Check the generated file — remove redundant / incorrect staff or adjust logic as needed.

- Roll back a migration (optional):
  `alembic downgrade -1 / alembic downgrade <revision_id>`

- Mark current DB as up-to-date without running migrations:
  ` alembic stamp head` (if got error about not matching your current models with existing, u can stamp specific idwith: alembic stamp <revision_id> )

- To apply alembic migrations u neeed first to go to the container, then activate venv, then aplly migrations:
  `docker compose exec user-service bash`
  `source .venv/bin/activate`

  # Review the migration file before running!

  `cat alembic/versions/<new_file>.py`

  # If it looks correct (no DROP TABLE), run:

  `alembic upgrade head`

- . Run migrations for each service (MacOS)
  `docker compose exec user-service source .venv/bin/alembic upgrade head`
  `docker compose exec product-service source .venv/bin/alembic upgrade head`
  `docker compose exec notification-service source .venv/bin/alembic upgrade head`

- . Run migrations for each service (MacOS)
  `docker compose exec user-service .venv/bin/alembic upgrade head`
  `docker compose exec product-service .venv/bin/alembic upgrade head`
  `docker compose exec notification-service .venv/bin/alembic upgrade head`

## Redis

Remember to: 1. Cache only read operations 2. Set appropriate expiration times 3. Implement cache invalidation for write operations 4. Monitor cache hit/miss rates 5. Consider cache size and memory usage

Redis docker container
`docker exec -it backend-redis-1 redis-cli` : to check and interact with redis

Auth in Redis
` AUTH your_redis_password`

Select DB of Redis
`SELECT N`

check keys in Redis
`KEYS *`

check value of the key
` GET <KEY>`

Check if Redis is running
`sudo systemctl status redis`

If not running, start it
`sudo systemctl start redis`

`sudo systemctl stop redis`

Make sure Redis is enabled on startup
`sudo systemctl enable redis`

Find process using port 6379
`sudo lsof -i :6379`

Stop the process (if it's another Redis instance)
`sudo systemctl stop redis-server`

## UV

- uv init
- uv venv
- source .venv/bin/activate
- uv add <package_name>
- uv lock
- uv pip list

## FastStream (RabbitMQ)

RabbitMQ url
`http://localhost:15672`

FastStream allows you to scale application right from the command line by running you application in the Process pool.
`faststream run serve:app --workers 2`

Generating of ApiDocs

1.  `docker compose ps` - checking all running services
2.  `docker compose exec notification-consumer sh` - entering the container
3.  `faststream docs serve main:app --host 0.0.0.0 --port 8004` - generatig the
4.  `http://0.0.0.0:8004/docs/asyncapi` - opening generated docs

Once confirmed, open your browser and go to:
http://localhost:15672
You'll see the RabbitMQ Management interface where you can:

View Exchanges (where messages are published)
View Queues (where messages are stored)
View Connections (active connections)
Monitor Message rates
Debug Message flow

Order Creation Flow (Success):
1. User creates order → Order Service
2. Order Service saves order with status=PENDING
3. Order Service publishes: OrderCreatedEvent + InventoryReserveRequested
4. Product Service receives InventoryReserveRequested
5. Product Service reserves inventory
6. Product Service publishes: InventoryReserveSucceeded
7. Order Consumer (this file) receives InventoryReserveSucceeded
8. Order Consumer updates order status=CONFIRMED
9. Order Consumer publishes: OrderConfirmedEvent
10. Notification Service sends confirmation email

Order Creation Flow (Failure):
1-4. Same as above
5. Product Service cannot reserve (out of stock)
6. Product Service publishes: InventoryReserveFailed


## PG Admin

- http://localhost:5050

## Typical target latency budgets (containerized microservices, single region, moderate load):

P50, P95, P99 are latency percentiles.

P50 (50th percentile): Median. 50% of requests are faster than this value, 50% slower.
P95 (95th percentile): 95% of requests complete at or below this time; 5% are slower.
P99 (99th percentile): Tail latency. Only 1% of requests are slower. Shows rare slow cases.

Login (/login):

P50: 80–150 ms
P95: <300 ms
P99: <500 ms Dominant cost: password hash verify (bcrypt 12 cost ~80–200 ms). Acceptable: your 200 ms is fine.
Register (/register):

P50: 120–250 ms (DB insert + token generation)
P95: <600 ms
P99: <900 ms Send email asynchronously (queue) so request isn’t blocked by SMTP/API (email call alone can be 150–400 ms).
Password reset request (/password-reset/request):

P50: 100–180 ms (create token + persist)
P95: <350–400 ms Offload email same as register.
Password reset confirm (/password-reset/confirm):

P50: 90–170 ms (verify token + hash new password + update)
P95: <350 ms
P99: <550 ms
Access token refresh (/refresh):

P50: 40–90 ms
P95: <180 ms
Simple authenticated GET (user profile):

P50: 30–70 ms
P95: <150 ms
List endpoints (small result sets):

P50: 40–90 ms
P95: <180 ms
Write operations (standard DB insert/update):

P50: 50–120 ms
P95: <250 ms
SLO suggestions:

Global: 99% of auth-related requests <500 ms
P95 login/register <300–400 ms
Error rate <0.1%
If you need tighter login times:

Reduce bcrypt rounds (only if policy allows) or switch to Argon2id tuned for ~100 ms
Warm containers (avoid CPU throttling)
Trim excessive synchronous logging
Reuse DB sessions and HTTP clients

## AdminJS

---

## Docker

building the image
`docker build -t user-service .`

running with .env file
`docker run --env-file .env user-service`

` docker compose up --build`

`docker compose restart <service-name>`

Stop containers and remove volumes
`docker compose down -v`

Remove the DB volume (WARNING: deletes all Postgres data!)
`docker volume rm backend_postgres_data`

Remove all existing containers, networks, and volumes
`docker system prune -af --volumes`

Quick one-liner to remove only <none> images:
` docker rmi $(docker images -f "dangling=true" -q)`

rebuild via docker compose
`docker compose build <service-name> --no-cache`

restart via docker compose sepc. service
`docker compose up <service-name>`

Stop the service:
`docker compose stop user-service`

Rebuild with updated code:
`docker compose build user-service`

Start it again (detached):
`docker compose up -d user-service`

## Recreating the database
1. stop and remove containers and named volumes defined by the compose file
docker compose down -v

2. then build & start (detached)
docker compose up -d --build




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
