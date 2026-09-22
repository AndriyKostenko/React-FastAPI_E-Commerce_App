# Observability stack

Metrics, logs, traces and alerting for the backend. Everything here is
configuration for containers defined in `backend/docker-compose.yml` — there is
no application code. The Python side is one file, `shared/telemetry.py`, which
every service's `main.py` calls as `setup_tracing(app, service_name=...)`.

**This stack only runs under Docker.** `backend/local/dev.sh` deliberately skips
it and exports `OTEL_TRACES_DISABLED=true`, so a native dev run has no collector,
no Prometheus and no Grafana — see `backend/local/README.md`.

## Layout

```
observability/
├── prometheus/      prometheus.yml (scrape jobs) + rules/alerts.yml
├── alertmanager/    routing template, Telegram message template, entrypoint
├── grafana/         provisioned datasources + dashboards
├── tempo/           trace storage and the span-metrics generator
├── otelcollector/   OTLP receiver that forwards spans to Tempo
└── promtail/        Docker log scraper that ships to Loki
```

## How the pieces connect

```
services  ──/metrics──────────────▶  Prometheus ──▶ Alertmanager ──▶ Telegram
          ──OTLP :4317────────────▶  otel-collector ──▶ Tempo ──remote_write──▶ Prometheus
docker logs ──▶ Promtail ──────────▶  Loki
                                      └── all four are Grafana datasources
```

Two links are worth knowing about because they are easy to break:

- **Tempo → Prometheus.** Tempo's `metrics_generator` derives service-graph and
  span-metrics series from traces and remote-writes them to Prometheus. That
  only works because the Prometheus container runs with
  `--web.enable-remote-write-receiver` (set in `docker-compose.yml`, not here).
- **Tempo → Loki.** The Tempo datasource declares `tracesToLogsV2` pointing at
  the Loki UID, which is what puts the "View in Traces" jump on a log line and
  the logs link on a span. Renaming a datasource UID in
  `grafana/provisioning/datasources/datasource.yml` breaks both directions.

## Ports

| | host | notes |
|---|---|---|
| Grafana | 3002 | container listens on 3000 |
| Prometheus | 9090 | |
| Alertmanager | 9093 | |
| Loki | 3100 | |
| Tempo | 3200 | also receives OTLP on 4317/4318 |
| otel-collector | 4317 / 4318 | gRPC / HTTP OTLP |
| cAdvisor | 8080 | container CPU/memory, scraped by Prometheus |

## Verifying it works

**Traces.** Make any request through the API gateway, then Grafana → Explore →
Tempo → Search. You should get a waterfall spanning gateway and downstream
services. From a Loki log line, "View in Traces" jumps straight to its trace.

**Metrics.** Prometheus → Status → Targets; every job should be `UP`. Each
FastAPI service exposes `/metrics` directly, e.g. `curl localhost:8001/metrics`.

**Logs.** Grafana → Explore → Loki → `{service="user-service"}`. Promtail
promotes `level`, `service` and `request_id` out of the JSON log line into
labels, and drops `/health` and `/metrics` polls to keep storage lean.

**Alerting.** Fire a synthetic alert straight at Alertmanager:

```bash
curl -X POST http://localhost:9093/api/v2/alerts \
  -H "Content-Type: application/json" \
  -d '[{"labels":{"alertname":"TestAlert","severity":"warning","job":"test"},
       "annotations":{"description":"This is a test from Alertmanager"}}]'
```

It should reach Telegram within `group_wait` (30s).

## Alert rules

`prometheus/rules/alerts.yml`, three groups:

| group | alerts |
|---|---|
| `service_health` | `ServiceDown`, `HighErrorRate` (>5% 5xx), `HighLatency` (p95 >2s), `CriticalLatency` |
| `container_resources` | `HighContainerMemory`, `HighContainerCPU`, `ContainerRestarted` |
| `prometheus_health` | `PrometheusConfigReloadFailed`, `PrometheusStorageIssue` |

Routing lives in `alertmanager/alertmanager.yml.tmpl`: everything goes to
Telegram, `critical` re-notifies every 30m and `warning` every 4h, and an
inhibit rule suppresses a warning while a critical is firing for the same `job`.

### Why the Alertmanager config is a template

Alertmanager cannot read environment variables in its config file, so
`docker-entrypoint.sh` substitutes `${TELEGRAM_BOT_TOKEN}` and
`${TELEGRAM_CHAT_ID}` with `sed` into `/tmp/alertmanager.yml` before exec'ing the
binary — no `envsubst` needed on a busybox image. Both variables come from
`backend/.env`; with them unset the container still starts and notifications
silently fail.

## Known gap: four services are not scraped

`prometheus.yml` has jobs for api-gateway, user, product, notification, order and
payment — but **not** cart (8007), shipping (8008), wishlist (8009) or supplier
(8010), even though all four expose `/metrics`. They are invisible to dashboards
and to every `service_health` alert, `ServiceDown` included.

## Adding a new service

1. Add a `scrape_configs` job in `prometheus.yml` pointing at
   `<service-name>:<port>` with `metrics_path: /metrics`.
2. Nothing is needed for logs — Promtail discovers containers through the Docker
   socket and labels them by compose service name.
3. Nothing is needed for traces, as long as `main.py` calls `setup_tracing()` and
   the container gets `OTEL_EXPORTER_OTLP_ENDPOINT`.
