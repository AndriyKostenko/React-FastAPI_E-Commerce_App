#!/usr/bin/env bash
# Phase 4: bootstrap the storefront host. Run as root on the host, through
# Session Manager. Idempotent: safe to run again after a change.
#
# It does, in order:
#   - a 4 GB swap file (the host is 8 GB and the memory budget relies on it);
#   - security-only unattended updates;
#   - Docker (live-restore, bounded logs) and the Compose v2 plugin, checksum-verified;
#   - Vault as a systemd service: integrated storage, AWS KMS auto-unseal, plain
#     HTTP reachable only from the Docker bridges (firewall unit below);
#   - the backup scripts: pg_dump of the nine production databases every 6 h,
#     a Vault raft snapshot nightly, and a restore drill monthly.
#
# Not here: the compose stack (phase 5), the owner's secret import and the
# service AppRoles (phase 6). The Postgres backup timer is installed but left
# disabled until the database container runs.
set -euo pipefail

VAULT_VERSION="${VAULT_VERSION:-2.1.2}"
COMPOSE_VERSION="${COMPOSE_VERSION:-v5.5.0}"
ACCOUNT_ID="${ACCOUNT_ID:-008897528825}"
REGION="${REGION:-ca-central-1}"
BACKUP_BUCKET="${BACKUP_BUCKET:-ecommerce-backups-${ACCOUNT_ID}}"
# Terraform outputs kms_key_arns.data / kms_key_arns.vault_unseal (not secrets).
DATA_KMS_KEY_ARN="${DATA_KMS_KEY_ARN:-arn:aws:kms:ca-central-1:008897528825:key/1f932846-cee9-43eb-9517-9d81a30e8578}"
UNSEAL_KMS_KEY_ARN="${UNSEAL_KMS_KEY_ARN:-arn:aws:kms:ca-central-1:008897528825:key/db66282e-f7a8-4b69-a2c1-cae809a17e36}"

step() { printf '\n== %s\n' "$1"; }
die() { printf 'error: %s\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------------------
step "swap"
if ! swapon --show=NAME --noheadings | grep -qx /swapfile; then
    [ -f /swapfile ] || fallocate -l 4G /swapfile
    chmod 0600 /swapfile
    mkswap /swapfile >/dev/null
    swapon /swapfile
fi
grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
printf 'vm.swappiness = 10\n' > /etc/sysctl.d/90-ecommerce.conf
sysctl -q -p /etc/sysctl.d/90-ecommerce.conf

# ---------------------------------------------------------------------------
step "packages and security updates"
dnf -y -q install docker dnf-automatic unzip jq iptables-nft
# Security fixes apply themselves. Nothing reboots on its own: a reboot is
# done by hand, after checking the stack comes back.
sed -i -e 's/^#\?upgrade_type = .*/upgrade_type = security/' \
       -e 's/^#\?apply_updates = .*/apply_updates = yes/' /etc/dnf/automatic.conf
systemctl enable --now dnf-automatic-install.timer

# ---------------------------------------------------------------------------
step "docker"
install -d -m 0755 /etc/docker
# no-new-privileges is deliberately not set: the taskiq workers start as root
# and drop to their user with gosu, which needs setuid to work.
cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" },
  "live-restore": true
}
EOF
systemctl enable docker
systemctl restart docker

COMPOSE_PLUGIN=/usr/local/lib/docker/cli-plugins/docker-compose
if ! "$COMPOSE_PLUGIN" version 2>/dev/null | grep -q "${COMPOSE_VERSION#v}"; then
    tmp="$(mktemp -d)"
    base="https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}"
    curl -fsSL -o "$tmp/docker-compose" "$base/docker-compose-linux-aarch64"
    curl -fsSL -o "$tmp/sha256" "$base/docker-compose-linux-aarch64.sha256"
    (cd "$tmp" && echo "$(cut -d' ' -f1 sha256)  docker-compose" | sha256sum -c -)
    install -D -m 0755 "$tmp/docker-compose" "$COMPOSE_PLUGIN"
    rm -rf "$tmp"
fi
"$COMPOSE_PLUGIN" version

