"""
The wishlist caller comes from the gateway's verified assertion — which the
caller-assertion middleware leaves on request.state — and never from headers.
"""
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from dependencies.dependencies import get_current_user
from shared.utils.authenticated_caller import CALLER_STATE_KEY, AuthenticatedCaller


def _request(headers: dict[str, str] | None = None, caller: AuthenticatedCaller | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/wishlists/me",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "state": {CALLER_STATE_KEY: caller} if caller else {},
    }
    return Request(scope)


def test_caller_is_the_verified_assertion():
    user_id = uuid4()
    verified = AuthenticatedCaller(user_id=user_id, email="user@example.com", role="user")

    caller = get_current_user(_request(caller=verified))

    assert caller.user_id == user_id
    assert caller.email == "user@example.com"
    assert caller.role == "user"


def test_missing_identity_is_rejected():
    with pytest.raises(HTTPException) as exc:
        get_current_user(_request())
    assert exc.value.status_code == 401


def test_plain_identity_headers_are_not_trusted():
    # What anyone who reaches the service directly could send.
    with pytest.raises(HTTPException) as exc:
        get_current_user(_request({"X-Authenticated-User-Id": str(uuid4()), "X-Authenticated-User-Role": "admin"}))
    assert exc.value.status_code == 401
