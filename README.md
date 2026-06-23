## Getting Started

## Flows & Diagrams

Detailed flow diagrams (User Registration, Login, Token Refresh, Logout, Password Reset, Google OAuth, Order Creation, Order Cancellation, Stripe Payment, Inventory Release, Image Generation, Product Creation, Reviews, Notifications, Middleware Execution Order, and RabbitMQ Queue Topology) are documented in [FLOWS.md](FLOWS.md).


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

Rebuild the specific container
`docker compose up -d --build <container>`


## Recreating the database
1. stop and remove containers and named volumes defined by the compose file
docker compose down -v

2. then build & start (detached)
docker compose up -d --build


## Stripe

1. Triggering events in Stripe CLI:
  stripe trigger payment_intent.succeeded
  stripe trigger payment_intent.payment_failed
1. Webhook endpoint in API Gateway:


## Pytest

### Local development (fast feedback)

```bash
# Unit tests only — no Docker/DB required
cd backend/<service_name>

# run tests
uv run pytest tests/ -v -k "not integration"
```

### Full test suite in Docker (unit + integration)

```bash
cd backend

# First run / after dependency or Dockerfile changes
./run_tests.sh --build

# Subsequent runs (reuses images)
./run_tests.sh
```

### One service only

```bash
cd backend
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm --build user-service-test
```

### Filter by test type inside a container

```bash
cd backend

# Integration only
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm user-service-test \
  python -m pytest tests/ -v -k integration

# Unit only
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm user-service-test \
  python -m pytest tests/ -v -k "not integration"
```

> **Note:** Integration tests require the Docker infrastructure (`db`, `redis`, `rabbitmq`) and use the real PostgreSQL test database defined in `.env`.


## k6 - load testing
1. max_throughput test - `k6 run max_throughput_tests.js`
2. stress test- `k6 run stress_tests.js`


--- 2 CPU + 8 GIG RAM ---
1. max_throughput -> user-service (1 worker & no chaching) -> = 443 rps
2. max_throughput -> user-service (2 workers & no chaching)-> second test with  = 810 rps
3. stress -> api-gateway  (5 workers , no caching, 50 products) -> product-service (5 workers, no caching) ->  = 436 rps
4. stress -> api-gateway  (5 workers , caching, 50 products) -> product-service (5 workers, no caching) ->  = 759 rps
5. max_throughput -> api-gateway  (5 workers , caching, 50 products) = 759 rps
6. stress -> api-gateway (1 worker, caching, 50 products) = 584 rps / 100% / 668ms max / 272ms average 

App Stage                         | Typical RPS  | Your 2CPU result |
|---------------------------------|--------------|---|
| Early startup (0–1k users/day)  | 1–5 RPS      | ✅ Way more than enough |
| Growing product (10k users/day) | 10–50 RPS    | ✅ Comfortable |
| Mid-scale (100k users/day)      | 50–200 RPS   | ✅ Handles it |
| High traffic (1M users/day)     | 500–2000 RPS | ⚠️ Hitting the ceiling




## TRAEFIK

http://localhost:8090/dashboard

Key Features
- Dynamic Service Discovery: Instantly recognizes newly deployed containers and routes traffic automatically, eliminating the need to manually update configuration files.
 - Automated SSL/TLS: Integrates seamlessly with Let's Encrypt to automatically generate and renew SSL certificates.
 - Extensive Ecosystem: Offers built-in middleware for rate limiting, basic authentication, header modification, and request redirection.
 - Observability: Supports distributed tracing (OpenTelemetry) and provides metrics directly to Prometheus, Datadog, or InfluxDB. 

 How Traefik works — conceptually
 
 Traefik is a **reverse proxy + edge router**. Its job: receive all incoming HTTP/HTTPS traffic on one or a few ports, and decide which backend service should handle each request.
 
 The key mental model is a 3-layer pipeline:
 
 ```
 Internet / Browser
        │
        ▼
   EntryPoint        ← "which port did the request arrive on?"
        │
        ▼
     Router           ← "which rule matches this request?" (Host, Path, etc.)
        │
        ▼
   Middleware(s)      ← transform the request (rate limit, headers, redirect…)
        │
        ▼
    Service           ← "which backend container(s) handle this?"
        │
        ▼
   Your container

```