# ---------------------------------------------------------------------------
step "vault binary"
if ! vault version 2>/dev/null | grep -q "Vault v${VAULT_VERSION}"; then
    tmp="$(mktemp -d)"
    base="https://releases.hashicorp.com/vault/${VAULT_VERSION}"
    zip="vault_${VAULT_VERSION}_linux_arm64.zip"
    curl -fsSL -o "$tmp/$zip" "$base/$zip"
    curl -fsSL -o "$tmp/SHA256SUMS" "$base/vault_${VAULT_VERSION}_SHA256SUMS"
    (cd "$tmp" && grep " ${zip}\$" SHA256SUMS | sha256sum -c -)
    unzip -q "$tmp/$zip" -d "$tmp"
    install -m 0755 "$tmp/vault" /usr/local/bin/vault
    rm -rf "$tmp"
fi
vault version

# ---------------------------------------------------------------------------
step "vault configuration and service"
id vault >/dev/null 2>&1 || useradd --system --home-dir /var/lib/vault --shell /sbin/nologin vault
install -d -m 0750 -o vault -g vault /var/lib/vault /var/lib/vault/data
install -d -m 0750 -o root -g vault /etc/vault.d

cat > /etc/vault.d/vault.hcl <<EOF
ui           = false
disable_mlock = true

storage "raft" {
  path    = "/var/lib/vault/data"
  node_id = "vault-1"
}

# Plain HTTP. The listener answers on every interface, but the vault-firewall
# unit drops anything on port 8200 that does not come from the Docker bridges
# (or loopback), and the security group never opens it.
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}

seal "awskms" {
  region     = "${REGION}"
  kms_key_id = "${UNSEAL_KMS_KEY_ARN}"
}

api_addr     = "http://127.0.0.1:8200"
cluster_addr = "http://127.0.0.1:8201"
EOF
chown root:vault /etc/vault.d/vault.hcl
chmod 0640 /etc/vault.d/vault.hcl

cat > /usr/local/sbin/ecommerce-vault-firewall <<'EOF'
#!/usr/bin/env bash
# Port 8200 answers only the loopback and the Docker bridge ranges (172.16/12).
# Each rule is added once; the accept rules come before the drop.
set -euo pipefail
ensure() { iptables -C "$@" 2>/dev/null || iptables -A "$@"; }
ensure INPUT -p tcp --dport 8200 -s 127.0.0.0/8 -j ACCEPT
ensure INPUT -p tcp --dport 8200 -s 172.16.0.0/12 -j ACCEPT
ensure INPUT -p tcp --dport 8200 -j DROP
EOF
chmod 0755 /usr/local/sbin/ecommerce-vault-firewall

cat > /etc/systemd/system/vault-firewall.service <<'EOF'
[Unit]
Description=Restrict Vault port 8200 to loopback and Docker bridges
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/ecommerce-vault-firewall

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/vault.service <<'EOF'
[Unit]
Description=HashiCorp Vault (storefront secrets)
Wants=network-online.target
After=network-online.target vault-firewall.service
Requires=vault-firewall.service

[Service]
User=vault
Group=vault
ExecStart=/usr/local/bin/vault server -config=/etc/vault.d/vault.hcl
Restart=on-failure
RestartSec=5
LimitNOFILE=65536
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths=/var/lib/vault

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now vault-firewall.service
systemctl enable --now vault.service

export VAULT_ADDR=http://127.0.0.1:8200
vault_status() { vault status -format=json 2>/dev/null || true; }
for _ in $(seq 1 60); do
    [ -n "$(vault_status)" ] && break
    sleep 2
done
[ -n "$(vault_status)" ] || die "vault did not answer on 127.0.0.1:8200"

# First time only: initialise. With awskms the unseal is automatic; the
# recovery keys and root token go to a file the owner moves off the host.
if [ "$(vault_status | jq -r '.initialized')" != "true" ]; then
    [ -e /root/vault-init.json ] && die "/root/vault-init.json exists but Vault is not initialised"
    vault operator init -recovery-shares=5 -recovery-threshold=3 -format=json > /root/vault-init.json
    chmod 0600 /root/vault-init.json
    echo "Vault initialised. Move /root/vault-init.json off this host, then delete it."
