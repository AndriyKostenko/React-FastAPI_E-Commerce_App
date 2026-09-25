#!/usr/bin/env bash
#
# Run the whole stack natively -- no Docker, no observability stack.
#
# Postgres, Redis and RabbitMQ run as ordinary Homebrew-installed processes
# with their data under backend/local/data, so this setup never touches the
# compose volumes and can be thrown away with `dev.sh reset`.  Every Python
# process runs straight out of the venv its service already has, and the
# Next.js frontend runs out of ../frontend via `npm run dev`.
#
# Usage:
#   ./local/dev.sh install          # brew-install the three infra pieces
#   ./local/dev.sh init             # one-time: initdb, create DBs + rabbit user
#   ./local/dev.sh up               # infra + migrations + services + frontend
#   ./local/dev.sh up frontend      # bring up a single process by name
#   ./local/dev.sh down             # stop everything
#   ./local/dev.sh status           # what is running, and on which port
#   ./local/dev.sh logs <name>      # tail -f one process log
#   ./local/dev.sh restart <name>   # restart one process
#   ./local/dev.sh migrate          # alembic upgrade head, every service
#   ./local/dev.sh reset            # down + delete local data (destructive)
#   ./local/dev.sh dlq list         # dead-letter queues and how many they hold
#   ./local/dev.sh dlq replay <q>   # send parked messages back to their queue
#                  [--to <queue>]   #   target for taskiq's parked tasks
#                  [--limit N]      #   replay at most N
#
# RELOAD=1           ./local/dev.sh up   HTTP services start with --reload.
# FRONTEND_PORT=3000 ./local/dev.sh up   override the Next.js port.
# CJ_MCP_PORT=3009   ./local/dev.sh up   override the CJ MCP server port.

set -euo pipefail

LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$LOCAL_DIR/.." && pwd)"
RUN_DIR="$LOCAL_DIR/run"
LOG_DIR="$LOCAL_DIR/logs"
DATA_DIR="$LOCAL_DIR/data"
PGDATA="$DATA_DIR/postgres"

BREW_PREFIX="$(brew --prefix 2>/dev/null || echo /opt/homebrew)"
PG_BIN="$BREW_PREFIX/opt/postgresql@16/bin"
RABBIT_BIN="$BREW_PREFIX/opt/rabbitmq/sbin"
export PATH="$PG_BIN:$RABBIT_BIN:$PATH"

# Homebrew's rabbitmq reads its node/port config from here; without it the
# server starts with compiled-in defaults and ignores the brew install.
[ -f "$BREW_PREFIX/etc/rabbitmq/rabbitmq-env.conf" ] && \
  export CONF_ENV_FILE="$BREW_PREFIX/etc/rabbitmq/rabbitmq-env.conf"

mkdir -p "$RUN_DIR" "$LOG_DIR" "$DATA_DIR/media/generated" "$DATA_DIR/media/images" "$DATA_DIR/media/icons"

