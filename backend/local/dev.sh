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
#   ./local/dev.sh cj-sandbox status|ship|deliver|poll <order_id>
#                                   # play CJ's part for a sandbox order
#                                   # (CJ_DROPSHIPPING_SANDBOX=true only)
#   ./local/dev.sh cj-webhook tunnel|tunnel-stop|store-open-id|subscribe|status
#                                   # CJ's stock pushes, through a cloudflared
#                                   # tunnel to the gateway
#   ./local/dev.sh vault up|down|status
#                                   # the local Vault holding every secret
#   ./local/dev.sh vault import [--dry-run]
#                                   # one-time: move secrets from the config
#                                   # file into Vault (you run it)
#   ./local/dev.sh test <service_dir> [pytest args]
#                                   # a service's tests, with its Vault identity
#   ./local/dev.sh storage status|import-local
#                                   # the local S3 server (SeaweedFS): buckets
#                                   # and counts; one-time copy of local-disk
#                                   # designs and return photos into it
#   ./local/dev.sh images mirror    # copy CJ catalogue images into S3 now
#
# RELOAD=1           ./local/dev.sh up   HTTP services start with --reload.
# FRONTEND_PORT=3000 ./local/dev.sh up   override the Next.js port.
# ADMIN_JS_PORT=3002 ./local/dev.sh up   override the AdminJS port.
# CJ_MCP_PORT=3009   ./local/dev.sh up   override the CJ MCP server port.
# S3_PORT=8333       ./local/dev.sh up   override the local S3 server's port.

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
  for file in "$BACKEND_DIR/.env"; do
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
POSTGRES_PORT="$(env_get POSTGRES_PORT)"
REDIS_PORT="$(env_get REDIS_PORT)"
RABBITMQ_USER="$(env_get RABBITMQ_USER)"
RABBITMQ_PORT="$(env_get RABBITMQ_PORT)"
: "${POSTGRES_PORT:=5432}" "${REDIS_PORT:=6379}" "${RABBITMQ_PORT:=5672}"
# The three infra passwords live in Vault (secret/ecommerce/shared-infra) and
# are loaded by load_infra_secrets only where a command needs them.
POSTGRES_PASSWORD="" REDIS_PASSWORD="" RABBITMQ_PASSWORD=""

# --------------------------------------------------------------------------
# Vault: every secret lives here, one KV path per service, and each process
# signs in with its own AppRole, so it can read only its own path plus the
# infra credentials (shared-infra) every process needs.
# --------------------------------------------------------------------------
VAULT_PORT="${VAULT_PORT:-8200}"
VAULT_LOCAL_ADDR="http://127.0.0.1:$VAULT_PORT"
VAULT_DATA="$DATA_DIR/vault"
VAULT_RUN="$RUN_DIR/vault"
# Unseal key + root token. One key share, kept on this machine only (git-ignored).
VAULT_INIT_FILE="$VAULT_RUN/init.json"
VAULT_PREFIX="ecommerce"

# identity | service dir. Each identity gets a policy and an AppRole of its name.
vault_identities() {
  cat <<'EOF'
api-gateway|api_gateway
user-service|user_service
product-service|product_service
supplier-service|supplier_service
order-service|order_service
payment-service|payment_service
cart-service|cart_service
wishlist-service|wishlist_service
shipping-service|shipping_service
notification-service|notification_service
admin-js|admin-js-service
shared-tests|shared
EOF
}

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

# AdminJS listens on 3000 inside compose and is published on 3001; locally it
# listens on 3001 directly so the URL is the same either way.
ADMIN_JS_PORT="${ADMIN_JS_PORT:-3001}"

# --------------------------------------------------------------------------
# Object storage: SeaweedFS speaks S3 on $S3_PORT, standing in for AWS S3.
# Two buckets, never mixed: the catalogue one is anonymously readable (the
# storefront loads its images straight from it), the private one is reachable
# only with a service's own key. Every service key is scoped by bucket and
# prefix (local/s3_local.py), and kept in that service's Vault path.
# --------------------------------------------------------------------------
S3_PORT="${S3_PORT:-8333}"
S3_LOCAL_ENDPOINT="http://127.0.0.1:$S3_PORT"
S3_CATALOGUE_BUCKET="ecommerce-catalogue"
S3_PRIVATE_BUCKET="ecommerce-private"
SEAWEED_DATA="$DATA_DIR/seaweedfs"
SEAWEED_RUN="$RUN_DIR/seaweedfs"
# master / volume / filer HTTP ports (gRPC: each + 10000). The volume server
# moves off its default 8080, which too many other tools want.
SEAWEED_MASTER_PORT=9333 SEAWEED_VOLUME_PORT=8380 SEAWEED_FILER_PORT=8888