fi
for _ in $(seq 1 60); do
    [ "$(vault_status | jq -r '.sealed')" = "false" ] && break
    sleep 2
done
[ "$(vault_status | jq -r '.sealed')" = "false" ] || die "vault is still sealed (check the KMS key and the instance role)"

ROOT_TOKEN="$(jq -r '.root_token' /root/vault-init.json)"

# Snapshot token: may read a raft snapshot and nothing else. Created once.
VAULT_TOKEN="$ROOT_TOKEN" vault policy write backup-snapshot - <<'EOF'
path "sys/storage/raft/snapshot" {
  capabilities = ["read"]
}
EOF
install -d -m 0700 /etc/ecommerce
if [ ! -s /etc/ecommerce/vault-backup.token ]; then
    VAULT_TOKEN="$ROOT_TOKEN" vault token create -orphan -policy=backup-snapshot -period=720h -format=json \
        | jq -r '.auth.client_token' > /etc/ecommerce/vault-backup.token
    chmod 0600 /etc/ecommerce/vault-backup.token
fi
unset ROOT_TOKEN

# ---------------------------------------------------------------------------
step "backup and restore scripts"
cat > /usr/local/sbin/ecommerce-backup-postgres <<EOF
#!/usr/bin/env bash
# pg_dump of every production database into S3, one folder per run, with a
# MANIFEST written last: a run without one is incomplete and restores skip it.
#   PG_CONTAINER  container to dump (default: the compose "db" service)
#   PREFIX        S3 folder (default: postgres; the drill uses drill)
set -euo pipefail
BUCKET="\${BACKUP_BUCKET:-${BACKUP_BUCKET}}"
KEY="${DATA_KMS_KEY_ARN}"
PREFIX="\${PREFIX:-postgres}"
TS="\$(date -u +%Y%m%dT%H%M%SZ)"
DATABASES="user_service_db product_service_db notification_service_db order_service_db payment_service_db cart_service_db shipping_service_db wishlist_service_db supplier_service_db"

CONTAINER="\${PG_CONTAINER:-}"
if [ -z "\$CONTAINER" ]; then
    CONTAINER="\$(docker ps -q --filter label=com.docker.compose.service=db | head -n1)"
fi
[ -n "\$CONTAINER" ] || { echo "no running Postgres container" >&2; exit 1; }

for db in \$DATABASES; do
    echo "dumping \$db"
    docker exec -u postgres "\$CONTAINER" pg_dump -Fc -d "\$db" \\
        | aws s3 cp - "s3://\$BUCKET/\$PREFIX/\$TS/\$db.dump" --sse aws:kms --sse-kms-key-id "\$KEY" --only-show-errors
done
printf '%s\n' \$DATABASES | aws s3 cp - "s3://\$BUCKET/\$PREFIX/\$TS/MANIFEST" --sse aws:kms --sse-kms-key-id "\$KEY" --only-show-errors
echo "backup \$TS complete"
EOF
chmod 0755 /usr/local/sbin/ecommerce-backup-postgres

cat > /usr/local/sbin/ecommerce-backup-vault <<EOF
#!/usr/bin/env bash
# Raft snapshot of Vault into S3. Read-only token (backup-snapshot policy).
set -euo pipefail
BUCKET="\${BACKUP_BUCKET:-${BACKUP_BUCKET}}"
KEY="${DATA_KMS_KEY_ARN}"
TS="\$(date -u +%Y%m%dT%H%M%SZ)"
dir="\$(mktemp -d)"
trap 'rm -rf "\$dir"' EXIT
VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="\$(cat /etc/ecommerce/vault-backup.token)" \\
    vault operator raft snapshot save "\$dir/vault.snap"
aws s3 cp "\$dir/vault.snap" "s3://\$BUCKET/vault/\$TS.snap" --sse aws:kms --sse-kms-key-id "\$KEY" --only-show-errors
echo "vault snapshot \$TS complete"
EOF
chmod 0755 /usr/local/sbin/ecommerce-backup-vault

cat > /usr/local/sbin/ecommerce-restore-drill <<EOF
#!/usr/bin/env bash
# Restore the newest complete Postgres run into a scratch container and check
# it: each database must hold as many tables as its dump lists table data for.
# Nothing touches the live database.
set -euo pipefail
BUCKET="\${BACKUP_BUCKET:-${BACKUP_BUCKET}}"
PREFIX="\${PREFIX:-postgres}"
NAME="ecommerce-restore-drill"

