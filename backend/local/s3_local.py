"""The local S3 server (SeaweedFS): its credentials, buckets and data.

    s3_local.py bootstrap --config <s3.json>   # keys in Vault, identities file
    s3_local.py buckets                        # create the two buckets if missing
    s3_local.py status                         # buckets and object counts
    s3_local.py import-local --media <dir> --evidence <dir>
                                               # copy local-disk images into the
                                               # private bucket, same keys

Run by dev.sh with the operator's root token (VAULT_ADDR, VAULT_TOKEN), on the
product-service venv's interpreter (it has boto3). Prints key and bucket names,
never a secret value.

Credentials: product-service and order-service each get an access key pair in
their own Vault path (AWS_S3_ACCESS_KEY_ID / AWS_S3_SECRET_ACCESS_KEY), which
Settings reads like any other secret; the server's admin pair and the key
that encrypts objects at rest (SSE-S3) go to the root-only ``tooling`` path.
Generated here once, never rotated by accident: existing values are kept.
"""

import argparse
import json
import os
import secrets
import string
import sys
import urllib.error
import urllib.request
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

PREFIX = os.environ.get("VAULT_KV_PREFIX", "ecommerce")
ENDPOINT = os.environ.get("S3_LOCAL_ENDPOINT", "http://127.0.0.1:8333")
CATALOGUE_BUCKET = os.environ.get("S3_CATALOGUE_BUCKET", "ecommerce-catalogue")
PRIVATE_BUCKET = os.environ.get("S3_PRIVATE_BUCKET", "ecommerce-private")
# The test suites' own pair (``dev.sh test`` points them here), so a test run
# never writes into the buckets the running app reads.
TEST_SUFFIX = "-test"

# Prefixes in the private bucket, one per owning service.
DESIGNS_PREFIX = "generated-designs"
EVIDENCE_PREFIX = "return-evidence"


def buckets() -> list[tuple[str, str]]:
    """(catalogue, private) for the app, then for the test suites."""
    return [(CATALOGUE_BUCKET, PRIVATE_BUCKET), (CATALOGUE_BUCKET + TEST_SUFFIX, PRIVATE_BUCKET + TEST_SUFFIX)]


def identities() -> dict[str, list[str]]:
    """What each service's key may do: its own bucket or prefix, nothing else
    (the same on the test pair)."""
    rights: dict[str, list[str]] = {"product-service": [], "order-service": []}
    for catalogue, private in buckets():
        rights["product-service"] += [
            f"Read:{catalogue}",
            f"Write:{catalogue}",
            f"List:{catalogue}",
            f"Read:{private}/{DESIGNS_PREFIX}/*",
            f"Write:{private}/{DESIGNS_PREFIX}/*",
        ]
        rights["order-service"] += [
            f"Read:{private}/{EVIDENCE_PREFIX}/*",
            f"Write:{private}/{EVIDENCE_PREFIX}/*",
        ]
    return rights


class Vault:
    def __init__(self, address: str, token: str) -> None:
        self._address = address.rstrip("/")
        self._token = token

    def read(self, path: str) -> dict[str, str]:
        try:
            document = self._call("GET", f"/v1/secret/data/{PREFIX}/{path}")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return {}
            raise
        return {str(k): str(v) for k, v in document["data"]["data"].items()}

    def merge(self, path: str, values: dict[str, str]) -> None:
        """Add keys to a path, keeping what it already holds."""
        current = self.read(path)
        self._call("POST", f"/v1/secret/data/{PREFIX}/{path}", {"data": {**current, **values}})

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


def new_key_pair() -> dict[str, str]:
    alphabet = string.ascii_uppercase + string.digits
    return {
        "access": "AK" + "".join(secrets.choice(alphabet) for _ in range(18)),
        "secret": secrets.token_urlsafe(30),
    }


def ensure_secrets(vault: Vault) -> list[str]:
    """Generate whatever is missing; return the names of what was created."""
    created: list[str] = []
    for service in identities():
        held = vault.read(service)
        if not (held.get("AWS_S3_ACCESS_KEY_ID") and held.get("AWS_S3_SECRET_ACCESS_KEY")):
            pair = new_key_pair()
            vault.merge(service, {"AWS_S3_ACCESS_KEY_ID": pair["access"], "AWS_S3_SECRET_ACCESS_KEY": pair["secret"]})
            created.append(f"{service}: AWS_S3_ACCESS_KEY_ID, AWS_S3_SECRET_ACCESS_KEY")
    tooling = vault.read("tooling")
    missing: dict[str, str] = {}
    if not (tooling.get("SEAWEEDFS_ADMIN_ACCESS_KEY_ID") and tooling.get("SEAWEEDFS_ADMIN_SECRET_ACCESS_KEY")):
        pair = new_key_pair()
        missing |= {"SEAWEEDFS_ADMIN_ACCESS_KEY_ID": pair["access"], "SEAWEEDFS_ADMIN_SECRET_ACCESS_KEY": pair["secret"]}
    if not tooling.get("SEAWEEDFS_SSE_KEK"):
        # SeaweedFS refuses SSE-S3 writes without a key-encryption key: a
        # hex-encoded 256-bit key (WEED_S3_SSE_KEK).
        missing["SEAWEEDFS_SSE_KEK"] = secrets.token_hex(32)
    if missing:
        vault.merge("tooling", missing)
        created.append("tooling: " + ", ".join(sorted(missing)))
    return created


