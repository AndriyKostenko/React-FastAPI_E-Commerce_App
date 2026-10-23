"""Copied modules must stay identical in every service that carries them.

There is no shared library: each service keeps its own copy of the
infrastructure it uses (and of a few contracts and the pricing helpers), so a
fix made in one copy must be made in all. This fails when two copies of the
same path differ, apart from the modules that are trimmed per service on
purpose. The contract modules are trimmed too (each service keeps the events it
publishes or consumes), so their classes are compared one by one instead: a
model must be the same wherever it is carried, or a bound one service publishes
under could be refused by a consumer. Enums are left out, as each copy lists
only the members its service uses.

usage (from the repository root):  python3 backend/ci/check_copies.py
"""

import ast
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

# Paths, relative to a service directory, whose copies must match everywhere.
COPIED = ("infrastructure/**/*.py", "contracts/auth.py", "contracts/services_enums.py",
          "contracts/limits.py", "utils/supplier_pricing.py", "utils/exchange_rates.py", "utils/money.py")

# Trimmed per service on purpose (see PRODUCTION_GAPS §8.5, phase 4): each
# copy of the test signing keys keeps only what that service's tests call, and
# the gateway's user_tokens.py is the verifier alone.
TRIMMED = frozenset({"infrastructure/testing/signing_keys.py", "infrastructure/auth/user_tokens.py"})


def _services() -> list[Path]:
    return sorted(p for p in BACKEND.iterdir() if (p / "settings.py").is_file())


def _contract_classes() -> dict[str, dict[str, str]]:
    """Every non-enum class in a service's contracts/, by name: service -> source."""
    classes: dict[str, dict[str, str]] = defaultdict(dict)
    for service in _services():
        for path in sorted((service / "contracts").glob("*.py")):
            source = path.read_text()
            for node in ast.parse(source).body:
                if not isinstance(node, ast.ClassDef):
                    continue
                bases = {base.id if isinstance(base, ast.Name) else ast.unparse(base) for base in node.bases}
                if bases & {"StrEnum", "Enum", "str"}:
                    continue
                classes[f"{path.name}:{node.name}"][service.name] = ast.get_source_segment(source, node) or ""
    return classes


def _report(name: str, by_service: dict[str, str]) -> int:
    versions: dict[str, list[str]] = defaultdict(list)
    for service, digest in by_service.items():
        versions[digest].append(service)
    if len(versions) == 1:
        return 0
    print(f"!! {name} differs between copies:")
    for services in sorted(versions.values(), key=len, reverse=True):
        print(f"     {', '.join(sorted(services))}")
    return 1


def main() -> int:
    copies: dict[str, dict[str, str]] = defaultdict(dict)
    for service in _services():
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
        drifted += _report(relative, by_service)
    checked = sum(1 for r, s in copies.items() if r not in TRIMMED and len(s) > 1)

    shared_classes = {name: by_service for name, by_service in _contract_classes().items() if len(by_service) > 1}
    for name, by_service in sorted(shared_classes.items()):
        drifted += _report(name, by_service)

    print(f"{checked} copied modules and {len(shared_classes)} contract classes checked, {drifted} drifted")
    return 1 if drifted else 0


if __name__ == "__main__":
    sys.exit(main())
