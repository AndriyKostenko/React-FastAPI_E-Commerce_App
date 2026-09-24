"""The wishlist caller comes from the gateway's identity headers, not request.state."""
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from dependencies.dependencies import get_current_user


def _request(headers: dict[str, str]) -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/wishlists/me",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    })


def test_caller_is_read_from_gateway_headers():
    user_id = uuid4()
    caller = get_current_user(_request({
        "X-Authenticated-User-Id": str(user_id),
        "X-Authenticated-User-Email": "user@example.com",
        "X-Authenticated-User-Role": "user",
    }))

    assert caller.user_id == user_id
    assert caller.email == "user@example.com"
    assert caller.role == "user"


def test_missing_identity_is_rejected():
    with pytest.raises(HTTPException) as exc:
        get_current_user(_request({}))
    assert exc.value.status_code == 401


def test_malformed_identity_is_rejected():
    with pytest.raises(HTTPException) as exc:
        get_current_user(_request({"X-Authenticated-User-Id": "not-a-uuid"}))
    assert exc.value.status_code == 401