# --------------------------------------------------------------------------
# .env readers
#
# backend/.env holds list values like ALLOWED_HOSTS=["localhost", ...] that
# bash cannot source, so single keys are pulled out by hand instead.
# --------------------------------------------------------------------------
env_get() {
  local key="$1" value=""
  for file in "$BACKEND_DIR/.env" "$BACKEND_DIR/.env.local"; do
    [ -f "$file" ] || continue
    local found
    found="$(sed -n -E "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*(.*)\$/\1/p" "$file" | tail -n 1)"
    [ -n "$found" ] && value="$found"
  done
  # strip surrounding quotes and any trailing comment-free whitespace
  value="${value%"${value##*[![:space:]]}"}"
  value="${value%\"}"; value="${value#\"}"
  value="${value%\'}"; value="${value#\'}"
  printf '%s' "$value"
}

POSTGRES_USER="$(env_get POSTGRES_USER)"
POSTGRES_PASSWORD="$(env_get POSTGRES_PASSWORD)"
POSTGRES_PORT="$(env_get POSTGRES_PORT)"
REDIS_PASSWORD="$(env_get REDIS_PASSWORD)"
REDIS_PORT="$(env_get REDIS_PORT)"
RABBITMQ_USER="$(env_get RABBITMQ_USER)"
RABBITMQ_PASSWORD="$(env_get RABBITMQ_PASSWORD)"
RABBITMQ_PORT="$(env_get RABBITMQ_PORT)"
: "${POSTGRES_PORT:=5432}" "${REDIS_PORT:=6379}" "${RABBITMQ_PORT:=5672}"

# frontend/.env pins NEXT_PUBLIC_APP_URL to :30000 and backend CORS_ALLOWED_ORIGINS
# lists that same port, so serving on anything else needs both updated too.
FRONTEND_PORT="${FRONTEND_PORT:-30000}"

# The CJ Dropshipping MCP server lives outside this repo (a sibling checkout of
# api-mcp).  It is run in HTTP transport mode because that is the only one that
# accepts CJ's direct-token URL, /mcp/MCP@<userId>@CJ:<accessToken> -- the stdio
# transport has no way to carry the token.  CJ_ENV is left unset: the server
# defaults to production, which is the environment the account tokens belong to.
CJ_MCP_PORT="${CJ_MCP_PORT:-3009}"
CJ_MCP_DIR="${CJ_MCP_DIR:-../../api-mcp}"

# --------------------------------------------------------------------------
# The process table: name | service dir | command (relative to that dir)
#
# Mirrors docker-compose.yml minus the observability stack, traefik, pgadmin
# and admin-js.  gunicorn is replaced by plain uvicorn: one process is enough
# locally, and it keeps PROMETHEUS_MULTIPROC_DIR out of the picture.
#
# The frontend is the one non-Python row: its dir is relative to backend/ like
# every other, and it is appended after the heredoc because the quoted heredoc
# cannot interpolate $FRONTEND_PORT.
# --------------------------------------------------------------------------
processes() {
  cat <<'EOF'
api-gateway|api_gateway|.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
user-service|user_service|.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001
product-service|product_service|.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8002
notification-service|notification_service|.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8003
order-service|order_service|.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8005
payment-service|payment_service|.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8006
cart-service|cart_service|.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8007
shipping-service|shipping_service|.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8008
wishlist-service|wishlist_service|.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8009
supplier-service|supplier_service|.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8010
user-outbox-worker|user_service|.venv/bin/python outbox_worker.py
product-outbox-worker|product_service|.venv/bin/python outbox_worker.py
supplier-outbox-worker|supplier_service|.venv/bin/python outbox_worker.py
order-outbox-worker|order_service|.venv/bin/python outbox_worker.py
payment-outbox-worker|payment_service|.venv/bin/python outbox_worker.py
shipping-outbox-worker|shipping_service|.venv/bin/python outbox_worker.py
order-saga-timeout-worker|order_service|.venv/bin/python saga_timeout_worker.py
product-consumer|product_service|.venv/bin/faststream run event_consumer.app:app
supplier-consumer|supplier_service|.venv/bin/faststream run event_consumer.app:app
notification-consumer|notification_service|.venv/bin/faststream run events_consumer.app:app
order-consumer|order_service|.venv/bin/faststream run events_consumer.app:app
payment-consumer|payment_service|.venv/bin/faststream run events_consumer.app:app
cart-consumer|cart_service|.venv/bin/faststream run events_consumer.app:app
wishlist-consumer|wishlist_service|.venv/bin/faststream run events_consumer.app:app
shipping-consumer|shipping_service|.venv/bin/faststream run events_consumer.app:app
product-taskiq-worker|product_service|.venv/bin/taskiq worker tasks.broker:taskiq_broker tasks.image_tasks --workers 1
supplier-taskiq-worker|supplier_service|.venv/bin/taskiq worker tasks.broker:taskiq_broker tasks.sync_tasks tasks.tracking_tasks tasks.cj_payment_tasks --workers 1
notification-taskiq-worker|notification_service|.venv/bin/taskiq worker tasks.broker:taskiq_broker tasks.email_tasks --workers 1
supplier-taskiq-scheduler|supplier_service|.venv/bin/taskiq scheduler tasks.scheduler:supplier_task_scheduler tasks.sync_tasks tasks.tracking_tasks tasks.cj_payment_tasks
EOF
  # No --hostname: next's default binding answers on both localhost and
  # 127.0.0.1, and next.config.js already allows the 127.0.0.1 dev origin.
  printf 'frontend|../frontend|npm run dev -- --port %s\n' "$FRONTEND_PORT"
  # Prefixed with env(1) rather than CJ_TRANSPORT=...: start_one execs the
  # command word for word, so a bare VAR=value would be taken as the program.
  # The row disappears when the sibling checkout is absent, so a machine
  # without api-mcp still brings the rest of the stack up.
  if [ -d "$BACKEND_DIR/$CJ_MCP_DIR" ]; then
    printf 'cj-mcp|%s|env CJ_TRANSPORT=http CJ_HTTP_PORT=%s node dist/mcp-server/index.cjs\n' \
      "$CJ_MCP_DIR" "$CJ_MCP_PORT"
  fi
}

# Services owning an alembic tree, in the order compose brings them up.
MIGRATABLE="user_service product_service supplier_service notification_service order_service payment_service cart_service wishlist_service shipping_service"

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m warn\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m!!\033[0m %s\n' "$*" >&2; exit 1; }

port_busy() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

# --------------------------------------------------------------------------
# Infra
# --------------------------------------------------------------------------
cmd_install() {
  say "Installing postgresql@16, redis and rabbitmq via Homebrew"
  brew install postgresql@16 redis rabbitmq
}

require_bin() {
  command -v "$1" >/dev/null 2>&1 || die "'$1' not found. Run: ./local/dev.sh install"
}

pg_running() { [ -f "$PGDATA/postmaster.pid" ] && pg_ctl -D "$PGDATA" status >/dev/null 2>&1; }

pg_start() {
  require_bin pg_ctl
  [ -d "$PGDATA" ] || die "No local cluster yet. Run: ./local/dev.sh init"
  if pg_running; then say "postgres already running"; return; fi
  if port_busy "$POSTGRES_PORT"; then
    die "port $POSTGRES_PORT is taken (the compose 'db' container?). Stop it first: (cd $BACKEND_DIR && docker compose down)"
  fi
  say "starting postgres on :$POSTGRES_PORT"
  # Same tuning the compose 'db' service uses, so pool sizing behaves alike.
  pg_ctl -D "$PGDATA" -l "$LOG_DIR/postgres.log" -w -o \
    "-p $POSTGRES_PORT -k $RUN_DIR -c max_connections=300 -c shared_buffers=256MB -c effective_cache_size=768MB -c work_mem=4MB -c max_wal_size=1GB" \
    start
}

pg_stop() {
  if pg_running; then say "stopping postgres"; pg_ctl -D "$PGDATA" -m fast -w stop; fi
}

psql_run() { PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -p "$POSTGRES_PORT" -U "$POSTGRES_USER" "$@"; }

redis_pid_file="$RUN_DIR/redis.pid"
redis_running() { [ -f "$redis_pid_file" ] && kill -0 "$(cat "$redis_pid_file")" 2>/dev/null; }

redis_start() {
  require_bin redis-server
  if redis_running; then say "redis already running"; return; fi
  if port_busy "$REDIS_PORT"; then die "port $REDIS_PORT is already in use"; fi
  say "starting redis on :$REDIS_PORT"
  mkdir -p "$DATA_DIR/redis"
  redis-server --port "$REDIS_PORT" --requirepass "$REDIS_PASSWORD" \
    --appendonly yes --dir "$DATA_DIR/redis" \
    --daemonize yes --pidfile "$redis_pid_file" --logfile "$LOG_DIR/redis.log"
}

redis_stop() {
  if redis_running; then
    say "stopping redis"
    redis-cli -p "$REDIS_PORT" -a "$REDIS_PASSWORD" --no-auth-warning shutdown nosave 2>/dev/null || kill "$(cat "$redis_pid_file")"
    rm -f "$redis_pid_file"
  fi
}

rabbit_running() { rabbitmqctl -q status >/dev/null 2>&1; }

rabbit_start() {
  require_bin rabbitmq-server
  if rabbit_running; then say "rabbitmq already running"; return; fi
  if port_busy "$RABBITMQ_PORT"; then die "port $RABBITMQ_PORT is already in use"; fi
  say "starting rabbitmq on :$RABBITMQ_PORT (management UI on :15672)"
  rabbitmq-server -detached
  # `-detached` returns before the node registers with epmd, so await_startup
  # on its own loses a race with a cold boot (~2s here).
  local tries=0
  until rabbitmqctl -q await_startup >/dev/null 2>&1; do
    tries=$((tries + 1))
    [ "$tries" -gt 60 ] && die "rabbitmq did not come up -- see $BREW_PREFIX/var/log/rabbitmq/"
    sleep 1
  done
}

rabbit_stop() {
  if rabbit_running; then say "stopping rabbitmq"; rabbitmqctl -q stop; fi
}

cmd_infra() {
  case "${1:-up}" in
    up)     pg_start; redis_start; rabbit_start ;;
    down)   rabbit_stop; redis_stop; pg_stop ;;
    status) pg_running && echo "postgres  up" || echo "postgres  down"
            redis_running && echo "redis     up" || echo "redis     down"
            rabbit_running && echo "rabbitmq  up" || echo "rabbitmq  down" ;;
    *) die "infra: expected up|down|status" ;;
  esac
}