# --------------------------------------------------------------------------
# The process table: name | service dir | command (relative to that dir)
#
# Mirrors docker-compose.yml minus the observability stack, traefik and
# pgadmin.  gunicorn is replaced by plain uvicorn: one process is enough
# locally, and it keeps PROMETHEUS_MULTIPROC_DIR out of the picture.
#
# The Node rows (frontend, admin-js, cj-mcp) are appended after the heredoc
# because the quoted heredoc cannot interpolate their ports.
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
product-taskiq-worker|product_service|.venv/bin/taskiq worker tasks.broker:taskiq_broker tasks.image_tasks tasks.catalogue_image_tasks --workers 1
supplier-taskiq-worker|supplier_service|.venv/bin/taskiq worker tasks.broker:taskiq_broker tasks.sync_tasks tasks.tracking_tasks tasks.cj_payment_tasks tasks.stock_tasks --workers 1
notification-taskiq-worker|notification_service|.venv/bin/taskiq worker tasks.broker:taskiq_broker tasks.email_tasks --workers 1
product-taskiq-scheduler|product_service|.venv/bin/taskiq scheduler tasks.scheduler:product_task_scheduler tasks.catalogue_image_tasks
supplier-taskiq-scheduler|supplier_service|.venv/bin/taskiq scheduler tasks.scheduler:supplier_task_scheduler tasks.sync_tasks tasks.tracking_tasks tasks.cj_payment_tasks tasks.stock_tasks
EOF
  # No --hostname: next's default binding answers on both localhost and
  # 127.0.0.1, and next.config.js already allows the 127.0.0.1 dev origin.
  printf 'frontend|../frontend|npm run dev -- --port %s\n' "$FRONTEND_PORT"
  # admin-js reads the same backend/.env compose hands it, via
  # node's own --env-file (see its start:local script).  The values that differ
  # outside compose are pinned here: variables already in the environment win
  # over --env-file, so the container host names in .env never apply.
  printf 'admin-js|admin-js-service|env NODE_ENV=development ADMIN_JS_PORT=%s REDIS_HOST=127.0.0.1 REDIS_PORT=%s API_GATEWAY_SERVICE_URL=http://127.0.0.1:8000 npm run start:local\n' \
    "$ADMIN_JS_PORT" "$REDIS_PORT"
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

# "pid command" of whatever listens on a port, for the message naming it.
port_owner() {
  local pid; pid="$(lsof -nP -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -n 1)"
  [ -n "$pid" ] && printf '%s %s' "$pid" "$(ps -o command= -p "$pid" 2>/dev/null)"
}

# The port a processes() row listens on, read from its own command line:
# uvicorn/next take --port, admin-js and cj-mcp get it through env(1).
# Workers and consumers listen on nothing and print an empty string.
cmd_port() {
  local re='(--port |ADMIN_JS_PORT=|CJ_HTTP_PORT=)([0-9]+)'
  [[ "$1" =~ $re ]] && printf '%s' "${BASH_REMATCH[2]}"
  return 0
}

