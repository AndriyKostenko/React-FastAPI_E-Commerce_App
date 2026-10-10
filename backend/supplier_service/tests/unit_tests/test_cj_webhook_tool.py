"""
``dev.sh cj-webhook open-id``: the openId only ever lands in dev.sh's private file.

It once went to standard output, where the service's JSON log lines go too,
and Vault stored the log lines around the openId: every CJ push then failed
verification. Each refusal here happens before CJ is asked for a token
(CJ rate-limits those).
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from tools import cj_webhook


def _file(tmp_path: Path, mode: int, content: str = "") -> Path:
    path = tmp_path / "cj-open-id"
    path.write_text(content)
    path.chmod(mode)
    return path


def test_only_an_empty_owner_only_file_is_accepted(tmp_path: Path) -> None:
    assert cj_webhook._private_empty_file(_file(tmp_path, 0o600)) is True


@pytest.mark.parametrize("mode, content", [(0o644, ""), (0o640, ""), (0o600, "already here")])
def test_a_readable_or_used_file_is_refused(tmp_path: Path, mode: int, content: str) -> None:
    assert cj_webhook._private_empty_file(_file(tmp_path, mode, content)) is False


def test_no_file_or_a_directory_is_refused(tmp_path: Path) -> None:
    assert cj_webhook._private_empty_file(None) is False
    assert cj_webhook._private_empty_file(tmp_path / "missing") is False
    assert cj_webhook._private_empty_file(tmp_path) is False


async def test_without_a_private_file_cj_is_never_asked(tmp_path: Path) -> None:
    with patch.object(cj_webhook, "CJDropshippingAPIClient") as client:
        assert await cj_webhook.main(["open-id"]) == 2
        assert await cj_webhook.main(["open-id", "--to", str(_file(tmp_path, 0o644))]) == 2
    client.assert_not_called()


async def test_the_open_id_is_written_into_the_file_and_nowhere_else(tmp_path: Path, capsys) -> None:
    target = _file(tmp_path, 0o600)

    async def token_response(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {"result": True, "data": {"openId": 12312, "accessToken": "t"}}

    with patch.object(cj_webhook.CJDropshippingAPIClient, "request", side_effect=token_response):
        assert await cj_webhook.main(["open-id", "--to", str(target)]) == 0

    assert target.read_text() == "12312"
    assert "12312" not in capsys.readouterr().out


async def test_a_non_numeric_open_id_is_not_written(tmp_path: Path) -> None:
    target = _file(tmp_path, 0o600)

    async def token_response(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {"result": True, "data": {"openId": None}}

    with patch.object(cj_webhook.CJDropshippingAPIClient, "request", side_effect=token_response):
        assert await cj_webhook.main(["open-id", "--to", str(target)]) == 1

    assert target.read_text() == ""