In local dev (`TRAEFIK_ENTRYPOINT=web`) all routers bind to port 80. In production must switch to `websecure` and Traefik auto-requests TLS certs from Let's Encrypt.

Traefik watches Docker via the **socket-proxy** (not directly — that's the fix we made for OrbStack). When a container starts, Traefik reads its labels:

```
docker compose up api-gateway
         │
         ▼
  Traefik sees container via socket-proxy
         │
         ▼
  Reads labels:
    traefik.enable=true
    traefik.http.routers.api-gateway.rule=Host(`yourdomain.com`)
    traefik.http.services.api-gateway.loadbalancer.server.port=8000
         │
         ▼
  Dynamically creates: Router + Service
  No restart needed
```

`exposedByDefault: false` in `traefik.yml` means **only containers with `traefik.enable=true`** are routed. Everything else is invisible to Traefik.

---

### Your 4 routers

| Router | Rule | Backend | Middlewares |
|---|---|---|---|
| `api-gateway` | `yourdomain.com` or `www.yourdomain.com` | `api-gateway:8000` | rate-limit, compress, www→apex redirect |
| `admin-js` | `admin.yourdomain.com` | `admin-js-service:3000` | IP allowlist (private only) |
| `grafana` | `grafana.yourdomain.com` | `grafana:3000` | IP allowlist |
| `traefik-dashboard` | `traefik.yourdomain.com` | `api@internal` | IP allowlist |

---

### Load balancing

Right now each service runs **1 container**, so load balancing is trivial (1 backend). But if you scale:

```bash
docker compose up -d --scale api-gateway=3
```

Traefik **automatically** detects all 3 containers and round-robins between them — no config changes. The health check you have configured:

```yaml
loadbalancer.healthcheck.path=/health
loadbalancer.healthcheck.interval=30s
```

...means Traefik pings `/health` every 30s and **removes unhealthy containers from the pool** without taking down the others.

---

### Middleware pipeline for a typical API request

```
Browser → yourdomain.com/api/v1/products
    │
    ▼ port 80 (web entrypoint)
    │
    ▼ Router: api-gateway matches Host(`yourdomain.com`)
    │
    ▼ Middleware: rate-limit-api   (300 req/min, burst 100)
    ▼ Middleware: www-to-apex      (only fires for www. requests)
    ▼ Middleware: compress         (gzip JSON responses)
    │
    ▼ Service: api-gateway loadbalancer → container:8000
    │
    ▼ api-gateway forwards to the right microservice internally
```

The internal microservices (user-service, product-service, etc.) **don't go through Traefik at all** — they talk directly over the `usernet` Docker network. Traefik only handles the **public edge**.

---

### The socket-proxy (your OrbStack workaround)

```
Traefik → tcp://socket-proxy:2375
              │
              ▼
        nginx rewrites /v1.24/ → /v1.41/
              │
              ▼
        /var/run/docker.sock (OrbStack's socket)
```

Traefik v3 hardcodes Docker API v1.24 in its source code. OrbStack's Docker requires v1.40+. The nginx proxy transparently upgrades the version number in the URL path.

EntryPoint | Port | Purpose |
|---|---|---|
| `web` | `:80` | HTTP — redirects to HTTPS in prod; used directly in local dev |
| `websecure` | `:443` | HTTPS with Let's Encrypt (prod) |
| `metrics` | `:8082` | Prometheus scrapes Traefik's own metrics here |
| `traefik` | `:8090` | Dashboard UI (local dev only)

 Middleware              | Purpose |
 |-----------------------|----------------------------------------------------|
 | `secure-headers`      | HSTS, XSS, no-sniff, `Server:` header stripped     |
 | `compress`            | Gzip JSON/HTML responses                           |
 | `rate-limit-api`      | 3000 req/min avg, burst 100 (before api-gateway)   |
 | `admin-ip-allowlist`  | RFC-1918 only for admin tools                      |
 | `www-to-apex`         | `www.domain.com` → `domain.com` permanent redirect |
 

 
 | Service            | URL                      | Middlewares                                 |
 |--------------------|--------------------------|---------------------------------------------|
 | `api-gateway`      | `yourdomain.com`         | `www-to-apex`, `rate-limit-api`, `compress` |
 | `admin-js-service` | `admin.yourdomain.com`   | `admin-ip-allowlist`                        |
 | `grafana`          | `grafana.yourdomain.com` | `admin-ip-allowlist`                        |
 | `traefik`          | `traefik.yourdomain.com` | `admin-ip-allowlist`       (dashboard)      |


Router | Entry | Rule |
|--------|-------|------|
| `api-gateway` | `web` | `yourdomain.com` |
| `grafana` | `web` | `grafana.yourdomain.com` |
| `admin-js` | `web` | `admin.yourdomain.com` |
| `traefik-dashboard` | `web` | `traefik.yourdomain.com



## Prometheus AlertManager
Alertmanager UI is at **http://localhost:9093
Test:  curl -X POST http://localhost:9093/api/v2/alerts \
  -H "Content-Type: application/json" \
  -d '[{"labels":{"alertname":"TestAlert","severity":"warning","job":"test"},"annotations":{"description":"This is a test from Alertmanager"}}]'




## Scaling of the APP

Uvicorn workers — vertical scaling (inside one container)

```
Container (1x)
└── uvicorn --workers 4
    ├── worker process 1  (own memory, own GIL)
    ├── worker process 2
    ├── worker process 3
    └── worker process 4
```

- Multiple **OS processes** inside a **single container**
- Each worker has its own Python GIL → true CPU parallelism
- All share the same CPU/RAM limits of that one container
- If the container dies → **all 4 workers die together**
- Rule of thumb: `workers = (2 × CPU cores) + 1`

---

## `docker compose up -d --scale api-gateway=3` — horizontal scaling (multiple containers)

```
Traefik loadbalancer
├── Container 1 → uvicorn (1 worker)
├── Container 2 → uvicorn (1 worker)
└── Container 3 → uvicorn (1 worker)
```

- Multiple **independent containers** each running their own process
- Traefik distributes traffic between them (round-robin)
- If one container crashes → the other 2 keep serving traffic
- Each container can be on a different machine (in Swarm/K8s)

---

## The real difference — fault isolation

| | Uvicorn workers | Docker scale |
|---|---|---|
| A worker crashes | Other workers survive | Other **containers** survive |
| Memory leak | All workers in same container affected | Isolated per container |
| Deploy update | Restart whole container | Rolling update possible |
| State sharing | Easy (same process group) | Hard (need Redis/DB) |

---

## What you should actually do

**Combine both** — this is the production best practice:

```
Traefik
├── Container 1 → uvicorn --workers 2
├── Container 2 → uvicorn --workers 2
└── Container 3 → uvicorn --workers 2
                           = 6 real parallel workers
                           + fault isolation between containers
```

**FastAPI services specifically:**

For async workloads, **1 worker per container is often enough** because a single async worker can handle hundreds of concurrent requests without blocking. Workers only matter for CPU-bound work.

So the practical setup:
- **Local dev**: 1 container, 1 worker — simple, easy logs
- **Production**: `--scale 2-3`, 1-2 workers each — balance between resilience and resource use


## OpenTelemetry
1. Make some requests to your API (any endpoint through api-gateway)
2. Open Grafana → **Explore** → select **Tempo** datasource
3. Click **Search** → you'll see traces from all your services with full waterfall view
4. From a Loki log line you can also click **"View in Traces"** to jump directly to the trace