# --------------------------------------------------------------------------
# One-time initialisation
# --------------------------------------------------------------------------
cmd_init() {
  require_bin initdb

  if [ ! -d "$PGDATA" ]; then
    say "creating postgres cluster at $PGDATA"
    local pwfile="$DATA_DIR/.initpw"
    umask 077; printf '%s' "$POSTGRES_PASSWORD" > "$pwfile"
    initdb -D "$PGDATA" -U "$POSTGRES_USER" --auth-local=trust --auth-host=scram-sha-256 --pwfile="$pwfile" >/dev/null
    rm -f "$pwfile"
  else
    say "postgres cluster already exists"
  fi

  pg_start

  say "creating per-service databases"
  # Names come from db/init-databases.sql so the two never drift apart.
  local dbs
  dbs="$(sed -n -E 's/^CREATE DATABASE ([a-z_]+);.*/\1/p' "$BACKEND_DIR/db/init-databases.sql")"
  for db in $dbs; do
    if [ -z "$(psql_run -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db'")" ]; then
      psql_run -d postgres -q -c "CREATE DATABASE $db" && echo "  created $db"
    fi
  done

  redis_start
  rabbit_start

  say "provisioning rabbitmq user '$RABBITMQ_USER'"
  rabbitmq-plugins -q enable rabbitmq_management >/dev/null 2>&1 || true
  if ! rabbitmqctl -q list_users | grep -qF "$RABBITMQ_USER"; then
    rabbitmqctl -q add_user "$RABBITMQ_USER" "$RABBITMQ_PASSWORD"
  else
    rabbitmqctl -q change_password "$RABBITMQ_USER" "$RABBITMQ_PASSWORD"
  fi
  rabbitmqctl -q set_user_tags "$RABBITMQ_USER" administrator
  rabbitmqctl -q set_permissions -p / "$RABBITMQ_USER" ".*" ".*" ".*"

  say "init complete -- now run: ./local/dev.sh up"
}