# --------------------------------------------------------------------------
# Infra
# --------------------------------------------------------------------------
cmd_install() {
  say "Installing postgresql@16, redis, rabbitmq, cloudflared, seaweedfs and vault via Homebrew"
  # cloudflared: the tunnel CJ's stock webhook reaches the local gateway through.
  # seaweedfs: the local S3 server images are stored in.
  brew install postgresql@16 redis rabbitmq cloudflared seaweedfs
  brew tap hashicorp/tap
  brew install hashicorp/tap/vault
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

# Over the unix socket, which initdb set to trust: no password needed.
psql_run() { psql -h "$RUN_DIR" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" "$@"; }

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

vault_pid_file="$RUN_DIR/vault.pid"
vault_running() { [ -f "$vault_pid_file" ] && kill -0 "$(cat "$vault_pid_file")" 2>/dev/null; }

# 200 unsealed, 501 not initialised, 503 sealed, 000 not answering.
vault_health() {
  curl -s -o /dev/null -w '%{http_code}' "$VAULT_LOCAL_ADDR/v1/sys/health?standbyok=true" 2>/dev/null || true
}

# One field of the init file (a JSON document), e.g. root_token.
vault_init_field() {
  python3 -c 'import json, sys; d = json.load(open(sys.argv[1])); f = d[sys.argv[2]]; print(f[0] if isinstance(f, list) else f)' \
    "$VAULT_INIT_FILE" "$1"
}

# The vault CLI as the operator (root token), for dev.sh's own bookkeeping.
vault_op() {
  [ -f "$VAULT_INIT_FILE" ] || die "Vault is not initialised yet. Run: ./local/dev.sh vault up"
  VAULT_ADDR="$VAULT_LOCAL_ADDR" VAULT_TOKEN="$(vault_init_field root_token)" vault "$@"
}

vault_start() {
  require_bin vault
  mkdir -p "$VAULT_DATA" "$VAULT_RUN"
  chmod 700 "$VAULT_RUN"
  if ! vault_running; then
    if port_busy "$VAULT_PORT"; then die "port $VAULT_PORT is already in use (held by $(port_owner "$VAULT_PORT"))"; fi
    cat > "$VAULT_RUN/server.hcl" <<EOF
storage "file" {
  path = "$VAULT_DATA"
}
listener "tcp" {
  address     = "127.0.0.1:$VAULT_PORT"
  tls_disable = 1
}
api_addr      = "$VAULT_LOCAL_ADDR"
disable_mlock = true
ui            = true
EOF
    say "starting vault on :$VAULT_PORT"
    ( exec nohup vault server -config="$VAULT_RUN/server.hcl" >> "$LOG_DIR/vault.log" 2>&1 ) &
    echo $! > "$vault_pid_file"
    local tries=0
    while [ "$(vault_health)" = "000" ]; do
      tries=$((tries + 1))
      [ "$tries" -gt 30 ] && die "vault did not come up -- see $LOG_DIR/vault.log"
      sleep 1
    done
  else
    say "vault already running"
  fi
  if [ "$(vault_health)" = "501" ]; then
    say "initialising vault (one key share, kept in $VAULT_INIT_FILE -- this machine only)"
    ( umask 077; VAULT_ADDR="$VAULT_LOCAL_ADDR" vault operator init -key-shares=1 -key-threshold=1 -format=json > "$VAULT_INIT_FILE" )
  fi
  if [ "$(vault_health)" = "503" ]; then
    VAULT_ADDR="$VAULT_LOCAL_ADDR" vault operator unseal "$(vault_init_field unseal_keys_b64)" >/dev/null
  fi
  [ "$(vault_health)" = "200" ] || die "vault is not ready (health $(vault_health)) -- see $LOG_DIR/vault.log"
  vault_bootstrap
}

vault_stop() {
  if vault_running; then say "stopping vault"; kill "$(cat "$vault_pid_file")" 2>/dev/null || true; fi
  rm -f "$vault_pid_file"
}

# Idempotent: the KV engine, AppRole auth, and per identity a read-only policy
# on its own path + shared-infra, an AppRole, and its credentials in files.
vault_bootstrap() {
  # Captured, not piped into grep -q: under pipefail an early-exiting grep
  # would fail the check and try to enable an engine that already exists.
  local engines auths
  engines="$(vault_op secrets list -format=json)"
  [[ "$engines" == *'"secret/"'* ]] || vault_op secrets enable -path=secret -version=2 kv >/dev/null
  auths="$(vault_op auth list -format=json)"
  [[ "$auths" == *'"approle/"'* ]] || vault_op auth enable approle >/dev/null
  local name
  while IFS='|' read -r name _; do
    printf 'path "secret/data/%s/%s" { capabilities = ["read"] }\npath "secret/data/%s/shared-infra" { capabilities = ["read"] }\n' \
      "$VAULT_PREFIX" "$name" "$VAULT_PREFIX" | vault_op policy write "$name" - >/dev/null
    vault_op write "auth/approle/role/$name" token_policies="$name" token_ttl=1h token_max_ttl=24h secret_id_ttl=0 >/dev/null
    # Every identity's own path exists, empty when it holds no secret of its own
    # (cart, wishlist, shipping): a missing path makes the service refuse to start.
    vault_op kv metadata get "secret/$VAULT_PREFIX/$name" >/dev/null 2>&1 || \
      printf '{"data": {}}' | vault_op write "secret/data/$VAULT_PREFIX/$name" - >/dev/null
    ( umask 077
      vault_op read -field=role_id "auth/approle/role/$name/role-id" > "$VAULT_RUN/$name.role-id"
      # A secret id is issued once and reused; delete the file to rotate it.
      [ -s "$VAULT_RUN/$name.secret-id" ] || \
        vault_op write -f -field=secret_id "auth/approle/role/$name/secret-id" > "$VAULT_RUN/$name.secret-id" )
  done < <(vault_identities)
}

# The infra passwords dev.sh itself needs (redis, rabbitmq, a new cluster).
load_infra_secrets() {
  local path="secret/$VAULT_PREFIX/shared-infra"
  vault_op kv get "$path" >/dev/null 2>&1 || \
    die "Vault has no $path yet. Move the secrets in first: ./local/dev.sh vault import"
  POSTGRES_PASSWORD="$(vault_op kv get -field=POSTGRES_PASSWORD "$path")"
  REDIS_PASSWORD="$(vault_op kv get -field=REDIS_PASSWORD "$path")"
  RABBITMQ_PASSWORD="$(vault_op kv get -field=RABBITMQ_PASSWORD "$path")"
}

vault_identity_for_dir() {
  local name dir
  while IFS='|' read -r name dir; do
    [ "$dir" = "$1" ] && { printf '%s' "$name"; return; }
  done < <(vault_identities)
}

# Point a Python process at its own Vault identity (call inside its subshell).
# Settings read the secrets themselves (shared.vault.VaultSettingsSource).
export_vault_identity() {
  local name; name="$(vault_identity_for_dir "$1")"
  [ -n "$name" ] || return 0
  export VAULT_ADDR="$VAULT_LOCAL_ADDR"
  export VAULT_ROLE_ID_FILE="$VAULT_RUN/$name.role-id"
  export VAULT_SECRET_ID_FILE="$VAULT_RUN/$name.secret-id"
  export VAULT_SECRET_PATHS="$VAULT_PREFIX/shared-infra,$VAULT_PREFIX/$name"
}

# The secrets a Node process reads, and nothing more: its AppRole may read the
# whole shared-infra path, but admin-js needs only the Redis password from it.
vault_node_keys() {
  case "$1" in
    admin-js) printf 'COOKIE_SECRET,REDIS_PASSWORD' ;;
    *) die "no secret list for Node identity $1" ;;
  esac
}

