"""
Guard: every request-scoped database session must commit before the response.

FastAPI runs a yield dependency's exit code after the response by default, so a
session dependency without scope="function" commits after the client has been
told the write succeeded (proven in order_service's
test_commit_before_response.py). This scan keeps a new route or dependency
from quietly reintroducing that.
"""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]
SESSION_DEPENDENCY = re.compile(r"Depends\(\s*(get_db_session)\s*(?P<rest>[,)])")


def _service_sources() -> list[Path]:
    return [
        path
        for path in BACKEND.glob("*_service/**/*.py")
        if ".venv" not in path.parts and "tests" not in path.parts and "alembic" not in path.parts
    ]


def test_the_scan_finds_the_services() -> None:
    assert len({path.relative_to(BACKEND).parts[0] for path in _service_sources()}) >= 9


def test_every_session_dependency_commits_before_the_response() -> None:
    offenders = []
    for path in _service_sources():
        source = path.read_text()
        for match in SESSION_DEPENDENCY.finditer(source):
            call = source[match.start(): source.find(")", match.start()) + 1]
            if 'scope="function"' not in call:
                line = source.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(BACKEND)}:{line}: {call}")
    assert not offenders, "session dependency without scope=\"function\":\n" + "\n".join(offenders)
