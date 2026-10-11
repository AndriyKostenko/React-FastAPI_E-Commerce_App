"""The caller a service is acting for, as the API gateway's signed assertion states it."""

from uuid import UUID

from fastapi import HTTPException, status
from starlette.requests import HTTPConnection


# Where CallerAssertionMiddleware leaves the verified caller for this request.
CALLER_STATE_KEY = "authenticated_caller"

# Retired identity headers. Nothing trusts them any more; the gateway still
# strips them so a stale client or service cannot even appear to use them.
LEGACY_IDENTITY_HEADERS = (
    "X-Authenticated-User-Id",
    "X-Authenticated-User-Email",
    "X-Authenticated-User-Role",
)


class AuthenticatedCaller:
    """The user a downstream service is acting on behalf of.

    Built only from an assertion the gateway signed with its private key and
    this service verified with the public one — see ``CallerAssertionMiddleware``.
    Plain headers are never read, so reaching a service directly (bypassing
    the gateway) can at most make a request anonymous, never impersonate.

    Every field is optional: internal calls between services, event consumers,
    and public endpoints all arrive without a caller. A service must therefore
    treat "no caller" as "cannot prove ownership" and refuse, never as
    "ownership check not required".
    """

    def __init__(
        self,
        user_id: UUID | None = None,
        email: str | None = None,
        role: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.email = email
        self.role = role

    @property
    def is_present(self) -> bool:
        return self.user_id is not None

    def is_admin(self, admin_role: str) -> bool:
        return self.role == admin_role

    @classmethod
    def from_request(cls, connection: HTTPConnection) -> "AuthenticatedCaller":
        """The verified caller, or an anonymous one when the request carried no assertion."""
        caller = getattr(connection.state, CALLER_STATE_KEY, None)
        return caller if isinstance(caller, AuthenticatedCaller) else cls()

    @classmethod
    def require(cls, connection: HTTPConnection) -> "AuthenticatedCaller":
        """The asserted caller, or 401 — for routes that act on a user's behalf."""
        caller = cls.from_request(connection)
        if not caller.is_present:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        return caller

    @classmethod
    def require_admin(cls, connection: HTTPConnection, admin_role: str) -> "AuthenticatedCaller":
        """The asserted caller if they hold the admin role; 401 or 403 otherwise."""
        caller = cls.require(connection)
        if not caller.is_admin(admin_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required",
            )
        return caller