# admin-js is Node and has no Vault client: read its secrets here, signed in
# with its own AppRole, and export them into its own environment (call inside
# its subshell). Exported variables win over the file node --env-file reads.
export_vault_secrets_for_node() {
  local name="$1" exports
  exports="$(python3 "$LOCAL_DIR/vault_read.py" \
    --address "$VAULT_LOCAL_ADDR" --keys "$(vault_node_keys "$name")" \
    --role-id-file "$VAULT_RUN/$name.role-id" --secret-id-file "$VAULT_RUN/$name.secret-id" \
    "$VAULT_PREFIX/shared-infra" "$VAULT_PREFIX/$name")" || die "$name could not read its secrets from Vault"
  eval "$exports"
}

seaweed_pid_file="$RUN_DIR/seaweedfs.pid"
seaweed_running() { [ -f "$seaweed_pid_file" ] && kill -0 "$(cat "$seaweed_pid_file")" 2>/dev/null; }

# local/s3_local.py as the operator (root token), on product-service's venv
# (it has boto3). It prints names only, never a key.
s3_local() {
  [ -x "$BACKEND_DIR/product_service/.venv/bin/python" ] || die "product_service has no .venv -- run 'uv sync' in it first"
  VAULT_ADDR="$VAULT_LOCAL_ADDR" VAULT_TOKEN="$(vault_init_field root_token)" VAULT_KV_PREFIX="$VAULT_PREFIX" \
    S3_LOCAL_ENDPOINT="$S3_LOCAL_ENDPOINT" S3_CATALOGUE_BUCKET="$S3_CATALOGUE_BUCKET" S3_PRIVATE_BUCKET="$S3_PRIVATE_BUCKET" \
    "$BACKEND_DIR/product_service/.venv/bin/python" -I "$LOCAL_DIR/s3_local.py" "$@"
}

