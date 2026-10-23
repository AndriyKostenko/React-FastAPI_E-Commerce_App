"""Fail on high or critical npm advisories in production dependencies.

Reads `npm audit --omit=dev --json` on stdin. Every high or critical advisory
fails the run unless it is listed for that app in ALLOWED below, with the
reason it cannot reach a user. An allowed advisory that no longer appears is
reported, so the entry is removed once its reason is gone.

usage (from the repository root):
    (cd <app> && npm audit --omit=dev --json) | python3 backend/ci/npm_audit_gate.py <app>
"""

import json
import sys

BLOCKING = frozenset({"high", "critical"})

# App directory -> advisory URL -> why it is accepted. Keep this list short;
# never add an advisory for code that is served or run.
_TINYMCE = (
    "tinymce 6 comes with the newest AdminJS (@adminjs/design-system -> "
    "@tinymce/tinymce-react) and has no fixed release under its licence (7.9.3+ "
    "is GPL). The npm copy is never served: AdminJS loads TinyMCE from its own "
    "CDN URL, and only for a 'richtext' property, which no admin-js resource has."
)
ALLOWED: dict[str, dict[str, str]] = {
    "backend/admin-js-service": {
        "https://github.com/advisories/GHSA-mh5m-5hw4-5c69": _TINYMCE,
        "https://github.com/advisories/GHSA-vg35-5wq7-3x7w": _TINYMCE,
        "https://github.com/advisories/GHSA-q742-qvgc-gc2f": _TINYMCE,
        "https://github.com/advisories/GHSA-v98h-vmpc-fpqv": _TINYMCE,
    },
}


def blocking_advisories(report: dict) -> dict[str, str]:
    """Each high or critical advisory's URL, with the package and title."""
    found: dict[str, str] = {}
    for package, vulnerability in report.get("vulnerabilities", {}).items():
        # `via` mixes advisories (objects) with the names of the vulnerable
        # dependencies that pull this package in (strings). The advisories
        # sit on the package that has them, so the strings can be skipped.
        for advisory in vulnerability.get("via", []):
            if isinstance(advisory, dict) and advisory.get("severity") in BLOCKING:
                found[advisory["url"]] = (
                    f"{advisory['severity']} {package}: {advisory['title']}"
                )
    return found


def main(app: str) -> int:
    allowed = ALLOWED.get(app.rstrip("/"), {})
    report = json.load(sys.stdin)
    # A failed audit (registry unreachable, no lock file) still prints JSON,
    # with an error and no vulnerabilities, which must not read as clean.
    if "error" in report or "metadata" not in report:
        print(f"FAILED   npm audit did not run: {report.get('error', report)}")
        return 1
    found = blocking_advisories(report)
    failing = {url: what for url, what in found.items() if url not in allowed}
    for url, what in sorted(found.items()):
        if url in allowed:
            print(f"allowed  {what} ({url})")
    for url in sorted(set(allowed) - set(found)):
        print(
            f"::warning title=npm audit::{url} is allowed for {app} but no longer reported; remove it from ALLOWED"
        )
    for url, what in sorted(failing.items()):
        print(f"FAILED   {what} ({url})")
    return 1 if failing else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
