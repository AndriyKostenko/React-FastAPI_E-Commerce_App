#!/usr/bin/env bash
# Phase 5: deploy one commit to the host, or roll back if it fails.
#
#   deploy.sh <git-sha>
#
# Run by the deploy workflow through SSM, from a checkout of the commit itself
# (so the deploy logic always matches the code it ships). Steps:
#   1. back up the databases, if the stack is already running; abort on failure;
#   2. pull the commit's images from ECR (immutable tags, one per SHA);
#   3. `compose up --wait`: migrations run in each service's entrypoint, and
#      --wait fails if any container with a healthcheck stays unhealthy;
#   4. on failure, bring the previous commit's images back the same way.
#
# A rollback never reverses a migration: the release rules (expand, then
# contract) keep the previous images compatible with the new schema.
set -euo pipefail

SHA="${1:?usage: deploy.sh <git-sha>}"
ACCOUNT_ID="${ACCOUNT_ID:-008897528825}"
REGION="${REGION:-ca-central-1}"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
REPO="/opt/ecommerce/src"
BACKEND="$REPO/backend"
STATE="/var/lib/ecommerce"
ENV_SOURCE="/etc/ecommerce/production.env"

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }

[ -s "$ENV_SOURCE" ] || { log "missing $ENV_SOURCE: the owner creates it (see the runbook)"; exit 1; }
install -d -m 0755 "$STATE"
prev="$(cat "$STATE/current" 2>/dev/null || true)"
log "deploying $SHA (currently: ${prev:-nothing})"

# Compose reads .env from the project directory; it holds only non-secret
# settings and the infrastructure passwords (secrets for the services are in Vault).
install -m 0600 "$ENV_SOURCE" "$BACKEND/.env"
aws ecr get-login-password --region "$REGION" \
    | docker login --username AWS --password-stdin "$REGISTRY" >/dev/null

cd "$BACKEND"
export IMAGE_REGISTRY="$REGISTRY"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

if docker ps -q --filter label=com.docker.compose.service=db | grep -q .; then
    log "backing up the databases before the change"
    /usr/local/sbin/ecommerce-backup-postgres
fi

# Returns non-zero (and does not exit) so the caller decides what to do.
bring_up() {
    export IMAGE_TAG="$1"
    "${COMPOSE[@]}" pull --quiet || return 1
    "${COMPOSE[@]}" up -d --no-build --remove-orphans --wait --wait-timeout 600
}

if bring_up "$SHA"; then
    echo "$SHA" > "$STATE/current"
    [ -n "$prev" ] && [ "$prev" != "$SHA" ] && echo "$prev" > "$STATE/previous"
    # The database backup timer runs from now on: the stack has a database.
    systemctl enable --now ecommerce-backup-postgres.timer >/dev/null
    log "deployed $SHA"
    exit 0
fi

log "deploy of $SHA failed its health gate"
if [ -n "$prev" ] && [ "$prev" != "$SHA" ]; then
    log "rolling back to $prev"
    if bring_up "$prev"; then
        log "rolled back to $prev"
    else
        log "ROLLBACK TO $prev FAILED: a person has to look at the host now"
    fi
else
    log "no previous deploy to roll back to"
fi
exit 1
