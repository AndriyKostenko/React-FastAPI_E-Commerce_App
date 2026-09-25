"""Verifies the gateway's caller assertion before any route runs."""

from logging import Logger

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from shared.auth.caller_assertion import (
    CALLER_ASSERTION_HEADER,
    CallerAssertionVerifier,
    InvalidCallerAssertion,
    RequestTarget,
)
from shared.utils.authenticated_caller import CALLER_STATE_KEY, AuthenticatedCaller


# Where the builder puts the verifier. Read per request, not captured at
# construction, so a test can swap in one built from throwaway keys.
VERIFIER_STATE_KEY = "caller_assertion_verifier"
_HEADER_BYTES = CALLER_ASSERTION_HEADER.lower().encode("latin-1")


class CallerAssertionMiddleware:
    """
    Turns the ``X-Caller-Assertion`` header into ``request.state.authenticated_caller``.

    - no header -> an anonymous caller (public routes, internal service calls);
    - a valid header -> the user it names;
    - a header that fails verification -> 401 at once. Someone presented an
      identity that does not check out; carrying on anonymously would hide it.

    Routes never read the header themselves: they ask ``AuthenticatedCaller``.
    """

    def __init__(self, app: ASGIApp, logger: Logger) -> None:
        self.app = app
        self._logger = logger

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        caller = AuthenticatedCaller()
        assertion = self._header(scope)
        if assertion is not None:
            try:
                caller = self._verifier(scope).verify(
                    assertion, RequestTarget(method=scope["method"], path=scope["path"])
                )
            except InvalidCallerAssertion as error:
                self._logger.warning(
                    "Rejected caller assertion for %s %s: %s", scope["method"], scope["path"], error
                )
                response = JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid caller assertion", "error": "invalid_caller_assertion"},
                )
                await response(scope, receive, send)
                return

        scope.setdefault("state", {})[CALLER_STATE_KEY] = caller
        await self.app(scope, receive, send)

    @staticmethod
    def _header(scope: Scope) -> str | None:
        for name, value in scope.get("headers", ()):
            if name == _HEADER_BYTES:
                return value.decode("latin-1")
        return None

    @staticmethod
    def _verifier(scope: Scope) -> CallerAssertionVerifier:
        verifier = getattr(scope["app"].state, VERIFIER_STATE_KEY, None)
        if not isinstance(verifier, CallerAssertionVerifier):
            # A misconfigured service must fail closed, not fall back to anonymous.
            raise InvalidCallerAssertion("this service has no caller-assertion verifier")
        return verifier