seaweed_start() {
  require_bin weed
  mkdir -p "$SEAWEED_DATA" "$SEAWEED_RUN"
  chmod 700 "$SEAWEED_RUN"
  # Keys missing from Vault are generated, and the identities file is
  # rendered from Vault: nothing to set up by hand. Exit 10 = it changed.
  local rendered=0
  s3_local bootstrap --config "$SEAWEED_RUN/s3.json" || rendered=$?
  [ "$rendered" = 0 ] || [ "$rendered" = 10 ] || die "could not prepare the S3 credentials (see above)"
  if seaweed_running; then
    if [ "$rendered" = 10 ]; then
      warn "S3 identities changed while seaweedfs runs: restarting it to load them"
      seaweed_stop
    else
      say "seaweedfs already running"; return
    fi
  fi
  local port
  for port in "$S3_PORT" "$SEAWEED_MASTER_PORT" "$SEAWEED_VOLUME_PORT" "$SEAWEED_FILER_PORT"; do
    port_busy "$port" && die "port $port is already in use (held by $(port_owner "$port"))"
  done
  say "starting seaweedfs, S3 on :$S3_PORT"
  local kek
  kek="$(vault_op kv get -field=SEAWEEDFS_SSE_KEK "secret/$VAULT_PREFIX/tooling")"
  # The key that encrypts objects at rest reaches only this process. Small
  # volumes and a fixed count: the defaults (30 GB each, as many as the disk
  # holds) run out of slots after a couple of buckets on a laptop.
  ( export WEED_S3_SSE_KEK="$kek"
    exec nohup weed server -dir="$SEAWEED_DATA" -ip=127.0.0.1 -ip.bind=127.0.0.1 \
      -master.port="$SEAWEED_MASTER_PORT" -volume.port="$SEAWEED_VOLUME_PORT" -filer.port="$SEAWEED_FILER_PORT" \
      -master.volumeSizeLimitMB=128 -volume.max=64 \
      -s3 -s3.port="$S3_PORT" -s3.port.iceberg=0 -s3.port.lance=0 -s3.config="$SEAWEED_RUN/s3.json" \
      >> "$LOG_DIR/seaweedfs.log" 2>&1 ) &
  echo $! > "$seaweed_pid_file"
  local tries=0
  until [ "$(curl -s -o /dev/null -w '%{http_code}' "$S3_LOCAL_ENDPOINT/" 2>/dev/null || true)" != "000" ]; do
    tries=$((tries + 1))
    [ "$tries" -gt 60 ] && die "seaweedfs did not come up -- see $LOG_DIR/seaweedfs.log"
    sleep 1
  done
  # The S3 port answers before the filer is ready to take a bucket.
  tries=0
  until s3_local buckets >/dev/null 2>&1; do
    tries=$((tries + 1))
    [ "$tries" -gt 30 ] && { s3_local buckets; die "could not create the S3 buckets -- see $LOG_DIR/seaweedfs.log"; }
    sleep 1
  done
}

seaweed_stop() {
  if seaweed_running; then
    say "stopping seaweedfs"
    local pid; pid="$(cat "$seaweed_pid_file")"
    kill "$pid" 2>/dev/null || true
    # weed server runs master, volume and filer in one process and takes
    # ~20s to shut them down; wait for it to let go of its ports, or an
    # immediate restart fails to bind.
    local tries=0
    while kill -0 "$pid" 2>/dev/null && [ "$tries" -lt 120 ]; do sleep 0.5; tries=$((tries + 1)); done
    kill -0 "$pid" 2>/dev/null && { warn "seaweedfs did not stop in 60s: killing it"; kill -9 "$pid" 2>/dev/null || true; }
  fi
  rm -f "$seaweed_pid_file"
}

cmd_storage() {
  case "${1:-status}" in
    status)
      if ! seaweed_running; then echo "seaweedfs down"; return; fi
      echo "seaweedfs up -- S3 at $S3_LOCAL_ENDPOINT"
      s3_local status ;;
    import-local)
      seaweed_running || die "seaweedfs is not running -- ./local/dev.sh infra up"
      s3_local import-local --media "$DATA_DIR/media" --evidence "$DATA_DIR/private-media" ;;
    *) die "storage: expected status|import-local" ;;
  esac
}

# CJ catalogue images into the catalogue bucket, now: the 15-minute task
# does one batch per run, this repeats batches until nothing is due.
cmd_images() {
  case "${1:-}" in
    mirror)
      service_env
      (export_vault_identity product_service; cd "$BACKEND_DIR/product_service" && .venv/bin/python -m tools.mirror_catalogue_images) ;;
    *) die "images: expected mirror" ;;
  esac
}

