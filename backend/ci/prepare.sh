#!/usr/bin/env bash
# Bring up what one service's test suite needs on a CI runner, and hand the
# suite its settings through $GITHUB_ENV.
#
#   backend/ci/prepare.sh <service_dir>        e.g. backend/ci/prepare.sh order_service
#
# 1. Generates this run's passwords (Postgres, Redis, RabbitMQ). They live
#    only in this job's environment and are masked in the log.
# 2. Starts a throwaway Vault dev server just long enough for
#    local/s3_local.py to generate the S3 keys and render SeaweedFS's
#    identities file -- the same code dev.sh runs, so CI tests the same
#    per-service S3 scoping. The suites themselves never see Vault: with no
#    VAULT_ADDR their settings read the environment, as in production builds.
# 3. Starts Postgres, Redis, RabbitMQ and SeaweedFS (ci/docker-compose.ci.yml)
#    and waits until each is healthy, then creates the test buckets and the
#    service's own Postgres login (db/service-role.sql, as dev.sh does), so
#    the suite and its migrations run without superuser rights.
# 4. Writes ci/test-settings.conf, the passwords, throwaway Ed25519 signing
#    keys (an app reads its verifying key at startup; the suites sign with
#    their own) and, for product-, order- and user-service, that service's own S3
#    key pair to $GITHUB_ENV.
#
# Off GitHub, point GITHUB_ENV at a file and source it afterwards; the
# CI_*_PORT variables move the containers off the ports a local stack uses.
set -euo pipefail

service="${1:?usage: prepare.sh <service_dir>}"
CI_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$CI_DIR")"
[ -f "$BACKEND_DIR/$service/settings.py" ] || { echo "no service $service" >&2; exit 2; }
: "${GITHUB_ENV:?GITHUB_ENV must name the file the settings are written to}"

RUN_DIR="${RUNNER_TEMP:-$CI_DIR/.run}/ecommerce-ci"
mkdir -p "$RUN_DIR"
chmod 700 "$RUN_DIR"

S3_ENDPOINT="http://127.0.0.1:${CI_S3_PORT:-8333}"
VAULT_PORT="${CI_VAULT_PORT:-8200}"
export VAULT_ADDR="http://127.0.0.1:$VAULT_PORT"

# Hide a value in the job log. On GitHub, the runner reads the command from
# this script's stdout -- never call it inside $(...), where it would be
# captured into a value instead.
mask() { if [ "${GITHUB_ACTIONS:-}" = "true" ]; then echo "::add-mask::$1"; fi; }

# A value for this run only, set into the named variable and masked.
new_secret() {
  printf -v "$1" '%s' "$(openssl rand -hex 24)"
  mask "${!1}"
}

publish() { printf '%s=%s\n' "$1" "$2" >> "$GITHUB_ENV"; }

# A fresh Ed25519 pair as the one-line base64 bodies Ed25519KeyLoader accepts
# (PKCS#8 private, SubjectPublicKeyInfo public). The private half is masked.
publish_key_pair() {
  local pem private public
  pem="$(openssl genpkey -algorithm ed25519)"
  private="$(printf '%s\n' "$pem" | grep -v -- '-----' | tr -d '\n')"
  public="$(printf '%s\n' "$pem" | openssl pkey -pubout | grep -v -- '-----' | tr -d '\n')"
  mask "$private"
  publish "$1_PRIVATE_KEY" "$private"
  publish "$1_PUBLIC_KEY" "$public"
}

s3_local() {
  # boto3 is all it needs; -I keeps the runner's own site-packages out.
  S3_LOCAL_ENDPOINT="$S3_ENDPOINT" \
    uv run --quiet --no-project --with boto3 python -I "$BACKEND_DIR/local/s3_local.py" "$@"
}

vault_field() {
  curl -fsS -H "X-Vault-Token: $VAULT_TOKEN" "$VAULT_ADDR/v1/secret/data/ecommerce/$1" |
    python3 -c "import json, sys; print(json.load(sys.stdin)['data']['data']['$2'])"
}

