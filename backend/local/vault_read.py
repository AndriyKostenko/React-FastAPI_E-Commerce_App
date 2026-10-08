"""Print `export KEY=value` lines for one AppRole's Vault secrets (used by dev.sh for admin-js).

    python vault_read.py --address URL --role-id-file F --secret-id-file F [--keys A,B] PATH [PATH ...]

Signs in with the AppRole, reads each KV v2 path under `secret/`, and prints
shell-quoted exports, later paths winning on a clash. With --keys, only those
keys are exported: Vault grants a whole path, so a process that needs one key
of a shared path must not be handed the rest. Standard library only,
so it runs under any python3. Exits non-zero, naming the path, on any failure.
"""

import argparse
import json
import shlex
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _call(address: str, method: str, path: str, token: str | None = None, body: dict[str, str] | None = None) -> dict[str, object]:
    request = urllib.request.Request(
        f"{address}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"X-Vault-Token": token} if token else {},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--address", required=True)
    parser.add_argument("--role-id-file", required=True)
    parser.add_argument("--secret-id-file", required=True)
    parser.add_argument("--keys", default="", help="comma-separated; export only these")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()

    address = args.address.rstrip("/")
    try:
        login = _call(address, "POST", "/v1/auth/approle/login", body={
            "role_id": Path(args.role_id_file).read_text().strip(),
            "secret_id": Path(args.secret_id_file).read_text().strip(),
        })
        token = str(login["auth"]["client_token"])  # type: ignore[index]
        values: dict[str, str] = {}
        for path in args.paths:
            document = _call(address, "GET", f"/v1/secret/data/{path}", token=token)
            data = document["data"]["data"]  # type: ignore[index]
            values.update({str(key): str(value) for key, value in data.items()})  # type: ignore[union-attr]
    except (OSError, urllib.error.URLError, KeyError) as error:
        print(f"vault_read: could not read {', '.join(args.paths)}: {error}", file=sys.stderr)
        return 1
    wanted = {key.strip() for key in args.keys.split(",") if key.strip()}
    missing = wanted - set(values)
    if missing:
        print(f"vault_read: {', '.join(sorted(missing))} not found in {', '.join(args.paths)}", file=sys.stderr)
        return 1
    for key, value in values.items():
        if not wanted or key in wanted:
            print(f"export {key}={shlex.quote(value)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
