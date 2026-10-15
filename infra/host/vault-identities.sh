#!/usr/bin/env bash
# Phase 5: one Vault policy, AppRole and credential pair per service, on the
# host, as root. Same model as local/dev.sh vault_bootstrap: a read-only policy
# on the service's own path plus shared-infra, and a secret id that never
# expires (rotate by deleting its file and running this again).
#
# Each container mounts only its own directory, read-only, at /run/vault:
#   /etc/ecommerce/vault/<identity>/role-id
#   /etc/ecommerce/vault/<identity>/secret-id
# The directories are 0755 and the files 0644 so the container's user can read
# them; only root can write them, and no other host user is expected to exist.
#
# Idempotent. Needs /root/vault-init.json (the root token) on the host. Run
# after bootstrap-host.sh, before the first deploy.
set -euo pipefail

PREFIX="ecommerce"
CREDS="/etc/ecommerce/vault"
INIT="/root/vault-init.json"
IDENTITIES="api-gateway user-service product-service supplier-service order-service payment-service cart-service wishlist-service shipping-service notification-service"

[ -s "$INIT" ] || { echo "error: $INIT is missing (Vault must be initialised on this host)" >&2; exit 1; }
export VAULT_ADDR="http://127.0.0.1:8200"
VAULT_TOKEN="$(jq -r '.root_token' "$INIT")"
export VAULT_TOKEN

# KV v2 and AppRole, once.
vault secrets list -format=json | jq -e 'has("secret/")' >/dev/null \
    || vault secrets enable -path=secret -version=2 kv >/dev/null
vault auth list -format=json | jq -e 'has("approle/")' >/dev/null \
    || vault auth enable approle >/dev/null

# Paths that must exist even when empty: a missing path makes the service
# refuse to start. The owner fills them by import (phase 6).
ensure_path() {
    vault kv metadata get "secret/$PREFIX/$1" >/dev/null 2>&1 \
        || printf '{"data": {}}' | vault write "secret/data/$PREFIX/$1" - >/dev/null
}
ensure_path shared-infra

for name in $IDENTITIES; do
    printf 'path "secret/data/%s/%s" { capabilities = ["read"] }\npath "secret/data/%s/shared-infra" { capabilities = ["read"] }\n' \
        "$PREFIX" "$name" "$PREFIX" | vault policy write "$name" - >/dev/null
    vault write "auth/approle/role/$name" token_policies="$name" token_ttl=1h token_max_ttl=24h secret_id_ttl=0 >/dev/null
    ensure_path "$name"

    install -d -m 0755 "$CREDS/$name"
    vault read -field=role_id "auth/approle/role/$name/role-id" > "$CREDS/$name/role-id"
    # A secret id is issued once and reused; delete the file to rotate it.
    if [ ! -s "$CREDS/$name/secret-id" ]; then
        vault write -f -field=secret_id "auth/approle/role/$name/secret-id" > "$CREDS/$name/secret-id"
    fi
    chmod 0644 "$CREDS/$name/role-id" "$CREDS/$name/secret-id"
    echo "ok $name"
done
echo "vault identities ready under $CREDS"