cmd_vault() {
  case "${1:-status}" in
    up)     vault_start ;;
    down)   vault_stop ;;
    status)
      if ! vault_running; then echo "vault     down"; return; fi
      echo "vault     up (health $(vault_health))"
      local name
      # tooling and observability: read by no local process, root token only.
      for name in shared-infra $(vault_identities | cut -d'|' -f1) tooling observability; do
        # Key names only, never values.
        printf '  %-22s %s\n' "$name" "$(vault_op kv get -format=json "secret/$VAULT_PREFIX/$name" 2>/dev/null \
          | python3 -c 'import json, sys; print(", ".join(sorted(json.load(sys.stdin)["data"]["data"])))' 2>/dev/null || echo '(empty)')"
      done ;;
    import)
      shift
      vault_start
      # order-service's venv has python-dotenv: the file is parsed exactly as Settings parses it.
      VAULT_ADDR="$VAULT_LOCAL_ADDR" VAULT_TOKEN="$(vault_init_field root_token)" \
        "$BACKEND_DIR/order_service/.venv/bin/python" "$LOCAL_DIR/vault_import.py" \
        --env-file "$BACKEND_DIR/.env" --prefix "$VAULT_PREFIX" "$@" ;;
    *) die "vault: expected up|down|status|import" ;;
  esac
}

cmd_infra() {
  case "${1:-up}" in
    up)     vault_start; load_infra_secrets; pg_start; redis_start; rabbit_start; seaweed_start ;;
    down)   if vault_running && [ -f "$VAULT_INIT_FILE" ]; then load_infra_secrets; fi
            seaweed_stop; rabbit_stop; redis_stop; pg_stop; vault_stop ;;
    status) vault_running && echo "vault     up" || echo "vault     down"
            pg_running && echo "postgres  up" || echo "postgres  down"
            redis_running && echo "redis     up" || echo "redis     down"
            rabbit_running && echo "rabbitmq  up" || echo "rabbitmq  down"
            seaweed_running && echo "seaweedfs up" || echo "seaweedfs down" ;;
    *) die "infra: expected up|down|status" ;;
  esac
}

# --------------------------------------------------------------------------
# One-time initialisation
# --------------------------------------------------------------------------
cmd_init() {
  require_bin initdb
  vault_start
  load_infra_secrets

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
  # Set here rather than in .env: a relative path would resolve against each
  # service's own cwd.
  export MEDIA_ROOT="$DATA_DIR/media"
  # Return photos are private: kept apart from the publicly served media.
  export RETURN_EVIDENCE_ROOT="$DATA_DIR/private-media"
  # Images live in the local S3 server. Only the non-secret half is set here;
  # each service's access key pair comes from its own Vault path.
  export OBJECT_STORAGE_BACKEND=s3
  export AWS_S3_ENDPOINT_URL="$S3_LOCAL_ENDPOINT"
  export AWS_S3_REGION=us-east-1
  export AWS_S3_CATALOGUE_BUCKET="$S3_CATALOGUE_BUCKET"
  export AWS_S3_CATALOGUE_PUBLIC_BASE_URL="$S3_LOCAL_ENDPOINT/$S3_CATALOGUE_BUCKET"
  export AWS_S3_PRIVATE_BUCKET="$S3_PRIVATE_BUCKET"
}

