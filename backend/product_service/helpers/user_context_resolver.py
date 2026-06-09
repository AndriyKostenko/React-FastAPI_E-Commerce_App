from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request

from shared.settings import Settings


@dataclass
class UserContextData:
    """Resolved user context containing user/guest identification and cookie metadata."""
    user_id: UUID | None
    is_guest_user: bool
    guest_id: UUID | None
    new_guest_id: UUID | None  # Only set if a new guest ID was just created
    cookie_kwargs: dict[str, Any] | None  # Cookie settings to apply to response (only if new_guest_id)


class UserContextResolver:
    """
    Resolves user context from HTTP request.
    Handles both authenticated users and guest users with quota tracking via cookies.
    """

    def __init__(self, guest_quota_cookie_name: str, settings: Settings):
        """
        Initialize the resolver with cookie configuration.

        Args:
            guest_quota_cookie_name: Name of the cookie used for guest quota tracking
            settings: Application settings object (must have SECURE_COOKIES attribute)
        """
        self.guest_quota_cookie_name: str = guest_quota_cookie_name
        self.settings: Settings = settings

    async def resolve(self, request: Request) -> UserContextData:
        """
        Resolve user context from the request.

        Returns:
            UserContextData with user_id, guest identification, and cookie metadata
        """
        # Step 1: Extract user_id from authenticated session (set by auth middleware)
        user_id = self._extract_user_id(request)
        is_guest_user = user_id is None

        # Step 2: Handle guest identification and quota cookies
        raw_cookie = request.cookies.get(self.guest_quota_cookie_name)
        guest_id = self._validate_guest_id(raw_cookie, is_guest_user)

        new_guest_id = None
        if not guest_id and is_guest_user:
            new_guest_id = str(uuid4())
            guest_id = new_guest_id

        # Step 3: Build cookie kwargs if a new guest ID was created
        cookie_kwargs = None
        if new_guest_id:
            cookie_kwargs = self._build_cookie_kwargs(request)

        return UserContextData(
            user_id=user_id,
            is_guest_user=is_guest_user,
            guest_id=guest_id,
            new_guest_id=new_guest_id,
            cookie_kwargs=cookie_kwargs,
        )

    @staticmethod
    def _extract_user_id(request: Request) -> str | None:
        """Extract user_id from authenticated session or None for guest."""
        if hasattr(request.state, 'current_user') and request.state.current_user:
            return str(request.state.current_user.id)
        return None

    @staticmethod
    def _validate_guest_id(raw_cookie: str | None, is_guest_user: bool) -> str | None:
        """
        Validate that the cookie value is a well-formed UUID.
        Returns the UUID if valid, None otherwise.
        Prevents arbitrary values from polluting Redis keys.
        """
        if not raw_cookie or not is_guest_user:
            return None

        try:
            UUID(raw_cookie)
            return raw_cookie
        except ValueError:
            return None

    def _build_cookie_kwargs(self, request: Request) -> dict:
        """
        Build cookie settings to apply to the response.
        Respects HTTPS detection and configured cookie security settings.
        """
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
        is_https_request = request.url.scheme == "https" or forwarded_proto == "https"

        return dict(
            key=self.guest_quota_cookie_name,
            value=None,  # Will be set by caller with new_guest_id
            httponly=True,
            secure=bool(self.settings.SECURE_COOKIES and is_https_request),
            samesite="lax",
            max_age=self.settings.PRODUCT_IMAGE_GUEST_GENERATION_WINDOW_HOURS * 3600,
        )