run=""
for p in \$(aws s3 ls "s3://\$BUCKET/\$PREFIX/" | awk '{print \$2}' | sort -r); do
    if aws s3api head-object --bucket "\$BUCKET" --key "\$PREFIX/\${p}MANIFEST" >/dev/null 2>&1; then
        run="\$p"
        break
    fi
done
[ -n "\$run" ] || { echo "no complete backup run in \$PREFIX/" >&2; exit 1; }
echo "restoring \$PREFIX/\$run"
mapfile -t dbs < <(aws s3 cp "s3://\$BUCKET/\$PREFIX/\${run}MANIFEST" -)

work="\$(mktemp -d)"
docker rm -f "\$NAME" >/dev/null 2>&1 || true
docker run -d --name "\$NAME" -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16-alpine >/dev/null
trap 'docker rm -f "\$NAME" >/dev/null 2>&1 || true; rm -rf "\$work"' EXIT
until docker exec "\$NAME" pg_isready -q -U postgres 2>/dev/null; do sleep 1; done

failures=0
for db in "\${dbs[@]}"; do
    aws s3 cp "s3://\$BUCKET/\$PREFIX/\${run}\$db.dump" "\$work/\$db.dump" --only-show-errors
    docker cp "\$work/\$db.dump" "\$NAME:/tmp/\$db.dump"
    expected="\$(docker exec "\$NAME" pg_restore -l "/tmp/\$db.dump" | grep -c ' TABLE DATA ' || true)"
    docker exec "\$NAME" createdb -U postgres "\$db"
    docker exec "\$NAME" pg_restore -U postgres -d "\$db" --no-owner --exit-on-error "/tmp/\$db.dump"
    restored="\$(docker exec "\$NAME" psql -U postgres -d "\$db" -tAc \\
        "select count(*) from information_schema.tables where table_schema = 'public'")"
    if [ "\$expected" = "\$restored" ]; then
        echo "ok \$db: \$restored tables"
    else
        echo "MISMATCH \$db: dump lists \$expected table data entries, restored \$restored tables" >&2
        failures=\$((failures + 1))
    fi
done
[ "\$failures" -eq 0 ] || { echo "restore drill FAILED" >&2; exit 1; }
echo "restore drill passed for \$PREFIX/\$run"
EOF
chmod 0755 /usr/local/sbin/ecommerce-restore-drill

# ---------------------------------------------------------------------------
step "systemd timers (Postgres backups stay off until the database runs)"
cat > /etc/systemd/system/ecommerce-backup-postgres.service <<'EOF'
[Unit]
Description=Back up the production Postgres databases to S3
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/ecommerce-backup-postgres
EOF
cat > /etc/systemd/system/ecommerce-backup-postgres.timer <<'EOF'
[Unit]
Description=Postgres backup every 6 hours

[Timer]
OnCalendar=*-*-* 00,06,12,18:15:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
cat > /etc/systemd/system/ecommerce-backup-vault.service <<'EOF'
[Unit]
Description=Snapshot Vault to S3
After=vault.service
Requires=vault.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/ecommerce-backup-vault
EOF
cat > /etc/systemd/system/ecommerce-backup-vault.timer <<'EOF'
[Unit]
Description=Vault snapshot every night

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
cat > /etc/systemd/system/ecommerce-restore-drill.service <<'EOF'
[Unit]
Description=Restore the newest Postgres backup into a scratch container and check it
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/ecommerce-restore-drill
EOF
cat > /etc/systemd/system/ecommerce-restore-drill.timer <<'EOF'
[Unit]
Description=Monthly restore drill

[Timer]
OnCalendar=*-*-01 04:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now ecommerce-backup-vault.timer ecommerce-restore-drill.timer
systemctl disable --now ecommerce-backup-postgres.timer 2>/dev/null || true

step "done"
systemctl --no-pager --plain list-timers 'ecommerce-*' || true
echo "vault: $(vault_status | jq -r '"initialized=\(.initialized) sealed=\(.sealed)"')"
