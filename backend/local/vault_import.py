"""One-time move of the secrets in backend's config file into Vault.

    ./local/dev.sh vault import             # write to Vault, then remove them from the file
    ./local/dev.sh vault import --dry-run   # show what would move; change nothing
    ./local/dev.sh vault import --keep-file # write to Vault, leave the file as it is

Run by you, on your machine: it reads the config file and writes each secret
to the Vault path of the service that uses it (secret/<prefix>/<service>).
It prints key names only, never a value. Each path is read back and compared
before anything is removed from the file, and the file is rewritten entry by
entry with python-dotenv's own parser, so multi-line values (PEM keys) and
every other line are preserved exactly.

VAULT_ADDR and VAULT_TOKEN (the operator's root token) come from dev.sh.
"""

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from io import StringIO
from pathlib import Path

from dotenv.parser import Binding, parse_stream

# Where each secret goes: the services that read it, and nothing else.
SECRET_PATHS: dict[str, tuple[str, ...]] = {
    # Every process connects to these until Vault issues per-service database users.
    "shared-infra": ("POSTGRES_PASSWORD", "REDIS_PASSWORD", "RABBITMQ_PASSWORD"),
    "api-gateway": ("GATEWAY_ASSERTION_PRIVATE_KEY",),
    "user-service": ("USER_TOKEN_PRIVATE_KEY",),
    # SECRET_KEY: only the artwork-signing fallback reads it, in these two services.
    "product-service": ("OPENROUTER_API_KEY", "ARTWORK_SIGNING_SECRET", "SECRET_KEY"),
    "order-service": ("ORDER_SERVICE_ASSERTION_PRIVATE_KEY", "ARTWORK_SIGNING_SECRET", "SECRET_KEY"),
    "supplier-service": ("SUPPLIER_SERVICE_ASSERTION_PRIVATE_KEY", "CJ_DROPSHIPPING_API_KEY", "CJ_DROPSHIPPING_OPEN_ID"),
    "payment-service": ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"),
    "notification-service": ("MAIL_PASSWORD",),
    "admin-js": ("COOKIE_SECRET",),
    # Read by no running service (compose's pgAdmin; an unused AdminJS token):
    # kept in Vault so the file holds no secrets, readable only with the root token.
    "tooling": ("PGADMIN_DEFAULT_PASSWORD", "ADMINJS_SERVICE_TOKEN"),
    # The compose observability stack: Alertmanager's Telegram alerts and
    # Grafana's own signing key. No local process reads them; root token only.
    "observability": ("TELEGRAM_BOT_TOKEN", "GRAFANA_SECRET_KEY"),
}

# Old names still accepted by Settings: imported under the current name.
RENAMED = {"STRIPE_TEST_SECRET_KEY": "STRIPE_SECRET_KEY"}

# Names that look secret but are not, for the "left in the file" warning.
NOT_SECRET = re.compile(r"(_PUBLIC_KEY|^TOKEN_|_TOKEN_(TIME|EXPIRY)|_URL$|^SECRET_ROLE$|_PASSWORD_HASH_)")
LOOKS_SECRET = re.compile(r"(PASSWORD|SECRET|PRIVATE|_KEY$|_TOKEN$|_API_KEY)")


class Vault:
    def __init__(self, address: str, token: str) -> None:
        self._address = address.rstrip("/")
        self._token = token

    def read(self, path: str) -> dict[str, str]:
        try:
            document = self._call("GET", f"/v1/secret/data/{path}")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return {}
            raise
        return {str(k): str(v) for k, v in document["data"]["data"].items()}

    def write(self, path: str, data: dict[str, str]) -> None:
        self._call("POST", f"/v1/secret/data/{path}", {"data": data})

    def _call(self, method: str, path: str, body: dict[str, dict[str, str]] | None = None) -> dict:
        request = urllib.request.Request(
            f"{self._address}{path}",
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"X-Vault-Token": self._token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = response.read()
        return json.loads(payload) if payload else {}


def plan(values: dict[str, str]) -> tuple[dict[str, dict[str, str]], set[str]]:
    """Per path, the secrets found in the file; and every file key that will be moved."""
    for old, new in RENAMED.items():
        if old in values and new not in values:
            values = {**values, new: values[old]}
    per_path: dict[str, dict[str, str]] = {}
    moved: set[str] = set()
    for path, keys in SECRET_PATHS.items():
        found = {key: values[key] for key in keys if values.get(key)}
        if found:
            per_path[path] = found
            moved.update(found)
    # The old name goes too, once its value lives on under the new one.
    moved.update(old for old, new in RENAMED.items() if old in values and new in moved)
    return per_path, moved


def rewrite_without(env_file: Path, bindings: list[Binding], moved: set[str]) -> None:
    kept = "".join(b.original.string for b in bindings if b.key not in moved)
    mode = env_file.stat().st_mode & 0o777
    handle, temporary = tempfile.mkstemp(dir=env_file.parent, prefix=".import-")
    with os.fdopen(handle, "w") as out:
        out.write(kept)
    os.chmod(temporary, mode)
    os.replace(temporary, env_file)


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--prefix", default="ecommerce")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-file", action="store_true")
    args = parser.parse_args()

    text = args.env_file.read_text()
    bindings = list(parse_stream(StringIO(text)))
    broken = [b.original.line for b in bindings if b.error]
    if broken:
        print(f"Could not parse lines {broken} of {args.env_file}; fix them first.", file=sys.stderr)
        return 1
    values = {b.key: b.value for b in bindings if b.key and b.value is not None}
    per_path, moved = plan(values)

    for path, found in per_path.items():
        print(f"  {args.prefix}/{path}: {', '.join(sorted(found))}")
    missing = sorted({k for keys in SECRET_PATHS.values() for k in keys} - set(values) - set(RENAMED.values()))
    if missing:
        print(f"  not in the file (skipped): {', '.join(missing)}")
    left = sorted(k for k in values if k not in moved and LOOKS_SECRET.search(k) and not NOT_SECRET.search(k))
    if left:
        print(f"  WARNING, these look secret but have no Vault path, so they stay in the file: {', '.join(left)}")
    if args.dry_run:
        print("Dry run: nothing written, the file is unchanged.")
        return 0

    vault = Vault(os.environ["VAULT_ADDR"], os.environ["VAULT_TOKEN"])
    for path, found in per_path.items():
        full = f"{args.prefix}/{path}"
        merged = {**vault.read(full), **found}
        vault.write(full, merged)
        if vault.read(full) != merged:
            print(f"Read-back of {full} did not match; the file is unchanged.", file=sys.stderr)
            return 1
    print(f"Wrote {len(moved)} secrets to Vault; each path read back and matched.")

    if args.keep_file:
        print("--keep-file: the file still holds them.")
        return 0
    rewrite_without(args.env_file, bindings, moved)
    print(f"Removed them from {args.env_file}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
