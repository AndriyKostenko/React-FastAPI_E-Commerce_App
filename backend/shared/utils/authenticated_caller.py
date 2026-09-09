"""Reads the caller identity the API gateway asserts on a proxied request."""

from uuid import UUID

from starlette.requests import HTTPConnection


USER_ID_HEADER = "X-Authenticated-User-Id"
USER_EMAIL_HEADER = "X-Authenticated-User-Email"
USER_ROLE_HEADER = "X-Authenticated-User-Role"


class AuthenticatedCaller:
    """The user a downstream service is acting on behalf of.

    The gateway validates the token and restates these headers, stripping any
    the client sent, so a service may trust them *only* because nothing outside
    the mesh can reach it directly — which is what the Host allowlist and the
    private Docker network enforce.

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
        raw_id = connection.headers.get(USER_ID_HEADER)
        user_id: UUID | None = None
        if raw_id:
            try:
                user_id = UUID(raw_id)
            except ValueError:
                # A malformed id is treated as no identity at all rather than
                # being passed on as a string that would never match an owner.
                user_id = None
        return cls(
            user_id=user_id,
            email=connection.headers.get(USER_EMAIL_HEADER),
            role=connection.headers.get(USER_ROLE_HEADER),
        )
