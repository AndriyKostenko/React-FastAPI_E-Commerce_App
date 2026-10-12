"""Copied modules must stay identical in every service that carries them.

There is no shared library: each service keeps its own copy of the
infrastructure it uses (and of a few contracts and the pricing helpers), so a
fix made in one copy must be made in all. This fails when two copies of the
same path differ, apart from the modules that are trimmed per service on
purpose.

usage (from the repository root):  python3 backend/ci/check_copies.py
"""

import hashlib
import sys
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

# Paths, relative to a service directory, whose copies must match everywhere.
COPIED = ("infrastructure/**/*.py", "contracts/auth.py", "contracts/services_enums.py",
          "utils/supplier_pricing.py", "utils/exchange_rates.py", "utils/money.py")

# Trimmed per service on purpose (see PRODUCTION_GAPS §8.5, phase 4): each
# copy of the test signing keys keeps only what that service's tests call, and
# the gateway's user_tokens.py is the verifier alone.
TRIMMED = frozenset({"infrastructure/testing/signing_keys.py", "infrastructure/auth/user_tokens.py"})


def main() -> int:
    copies: dict[str, dict[str, str]] = defaultdict(dict)
    for service in sorted(p for p in BACKEND.iterdir() if (p / "settings.py").is_file()):
        for pattern in COPIED:
            for path in service.glob(pattern):
                if ".venv" in path.parts or "__pycache__" in path.parts:
                    continue
                relative = path.relative_to(service).as_posix()
                copies[relative][service.name] = hashlib.sha256(path.read_bytes()).hexdigest()

    drifted = 0
    for relative, by_service in sorted(copies.items()):
        if relative in TRIMMED or len(by_service) < 2:
            continue
        versions: dict[str, list[str]] = defaultdict(list)
        for service, digest in by_service.items():
            versions[digest].append(service)
        if len(versions) > 1:
            drifted += 1
            print(f"!! {relative} differs between copies:")
            for services in sorted(versions.values(), key=len, reverse=True):
                print(f"     {', '.join(sorted(services))}")
    checked = sum(1 for r, s in copies.items() if r not in TRIMMED and len(s) > 1)
    print(f"{checked} copied modules checked, {drifted} drifted")
    return 1 if drifted else 0


if __name__ == "__main__":
    sys.exit(main())