echo "== passwords for this run"
new_secret CI_POSTGRES_PASSWORD
new_secret CI_REDIS_PASSWORD
new_secret CI_RABBITMQ_PASSWORD
new_secret VAULT_TOKEN
export CI_POSTGRES_PASSWORD CI_REDIS_PASSWORD CI_RABBITMQ_PASSWORD VAULT_TOKEN

echo "== S3 identities (throwaway Vault dev server)"
vault server -dev -dev-root-token-id="$VAULT_TOKEN" -dev-listen-address="127.0.0.1:$VAULT_PORT" \
  > "$RUN_DIR/vault.log" 2>&1 &
vault_pid=$!
trap 'kill "$vault_pid" 2>/dev/null || true' EXIT
for _ in $(seq 1 50); do
  curl -fsS "$VAULT_ADDR/v1/sys/health" > /dev/null 2>&1 && break
  sleep 0.2
done
export CI_SEAWEEDFS_CONFIG="$RUN_DIR/s3.json"
rendered=0
s3_local bootstrap --config "$CI_SEAWEEDFS_CONFIG" || rendered=$?
[ "$rendered" = 0 ] || [ "$rendered" = 10 ] || { echo "could not render the S3 identities" >&2; exit 1; }
# SeaweedFS reads the file as its own user; the keys in it are this run's only.
chmod 644 "$CI_SEAWEEDFS_CONFIG"
export CI_SEAWEEDFS_SSE_KEK
CI_SEAWEEDFS_SSE_KEK="$(vault_field tooling SEAWEEDFS_SSE_KEK)"
mask "$CI_SEAWEEDFS_SSE_KEK"

echo "== backing services"
docker compose -f "$CI_DIR/docker-compose.ci.yml" up -d --wait --quiet-pull

echo "== test buckets"
for attempt in $(seq 1 30); do
  s3_local buckets > /dev/null 2>&1 && break
  [ "$attempt" = 30 ] && { s3_local buckets; exit 1; }
  sleep 1
done

echo "== postgres login for $service"
# Every service with a database gets a login of its own that owns it and its
# test database; the gateway has none.
db_login_password=""
if grep -q "^CREATE DATABASE ${service}_db;" "$BACKEND_DIR/db/init-databases.sql"; then
  new_secret db_login_password
  for db in "${service}_db" "${service}_test_db"; do
    # The password reaches psql on stdin (\set), not on the command line.
    printf '\\set role %s\n\\set password %s\n' "$service" "$db_login_password" \
      | cat - "$BACKEND_DIR/db/service-role.sql" \
      | docker compose -f "$CI_DIR/docker-compose.ci.yml" exec -T postgres psql -U postgres -d "$db" -q -X > /dev/null
  done
fi

echo "== settings for $service"
grep -Ev '^[[:space:]]*(#|$)' "$CI_DIR/test-settings.conf" >> "$GITHUB_ENV"
if [ -n "$db_login_password" ]; then
  # After test-settings.conf, so they replace its POSTGRES_USER=postgres.
  publish POSTGRES_USER "$service"
  publish POSTGRES_PASSWORD "$db_login_password"
fi
publish REDIS_PASSWORD "$CI_REDIS_PASSWORD"
publish RABBITMQ_PASSWORD "$CI_RABBITMQ_PASSWORD"
for role in USER_TOKEN GATEWAY_ASSERTION ORDER_SERVICE_ASSERTION SUPPLIER_SERVICE_ASSERTION; do
  publish_key_pair "$role"
done
new_secret artwork_signing_secret
publish ARTWORK_SIGNING_SECRET "$artwork_signing_secret"
# notification-service builds its mail connection at import; nothing is sent.
new_secret mail_password
publish MAIL_PASSWORD "$mail_password"
case "$service" in
  product_service) s3_identity=product-service ;;
  order_service) s3_identity=order-service ;;
  user_service) s3_identity=user-service ;;
  *) s3_identity="" ;;
esac
if [ -n "$s3_identity" ]; then
  for key in AWS_S3_ACCESS_KEY_ID AWS_S3_SECRET_ACCESS_KEY; do
    value="$(vault_field "$s3_identity" "$key")"
    mask "$value"
    publish "$key" "$value"
  done
fi
echo "ready"