cmd_migrate() {
  service_env
  pg_start
  for svc in $MIGRATABLE; do
    say "alembic upgrade head -- $svc"
    ( export_vault_identity "$svc"; cd "$BACKEND_DIR/$svc" && ./.venv/bin/alembic upgrade head )
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
  # Something outside dev.sh (another project, a stale process) holding the port
  # would make the new process die on bind while the old one keeps answering
  # its requests -- the frontend would then talk to the wrong app.  Refuse,
  # name the holder, and let cmd_services report it once the rest is up.
  local port; port="$(cmd_port "$cmd")"
  if [ -n "$port" ] && port_busy "$port"; then
    printf '\033[1;31m  !! %s not started: port %s is held by pid %s\033[0m\n' \
      "$name" "$port" "$(port_owner "$port")" >&2
    PORT_CONFLICTS="${PORT_CONFLICTS:-} $name:$port"
    return
  fi
  # Each runtime has its own "are the deps installed?" marker.
  case "$cmd" in
    .venv/bin/*)
      [ -x "$BACKEND_DIR/$dir/.venv/bin/python" ] || die "$dir has no .venv -- run 'uv sync' in it first" ;;
    npm*|env*npm\ run*)
      require_bin npm
      [ -d "$BACKEND_DIR/$dir/node_modules" ] || die "$dir has no node_modules -- run 'npm install' in it first" ;;
    env*node*|node*)
      require_bin node
      [ -f "$BACKEND_DIR/$dir/dist/mcp-server/index.cjs" ] || \
        die "$dir is not built -- run 'npm install && npm run build' in it first" ;;
  esac
  local reload=""
  [ "${RELOAD:-0}" = "1" ] && case "$cmd" in *uvicorn*) reload=" --reload";; esac
  (
    case "$cmd" in
      .venv/bin/*) export_vault_identity "$dir" ;;
      *start:local*) export_vault_secrets_for_node "$(vault_identity_for_dir "$dir")" ;;
    esac
    cd "$BACKEND_DIR/$dir" && exec nohup $cmd$reload >> "$(log_file "$name")" 2>&1
  ) &
  echo $! > "$(pid_file "$name")"
  echo "  started $name (pid $!)"
}

STOPPED_PID=""
stop_one() {
  local name="$1" pf; pf="$(pid_file "$name")"
  STOPPED_PID=""
  if proc_running "$name"; then
    local pid; pid="$(cat "$pf")"
    STOPPED_PID="$pid"
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
      PORT_CONFLICTS=""
      while IFS='|' read -r name dir cmd; do
        [ -n "$name" ] || continue
        [ -n "${2:-}" ] && [ "$2" != "$name" ] && continue
        start_one "$name" "$dir" "$cmd"
      done < <(processes)
      # Everything that could start has; now fail so `up` never looks healthy.
      [ -z "$PORT_CONFLICTS" ] || \
        die "not started, port already in use:$PORT_CONFLICTS -- stop the holder (see above) and re-run"
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
  say "gateway docs http://127.0.0.1:8000/docs  |  rabbitmq UI http://127.0.0.1:15672  |  S3 $S3_LOCAL_ENDPOINT"
  say "admin-js on http://localhost:$ADMIN_JS_PORT/admin"
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

# SIGTERM only asks: uvicorn drains for a second or two before it lets go of
# its port. A restart that starts the new process meanwhile finds the port
# held and gives up, so wait for the old one (then kill it if it hangs).
wait_for_exit() {
  local name="$1" pid="$2" waited=0 limit="${STOP_TIMEOUT:-15}"
  [ -n "$pid" ] || return 0
  while kill -0 "$pid" 2>/dev/null && [ "$waited" -lt "$limit" ]; do
    sleep 1; waited=$((waited + 1))
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -KILL -"$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
    echo "  killed $name (still running after ${limit}s)"
  fi
}

cmd_restart() {
  [ -n "${1:-}" ] || die "restart: name required"
  service_env
  set -m
  stop_one "$1"
  wait_for_exit "$1" "$STOPPED_PID"
  PORT_CONFLICTS=""
  while IFS='|' read -r name dir cmd; do
    [ "$name" = "$1" ] && start_one "$name" "$dir" "$cmd"
  done < <(processes)
  [ -z "$PORT_CONFLICTS" ] || die "$1 not started, port already in use -- stop the holder (see above) and re-run"
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
      (export_vault_identity order_service; cd "$BACKEND_DIR/order_service" && \
        PYTHONPATH="$BACKEND_DIR" .venv/bin/python -m shared.messaging.dead_letter_replay "$@")
      ;;
    *) die "dlq: list | replay <queue> [--to <queue>] [--limit N]" ;;
  esac
}

# CJ sandbox orders never ship for real: this moves one to shipped/delivered
# through CJ's sandbox API and runs a tracking poll, so the saga, the customer
# emails and returns can be tested end to end.  Refuses real orders.
cmd_cj_sandbox() {
  service_env
  (export_vault_identity supplier_service; cd "$BACKEND_DIR/supplier_service" && .venv/bin/python -m tools.cj_sandbox "$@")
}

# CJ's STOCK webhook: CJ pushes stock changes to a public HTTPS address, so
# locally a cloudflared quick tunnel (no account, a new URL every run) gives
# the gateway one.  `tunnel` starts it and registers its URL with CJ; the
# rest runs tools/cj_webhook.py with supplier-service's Vault identity.
cj_tunnel_pid_file="$RUN_DIR/cj-tunnel.pid"
cj_tunnel_url_file="$RUN_DIR/cj-tunnel.url"
cj_tunnel_log="$LOG_DIR/cj-tunnel.log"
cj_tunnel_running() { [ -f "$cj_tunnel_pid_file" ] && kill -0 "$(cat "$cj_tunnel_pid_file")" 2>/dev/null; }

cj_webhook_tool() {
  (export_vault_identity supplier_service; cd "$BACKEND_DIR/supplier_service" && .venv/bin/python -m tools.cj_webhook "$@")
}

cmd_cj_webhook() {
  service_env
  local action="${1:-}"; shift || true
  case "$action" in
    tunnel)
      require_bin cloudflared
      mkdir -p "$RUN_DIR" "$LOG_DIR"
      if ! cj_tunnel_running; then
        : > "$cj_tunnel_log"
        # The gateway checks the Host header against its allowlist, so the
        # tunnel presents the local address rather than the trycloudflare one.
        nohup cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:8000" \
          --http-host-header "127.0.0.1:8000" >>"$cj_tunnel_log" 2>&1 &
        echo $! > "$cj_tunnel_pid_file"
        local url="" i
        for i in $(seq 1 30); do
          url="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$cj_tunnel_log" | head -1 || true)"
          [ -n "$url" ] && break
          sleep 1
        done
        [ -n "$url" ] || die "cloudflared gave no URL in 30s; see $cj_tunnel_log"
        echo "$url" > "$cj_tunnel_url_file"
        say "cj tunnel up: $url"
        # A fresh quick-tunnel hostname takes a few seconds to resolve.
        sleep 5
      fi
      cj_webhook_tool enable "$(cat "$cj_tunnel_url_file")"
      ;;
    tunnel-stop)
      if [ -f "$cj_tunnel_url_file" ]; then
        cj_webhook_tool disable "$(cat "$cj_tunnel_url_file")" || warn "CJ did not accept the cancel"
      fi
      if cj_tunnel_running; then kill "$(cat "$cj_tunnel_pid_file")"; say "cj tunnel stopped"; fi
      rm -f "$cj_tunnel_pid_file" "$cj_tunnel_url_file"
      ;;
    store-open-id)
      # Straight from CJ into Vault: the value is never printed or put on a
      # command line (vault reads it from stdin), so it shows in no log or ps.
      # The tool writes the openId into a private file (never stdout, where
      # its log lines go); it is checked, piped into Vault and deleted.
      local secret_file
      secret_file="$(umask 077; mktemp "$RUN_DIR/cj-open-id.XXXXXX")"
      # Expanded now: the trap runs at exit, after this function's locals are gone.
      # shellcheck disable=SC2064
      trap "rm -f '$secret_file'" EXIT
      cj_webhook_tool open-id --to "$secret_file" || die "could not read the openId from CJ"
      grep -qE '^[0-9]{1,20}$' "$secret_file" || die "what CJ returned is not a numeric openId; nothing stored"
      vault_op kv patch "secret/$VAULT_PREFIX/supplier-service" \
        CJ_DROPSHIPPING_OPEN_ID=- <"$secret_file" >/dev/null
      rm -f "$secret_file"
      say "CJ_DROPSHIPPING_OPEN_ID stored in Vault; restart supplier-service to load it"
      ;;
    enable|disable|subscribe|status) cj_webhook_tool "$action" "$@" ;;
    *) die "cj-webhook: tunnel | tunnel-stop | store-open-id | enable <url> | disable <url> | subscribe | status" ;;
  esac
}

# A service's test suite, with that service's Vault identity: its settings
# (database password included) come from Vault exactly as when it runs.
cmd_test() {
  [ -n "${1:-}" ] || die "test: service dir required (e.g. order_service)"
  local svc="$1"; shift
  [ -d "$BACKEND_DIR/$svc" ] || die "test: no service dir $svc"
  service_env
  # The suites' own buckets, like their own *_test_db databases.
  export AWS_S3_CATALOGUE_BUCKET="$S3_CATALOGUE_BUCKET-test" AWS_S3_PRIVATE_BUCKET="$S3_PRIVATE_BUCKET-test"
  export AWS_S3_CATALOGUE_PUBLIC_BASE_URL="$S3_LOCAL_ENDPOINT/$S3_CATALOGUE_BUCKET-test"
  (export_vault_identity "$svc"; cd "$BACKEND_DIR/$svc" && uv run pytest tests/ "$@")
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
  cj-sandbox) shift; cmd_cj_sandbox "$@" ;;
  cj-webhook) shift; cmd_cj_webhook "$@" ;;
  vault)    shift; cmd_vault "$@" ;;
  storage)  shift; cmd_storage "$@" ;;
  images)   shift; cmd_images "$@" ;;
  test)     shift; cmd_test "$@" ;;
  *) sed -n '2,49p' "${BASH_SOURCE[0]}" | sed -E 's/^#[[:space:]]?//'; exit 1 ;;
esac