# --------------------------------------------------------------------------
# Migrations + processes
# --------------------------------------------------------------------------
service_env() {
  # Exported for every child: these two are read via os.getenv, not from .env.
  export OTEL_TRACES_DISABLED=true
  unset PROMETHEUS_MULTIPROC_DIR || true
  export PYTHONPATH="$BACKEND_DIR${PYTHONPATH:+:$PYTHONPATH}"
  export PYTHONUNBUFFERED=1
  # Set here rather than in .env.local: that file is tracked, and a relative
  # path would resolve against each service's own cwd.
  export MEDIA_ROOT="$DATA_DIR/media"
}

cmd_migrate() {
  service_env
  pg_start
  for svc in $MIGRATABLE; do
    say "alembic upgrade head -- $svc"
    ( cd "$BACKEND_DIR/$svc" && ./.venv/bin/alembic upgrade head )
  done
}

pid_file() { printf '%s/%s.pid' "$RUN_DIR" "$1"; }
log_file() { printf '%s/%s.log' "$LOG_DIR" "$1"; }

proc_running() {
  local pf; pf="$(pid_file "$1")"
  [ -f "$pf" ] && kill -0 "$(cat "$pf")" 2>/dev/null
}

start_one() {
  # Job control is on (set -m) so each child becomes its own process group
  # leader -- that is what lets stop_one take down faststream's and taskiq's
  # forked children along with the parent.
  local name="$1" dir="$2" cmd="$3"
  if proc_running "$name"; then echo "  $name already running"; return; fi
  # Each runtime has its own "are the deps installed?" marker.
  case "$cmd" in
    .venv/bin/*)
      [ -x "$BACKEND_DIR/$dir/.venv/bin/python" ] || die "$dir has no .venv -- run 'uv sync' in it first" ;;
    npm*)
      require_bin npm
      [ -d "$BACKEND_DIR/$dir/node_modules" ] || die "$dir has no node_modules -- run 'npm install' in it first" ;;
    env*node*|node*)
      require_bin node
      [ -f "$BACKEND_DIR/$dir/dist/mcp-server/index.cjs" ] || \
        die "$dir is not built -- run 'npm install && npm run build' in it first" ;;
  esac
  local reload=""
  [ "${RELOAD:-0}" = "1" ] && case "$cmd" in *uvicorn*) reload=" --reload";; esac
  ( cd "$BACKEND_DIR/$dir" && exec nohup $cmd$reload >> "$(log_file "$name")" 2>&1 ) &
  echo $! > "$(pid_file "$name")"
  echo "  started $name (pid $!)"
}

stop_one() {
  local name="$1" pf; pf="$(pid_file "$name")"
  if proc_running "$name"; then
    local pid; pid="$(cat "$pf")"
    # Kill the process group first; fall back to the bare pid plus its direct
    # children if this process never became a group leader.
    kill -TERM -"$pid" 2>/dev/null || {
      pkill -TERM -P "$pid" 2>/dev/null || true
      kill -TERM "$pid" 2>/dev/null || true
    }
    echo "  stopped $name"
  fi
  rm -f "$pf"
}

cmd_services() {
  case "${1:-up}" in
    up)
      service_env
      set -m
      say "starting ${2:-all} services"
      while IFS='|' read -r name dir cmd; do
        [ -n "$name" ] || continue
        [ -n "${2:-}" ] && [ "$2" != "$name" ] && continue
        start_one "$name" "$dir" "$cmd"
      done < <(processes)
      ;;
    down)
      say "stopping services"
      while IFS='|' read -r name _ _; do
        [ -n "$name" ] || continue
        [ -n "${2:-}" ] && [ "$2" != "$name" ] && continue
        stop_one "$name"
      done < <(processes)
      ;;
    status)
      while IFS='|' read -r name dir cmd; do
        [ -n "$name" ] || continue
        if proc_running "$name"; then
          printf '  \033[32m%-28s up\033[0m   %s\n' "$name" "$(cat "$(pid_file "$name")")"
        else
          printf '  \033[31m%-28s down\033[0m\n' "$name"
        fi
      done < <(processes)
      ;;
    *) die "services: expected up|down|status" ;;
  esac
}

cmd_up() {
  cmd_infra up
  cmd_migrate
  cmd_services up "${1:-}"
  echo
  say "frontend on http://localhost:$FRONTEND_PORT  |  gateway on http://127.0.0.1:8000"
  say "gateway docs http://127.0.0.1:8000/docs  |  rabbitmq UI http://127.0.0.1:15672"
  [ -d "$BACKEND_DIR/$CJ_MCP_DIR" ] && \
    say "cj mcp on http://127.0.0.1:$CJ_MCP_PORT/mcp  |  health http://127.0.0.1:$CJ_MCP_PORT/health"
  say "logs: ./local/dev.sh logs <name>   status: ./local/dev.sh status"
}

cmd_down() { cmd_services down "${1:-}"; [ -n "${1:-}" ] || cmd_infra down; }

cmd_status() { cmd_infra status; echo; cmd_services status; }

cmd_logs() {
  [ -n "${1:-}" ] || die "logs: name required (e.g. user-service, postgres)"
  tail -n 100 -f "$(log_file "$1")"
}

cmd_restart() {
  [ -n "${1:-}" ] || die "restart: name required"
  service_env
  set -m
  stop_one "$1"
  while IFS='|' read -r name dir cmd; do
    [ "$name" = "$1" ] && start_one "$name" "$dir" "$cmd"
  done < <(processes)
}

cmd_reset() {
  read -r -p "Delete $DATA_DIR (all local DB/redis data)? [y/N] " answer
  [ "$answer" = "y" ] || die "aborted"
  cmd_down
  rm -rf "$DATA_DIR" "$RUN_DIR" "$LOG_DIR"
  say "local data removed. Run './local/dev.sh init' to start over."
}

# Dead-letter queues: every consumer parks a message here once its retries
# are exhausted (or its payload is invalid). Replay only after fixing the
# cause -- a message that still fails just goes round and parks again.
cmd_dlq() {
  case "${1:-}" in
    list)
      rabbitmqctl list_queues name messages -q \
        | awk '$1 ~ /(\.dlq|dead_letter)$/ { printf "  %6s  %s\n", $2, $1 }'
      ;;
    replay)
      shift
      [ -n "${1:-}" ] || die "dlq replay: queue name required (see: dlq list)"
      # Any service venv has aio-pika and the shared package; order-service's is used.
      (cd "$BACKEND_DIR/order_service" && \
        PYTHONPATH="$BACKEND_DIR" .venv/bin/python -m shared.messaging.dead_letter_replay "$@")
      ;;
    *) die "dlq: list | replay <queue> [--to <queue>] [--limit N]" ;;
  esac
}

case "${1:-}" in
  install)  shift; cmd_install "$@" ;;
  init)     shift; cmd_init "$@" ;;
  infra)    shift; cmd_infra "$@" ;;
  migrate)  shift; cmd_migrate "$@" ;;
  services) shift; cmd_services "$@" ;;
  up)       shift; cmd_up "$@" ;;
  down)     shift; cmd_down "$@" ;;
  restart)  shift; cmd_restart "$@" ;;
  status)   shift; cmd_status "$@" ;;
  logs)     shift; cmd_logs "$@" ;;
  reset)    shift; cmd_reset "$@" ;;
  dlq)      shift; cmd_dlq "$@" ;;
  *) sed -n '2,25p' "${BASH_SOURCE[0]}" | sed -E 's/^#[[:space:]]?//'; exit 1 ;;
esac