def render_config(vault: Vault) -> str:
    """The server's identities file: one identity per service, the admin, and
    anonymous read on the catalogue bucket only."""
    tooling = vault.read("tooling")
    config: dict[str, list[dict[str, object]]] = {"identities": []}
    for service, actions in identities().items():
        held = vault.read(service)
        config["identities"].append({
            "name": service,
            "credentials": [{"accessKey": held["AWS_S3_ACCESS_KEY_ID"], "secretKey": held["AWS_S3_SECRET_ACCESS_KEY"]}],
            "actions": actions,
        })
    config["identities"].append({
        "name": "storage-admin",
        "credentials": [{
            "accessKey": tooling["SEAWEEDFS_ADMIN_ACCESS_KEY_ID"],
            "secretKey": tooling["SEAWEEDFS_ADMIN_SECRET_ACCESS_KEY"],
        }],
        "actions": ["Admin", "Read", "List", "Tagging", "Write"],
    })
    # Anyone may GET a catalogue image; nothing else is anonymous.
    config["identities"].append({"name": "anonymous", "actions": [f"Read:{catalogue}" for catalogue, _ in buckets()]})
    return json.dumps(config, indent=2) + "\n"


def admin_client(vault: Vault):
    tooling = vault.read("tooling")
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id=tooling["SEAWEEDFS_ADMIN_ACCESS_KEY_ID"],
        aws_secret_access_key=tooling["SEAWEEDFS_ADMIN_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def cmd_bootstrap(vault: Vault, config_path: Path) -> int:
    for line in ensure_secrets(vault):
        print(f"  generated {line}")
    rendered = render_config(vault)
    previous = config_path.read_text() if config_path.exists() else None
    if rendered != previous:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        # Written private from the first byte: it holds every access key.
        fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(rendered)
        os.chmod(config_path, 0o600)
        print("  identities file updated")
        return 10  # tells dev.sh a running server must restart to read it
    return 0


def cmd_buckets(vault: Vault) -> int:
    client = admin_client(vault)
    for bucket in (name for pair in buckets() for name in pair):
        try:
            client.head_bucket(Bucket=bucket)
        except ClientError:
            client.create_bucket(Bucket=bucket)
            print(f"  created bucket {bucket}")
    return 0


def count(client, bucket: str, prefix: str = "") -> tuple[int, int]:
    objects = size = 0
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            objects += 1
            size += item["Size"]
    return objects, size


def cmd_status(vault: Vault) -> int:
    client = admin_client(vault)
    rows = [
        (CATALOGUE_BUCKET, "catalogue/cj/"),
        (CATALOGUE_BUCKET, "catalogue/uploads/"),
        (PRIVATE_BUCKET, f"{DESIGNS_PREFIX}/"),
        (PRIVATE_BUCKET, f"{EVIDENCE_PREFIX}/"),
    ]
    for bucket, prefix in rows:
        try:
            objects, size = count(client, bucket, prefix)
            print(f"  {bucket}/{prefix:<22} {objects:>6} objects  {size / 1_048_576:8.1f} MB")
        except ClientError as error:
            print(f"  {bucket}/{prefix:<22} unavailable ({error.response['Error'].get('Code')})")
    print("  identities: " + ", ".join([*identities(), "storage-admin", "anonymous (catalogue read)"]))
    return 0


def upload_tree(client, root: Path, bucket: str, key_prefix: str, content_type_for) -> tuple[int, int]:
    """Upload every file under ``root``; skip a key that already exists."""
    uploaded = skipped = 0
    if not root.is_dir():
        return uploaded, skipped
    for path in sorted(p for p in root.rglob("*") if p.is_file() and not p.name.startswith(".")):
        key = f"{key_prefix}/{path.relative_to(root).as_posix()}"
        try:
            client.head_object(Bucket=bucket, Key=key)
            skipped += 1
            continue
        except ClientError:
            pass
        client.put_object(
            Bucket=bucket, Key=key, Body=path.read_bytes(),
            ContentType=content_type_for(path), ServerSideEncryption="AES256",
        )
        uploaded += 1
    return uploaded, skipped


def guess_type(path: Path) -> str:
    return {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(
        path.suffix.lower(), "application/octet-stream"
    )


def cmd_import_local(vault: Vault, media: Path, evidence: Path) -> int:
    client = admin_client(vault)
    for label, root, prefix in (
        ("generated designs", media / DESIGNS_PREFIX, DESIGNS_PREFIX),
        ("return photos", evidence / EVIDENCE_PREFIX, EVIDENCE_PREFIX),
    ):
        uploaded, skipped = upload_tree(client, root, PRIVATE_BUCKET, prefix, guess_type)
        print(f"  {label}: {uploaded} uploaded, {skipped} already there ({root})")
    print("  the local files are left in place; delete them once you have checked the app reads from S3")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap").add_argument("--config", type=Path, required=True)
    commands.add_parser("buckets")
    commands.add_parser("status")
    importer = commands.add_parser("import-local")
    importer.add_argument("--media", type=Path, required=True)
    importer.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    vault = Vault(os.environ["VAULT_ADDR"], os.environ["VAULT_TOKEN"])
    if args.command == "bootstrap":
        return cmd_bootstrap(vault, args.config)
    if args.command == "buckets":
        return cmd_buckets(vault)
    if args.command == "status":
        return cmd_status(vault)
    return cmd_import_local(vault, args.media, args.evidence)


if __name__ == "__main__":
    sys.exit(main())
