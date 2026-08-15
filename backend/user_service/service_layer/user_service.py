from datetime import datetime, timedelta, timezone
from asyncio import Lock
import hashlib
import secrets
from time import monotonic
from typing import Annotated
from uuid import UUID

from httpx import AsyncClient, Response
from pydantic import EmailStr
from fastapi import Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.exceptions import HTTPException
from sqlalchemy.exc import IntegrityError
from jose import jwt as jose_jwt, jwk, JWTError

from models.user_models import User
from schemas.user_schemas import CurrentUserInfo
from schemas.user_schemas import (
    UserSignUp,
    UserInfo,
    UserBasicUpdate,
    UsersFilterParams,
)
from shared.contracts.events import (
    UserRegisteredEvent,
    UserLoginEvent,
    PasswordResetRequestedEvent,
    PasswordResetSuccessEvent,
    EmailVerificationEvent,
    UserDeletedEvent,
)
from shared.settings import Settings
from shared.managers.cache_manager import CacheManager
from shared.enums.event_enums import UserEvents
from exceptions.user_exceptions import (
    UserAlreadyExistsError,
    UserNotFoundError,
    UserUpdateError
)
from database_layer.user_repository import UserRepository
from shared.managers.password_manager import PasswordManager
from shared.managers.token_manager import TokenManager
from service_layer.outbox_event_service import OutboxEventService


class UserService:
    """
    Service layer for user management operations, business logic and data validation.

    Responsibilities:
    - Business logic execution
    - Database operations via repository
    - Event publishing for state changes via the outbox pattern
    """
    def __init__(self,
                repository: UserRepository,
                password_manager: PasswordManager,
                token_manager: TokenManager,
                cache_manager: CacheManager,
                outbox_event_service: OutboxEventService,
                http_client: AsyncClient,
                settings: Settings):
        self.repository: UserRepository = repository
        self.password_manager: PasswordManager = password_manager
        self.token_manager: TokenManager = token_manager
        self.cache_manager: CacheManager = cache_manager
        self.outbox_event_service: OutboxEventService = outbox_event_service
        self.httpx_client: AsyncClient = http_client
        self.settings = settings

    def _token_hash(self, token: str) -> str:
        """Compute SHA-256 hash of a token for secure Redis storage."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _refresh_key(self, token_or_hash: str) -> str:
        return f"refresh:{token_or_hash}"

    def _user_refresh_set_key(self, user_id: UUID | str) -> str:
        return f"refresh:user:{user_id}"

    def _verify_token_key(self, token: str) -> str:
        return f"verify_email:{self._token_hash(token)}"

    def _reset_token_key(self, token: str) -> str:
        return f"pwd_reset:{self._token_hash(token)}"

    async def _store_refresh(self, user_id: UUID | str, refresh_token: str) -> None:
        """Store hashed refresh token and index it in the user's active token set."""
        token_hash = self._token_hash(refresh_token)
        ttl_seconds = self.settings.REFRESH_TOKEN_TIME_DELTA_DAYS * 86400
        pipe = self.cache_manager.redis.pipeline()
        pipe.setex(self._refresh_key(token_hash), ttl_seconds, str(user_id))
        pipe.sadd(self._user_refresh_set_key(user_id), token_hash)
        pipe.expire(self._user_refresh_set_key(user_id), ttl_seconds)
        await pipe.execute()

    async def _revoke_all_refresh_for_user(self, user_id: UUID | str) -> None:
        """Revoke all active refresh tokens for a given user (family invalidation)."""
        set_key = self._user_refresh_set_key(user_id)
        token_hashes = await self.cache_manager.redis.smembers(set_key)
        if token_hashes:
            pipe = self.cache_manager.redis.pipeline()
            for th in token_hashes:
                th_str = th.decode("utf-8") if isinstance(th, bytes) else str(th)
                pipe.delete(self._refresh_key(th_str))
            pipe.delete(set_key)
            await pipe.execute()

    async def create_user(self, data: UserSignUp) -> tuple[UserInfo , str]:
        """
        Create a new user and publish registration event with opaque token via outbox.

        Returns:
            tuple: (UserInfo, verification_token)
        """
        email = str(data.email).strip().lower()
        hashed_password = self.password_manager.hash_password(data.password)
        new_user = User(
            name=data.name,
            email=email,
            hashed_password=hashed_password,
            is_verified=False,
            role="user",
            is_active=True,
            token_version=1
        )
        try:
            user = await self.repository.create(new_user)
        except IntegrityError as exc:
            raise UserAlreadyExistsError("User with that email already exists.") from exc

        # Generate single-use opaque verification token and store hash in Redis
        verification_token = secrets.token_urlsafe(32)
        ttl_seconds = self.settings.VERIFICATION_TOKEN_EXPIRY_MINUTES * 60
        await self.cache_manager.redis.setex(
            self._verify_token_key(verification_token),
            ttl_seconds,
            str(user.id)
        )

        await self.outbox_event_service.add_outbox_event(
            event_type=UserEvents.USER_REGISTERED,
            payload=UserRegisteredEvent(
                user_email=user.email,
                token=verification_token,
                user_id=user.id,
            )
        )

        return UserInfo.model_validate(user), verification_token

    async def verify_password(self, email: EmailStr, password: str) -> bool:
        user = await self.repository.get_by_field("email", email)
        if not user:
            raise UserNotFoundError(f"User with email: {email} is not found")
        return self.password_manager.verify_password(password, user.hashed_password)

    async def login_user(self, form_data: OAuth2PasswordRequestForm) -> tuple[CurrentUserInfo, str, int, str, int]:
        current_user, access_token, access_expiry, refresh_token, refresh_expiry = await self.authenticate_user(
            email=form_data.username, password=form_data.password
        )

        await self.outbox_event_service.add_outbox_event(
            event_type=UserEvents.USER_LOGGED_IN,
            payload=UserLoginEvent(
                user_email=current_user.email,
                user_id=current_user.id,
            )
        )

        return current_user, access_token, access_expiry, refresh_token, refresh_expiry

    async def login_or_register_google_user(self, id_token: str) -> tuple[CurrentUserInfo, str, int, str, int]:
        """
        Verify a Google ID token, then find or create the user, and issue backend JWT tokens.
        Validates aud, iss, and email_verified claims before trusting the token.
        """
        if not self.settings.GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=500, detail="Google authentication client ID is not configured")

        claims = await self._verify_google_id_token(id_token)

        # Require email_verified
        if claims.get("email_verified") not in (True, "true"):
            raise HTTPException(status_code=401, detail="Google email is not verified")

        email: str | None = claims.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Could not retrieve email from Google token")

        name: str = claims.get("name") or email.split("@")[0]

        # Find or create the user
        user = await self.repository.get_by_field("email", email)
        if not user:
            try:
                hashed_password = self.password_manager.hash_password(secrets.token_urlsafe(32))
                new_user = User(
                    name=name,
                    email=email,
                    hashed_password=hashed_password,
                    is_verified=True,
                    role="user",
                    is_active=True,
                    token_version=1
                )
                user = await self.repository.create(new_user)
            except IntegrityError:
                # Race condition: another request created the same user — fetch it
                user = await self.repository.get_by_field("email", email)
                if not user:
                    raise HTTPException(status_code=500, detail="Failed to create user")
        else:
            # Google has just proven ownership of this address.  A linked local
            # account must not retain a password-based session family.
            user = await self.repository.update_by_field(
                field_name="email", value=email, is_verified=True, hashed_password=None,
                token_version=(user.token_version or 1) + 1,
            )
            await self._revoke_all_refresh_for_user(user.id)

        # Enforce account-level guards (same as authenticate_user)
        if not user.is_active:
            raise HTTPException(status_code=401, detail="Account is deactivated")

        access_token, access_expiry = self.token_manager.create_access_token(
            email=email,
            user_id=user.id,
            role=user.role,
            expires_delta=timedelta(minutes=self.settings.TOKEN_TIME_DELTA_MINUTES),
            purpose="access",
            extra_claims={"ver": user.token_version},
        )
        refresh_token, refresh_expiry = self.token_manager.create_refresh_token(
            email=email,
            user_id=user.id,
            role=user.role,
            extra_claims={"ver": user.token_version},
        )
        await self._store_refresh(user.id, refresh_token)
        current_user = CurrentUserInfo(email=user.email, id=user.id, role=user.role)
        return current_user, access_token, access_expiry, refresh_token, refresh_expiry

    async def _verify_google_id_token(self, id_token: str) -> dict:
        """Verify a Google ID token locally against Google's rotating JWKS."""
        try:
            header = jose_jwt.get_unverified_header(id_token)
            kid = header.get("kid")
            if not kid or header.get("alg") not in {"RS256"}:
                raise ValueError("unsupported Google token header")
            keys = await self._get_google_jwks()
            key_data = next((item for item in keys if item.get("kid") == kid), None)
            if not key_data:
                # Key rotations are rare; force one refresh before rejecting.
                keys = await self._get_google_jwks(force_refresh=True)
                key_data = next((item for item in keys if item.get("kid") == kid), None)
            if not key_data:
                raise ValueError("unknown Google signing key")
            return jose_jwt.decode(
                id_token,
                jwk.construct(key_data, algorithm="RS256"),
                algorithms=["RS256"],
                audience=self.settings.GOOGLE_CLIENT_ID,
                issuer="https://accounts.google.com",
            )
        except (JWTError, ValueError, KeyError, TypeError):
            raise HTTPException(status_code=401, detail="Invalid Google token")

    async def _get_google_jwks(self, force_refresh: bool = False) -> list[dict]:
        if not force_refresh and self._google_jwks and monotonic() < self._google_jwks_expires_at:
            return self._google_jwks["keys"]
        async with self._google_jwks_lock:
            if not force_refresh and self._google_jwks and monotonic() < self._google_jwks_expires_at:
                return self._google_jwks["keys"]
            try:
                if self.httpx_client is None:
                    raise RuntimeError("Google HTTP client is unavailable")
                response: Response = await self.httpx_client.get("https://www.googleapis.com/oauth2/v3/certs")
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload.get("keys"), list):
                    raise ValueError("invalid JWKS response")
            except Exception:
                # Do not accept a token if signing keys cannot be obtained.
                raise HTTPException(status_code=503, detail="Google authentication is temporarily unavailable")
            self.__class__._google_jwks = payload
            # Google rotates keys at most daily; refresh within one hour even if
            # the cache-control header is unavailable.
            self.__class__._google_jwks_expires_at = monotonic() + 3600
            return payload["keys"]

    async def get_all_users(self, filters: Annotated[UsersFilterParams, Query()]) -> list[UserInfo]:
        filters_dict = filters.model_dump()

        # Extracting pagination and sorting params
        offset = filters_dict.pop("offset", None)
        limit = filters_dict.pop("limit", None)
        sort_by = filters_dict.pop("sort_by", None)
        sort_order = filters_dict.pop("sort_order", "asc").lower()
        search_term = filters_dict.pop("search_term", None)

        # Range filters
        date_filters = {"date_created_from": filters_dict.pop("date_created_from", None),
                        "date_created_to": filters_dict.pop("date_created_to", None),
                        "date_updated_from": filters_dict.pop("date_updated_from", None),
                        "date_updated_to": filters_dict.pop("date_updated_to", None)}

        # Remaining filters
        cleaned_filters = {key: value for key, value in filters_dict.items() if value is not None}

        # General query params
        users = await self.repository.get_all(filters=cleaned_filters,
                                              sort_by=sort_by,
                                              sort_order=sort_order,
                                              offset=offset,
                                              limit=limit,
                                              search_term=search_term,
                                              date_filters=date_filters,
                                              search_fields=User.get_search_fields())
        if not users:
            return []
        return [UserInfo.model_validate(user) for user in users]

    async def get_user_by_email(self, email: EmailStr) -> UserInfo:
        user: User | None = await self.repository.get_by_field(field_name="email", value=email)
        if not user:
            raise UserNotFoundError(f"User with email {email} not found.")
        return UserInfo.model_validate(user)

    async def get_user_by_id(self, user_id: UUID) -> UserInfo:
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id {user_id} not found.")
        return UserInfo.model_validate(user)

    async def get_user_hashed_password(self, email: EmailStr) -> str:
        user = await self.repository.get_by_field(field_name="email", value=email)
        if not user:
            raise UserNotFoundError(f"User with email {email} not found.")
        return user.hashed_password

    async def update_user_password(self, email: EmailStr, new_password: str) -> UserInfo:
        hashed_password = self.password_manager.hash_password(new_password)
        updated_user = await self.repository.update_by_field(field_name="email", value=email, hashed_password=hashed_password)
        if not updated_user:
            raise UserNotFoundError(f"User with email {email} not found.")
        return UserInfo.model_validate(updated_user)

    async def update_user_basic_info(self, user_id: UUID, update_data: UserBasicUpdate) -> UserInfo:
        changes = update_data.model_dump(exclude_unset=True)
        if not changes:
            raise HTTPException(status_code=400, detail="At least one field must be supplied")
        updated_user = await self.repository.update_by_id(item_id=user_id, data=changes)
        if not updated_user:
            raise UserNotFoundError(f"User with id: {user_id} not found.")
        return UserInfo.model_validate(updated_user)

    async def verify_email(self, token: str) -> "UserInfo":
        """Verify user email using single-use opaque token."""
        key = self._verify_token_key(token)
        user_id_str = await self.cache_manager.redis.getdel(key)
        if not user_id_str:
            raise HTTPException(status_code=401, detail="Verification token is invalid or expired")

        user_id = UUID(user_id_str.decode("utf-8") if isinstance(user_id_str, bytes) else user_id_str)
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError("User not found for verification")

        updated_user = await self.repository.update_by_field(
            field_name="email",
            value=user.email,
            is_verified=True
        )
        if not updated_user:
            raise UserNotFoundError("User not found for verification")

        await self.outbox_event_service.add_outbox_event(
            event_type=UserEvents.USER_EMAIL_VERIFIED,
            payload=EmailVerificationEvent(
                user_email=updated_user.email,
                user_id=updated_user.id,
            )
        )

        return UserInfo.model_validate(updated_user)

    async def delete_user_by_id(self, user_id: UUID) -> None:
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id: {user_id} not found.")

        anonymized_email = f"deleted+{user.id}@invalid.local"
        updated_user = await self.repository.update_by_id(
            item_id=user_id,
            data={"name": "Deleted user", "email": anonymized_email, "hashed_password": None,
                  "phone_number": None, "image": None, "is_active": False,
                  "deleted_at": datetime.now(timezone.utc), "token_version": (user.token_version or 1) + 1},
        )
        if not updated_user:
            raise UserNotFoundError(f"User with id: {user_id} not found.")

        await self._revoke_all_refresh_for_user(user_id)

        await self.outbox_event_service.add_outbox_event(
            event_type=UserEvents.USER_DELETED,
            payload=UserDeletedEvent(
                user_email=user.email,
                user_id=user_id,
            )
        )

    async def get_verified_users(self) -> list[UserInfo]:
        users =  await self.repository.get_verified_users()
        return [UserInfo.model_validate(user) for user in users]

    async def get_by_role(self, role: str) -> list[UserInfo]:
        users = await self.repository.get_users_by_role(role=role)
        return [UserInfo.model_validate(user) for user in users]

    async def request_password_reset(self, email: EmailStr) -> tuple[UserInfo | None, str]:
        """
        Request password reset with single-use opaque token.
        Always returns safely to prevent account enumeration.
        """
        user = await self.repository.get_by_field("email", email)
        if not user:
            # Prevent enumeration: return silently without raising 404 or writing outbox event
            return None, ""

        reset_token = secrets.token_urlsafe(32)
        ttl_seconds = self.settings.RESET_TOKEN_EXPIRY_MINUTES * 60
        await self.cache_manager.redis.setex(
            self._reset_token_key(reset_token),
            ttl_seconds,
            str(user.id)
        )

        await self.outbox_event_service.add_outbox_event(
            event_type=UserEvents.USER_PASSWORD_RESET_REQUEST,
            payload=PasswordResetRequestedEvent(
                user_email=user.email,
                reset_token=reset_token,
                user_id=user.id,
            )
        )

        return UserInfo.model_validate(user), reset_token

    async def reset_password_with_token(self, token: str, new_password: str) -> UserInfo:
        """Reset password using single-use opaque token, bumping token_version and invalidating sessions."""
        key = self._reset_token_key(token)
        user_id_str = await self.cache_manager.redis.getdel(key)
        if not user_id_str:
            raise HTTPException(status_code=401, detail="Password reset token is invalid or expired")

        user_id = UUID(user_id_str.decode("utf-8") if isinstance(user_id_str, bytes) else user_id_str)
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        new_version = (user.token_version or 1) + 1
        hashed_password = self.password_manager.hash_password(new_password)
        updated_user = await self.repository.update_by_id(
            item_id=user.id,
            data={"hashed_password": hashed_password, "token_version": new_version}
        )
        if not updated_user:
            raise UserUpdateError("Password reset failed")

        # Invalidate all existing sessions / refresh tokens
        await self._revoke_all_refresh_for_user(user.id)

        await self.outbox_event_service.add_outbox_event(
            event_type=UserEvents.USER_PASSWORD_RESET_SUCCESS,
            payload=PasswordResetSuccessEvent(
                user_email=updated_user.email,
                user_id=updated_user.id,
            )
        )

        return UserInfo.model_validate(updated_user)

    async def authenticate_user(self,
                                email: EmailStr,
                                password: str) -> tuple[CurrentUserInfo, str, int, str, int]:
        """
        Authenticate user with constant-time password verification and rotating refresh tokens.
        """
        user = await self.repository.get_by_field("email", email)
        dummy_hash = self.password_manager.dummy_hash()
        hashed = user.hashed_password if user and user.hashed_password else dummy_hash
        is_valid = self.password_manager.verify_password(password, hashed)

        if not user or not is_valid:
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        if not user.is_verified:
            raise HTTPException(status_code=401, detail="User is not verified")
        if not user.is_active:
            raise HTTPException(status_code=401, detail="Account is deactivated")

        access_token, access_expiry = self.token_manager.create_access_token(
            email=email,
            user_id=user.id,
            role=user.role,
            expires_delta=timedelta(minutes=self.settings.TOKEN_TIME_DELTA_MINUTES),
            purpose="access",
            extra_claims={"ver": user.token_version}
        )
        refresh_token, refresh_expiry = self.token_manager.create_refresh_token(
            email=email,
            user_id=user.id,
            role=user.role,
            extra_claims={"ver": user.token_version}
        )

        await self._store_refresh(user.id, refresh_token)

        current_user = CurrentUserInfo(
            email=user.email,
            id=user.id,
            role=user.role
        )
        return current_user, access_token, access_expiry, refresh_token, refresh_expiry

    async def refresh_access_token(self, refresh_token: str) -> tuple[str, int, str, int]:
        """
        Validate a refresh token, rotate it, detect reuse, and issue new credentials.

        Returns:
            tuple: (new_access_token, access_expiry, new_refresh_token, refresh_expiry)
        """
        token_data = self.token_manager.decode_token(refresh_token, required_purpose="refresh")
        token_hash = self._token_hash(refresh_token)
        stored_user_id = await self.cache_manager.redis.getdel(self._refresh_key(token_hash))

        if not stored_user_id:
            # Token reuse detected or token expired -> revoke all sessions for this user family
            await self._revoke_all_refresh_for_user(token_data.id)
            raise HTTPException(status_code=401, detail="Refresh token reuse detected or token expired")

        # Clean old token hash from user's active set
        await self.cache_manager.redis.srem(self._user_refresh_set_key(token_data.id), token_hash)

        # Fresh database check to eliminate stale-role / deactivation claims
        user = await self.repository.get_by_id(token_data.id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Account is deactivated or not found")

        if token_data.token_version != user.token_version:
            raise HTTPException(status_code=401, detail="Token version revoked")

        # Mint rotated refresh token
        new_refresh_token, new_refresh_expiry = self.token_manager.create_refresh_token(
            email=user.email,
            user_id=user.id,
            role=user.role,
            extra_claims={"ver": user.token_version}
        )
        await self._store_refresh(user.id, new_refresh_token)

        # Mint new access token
        access_token, expiry = self.token_manager.create_access_token(
            email=user.email,
            user_id=user.id,
            role=user.role,
            expires_delta=timedelta(minutes=self.settings.TOKEN_TIME_DELTA_MINUTES),
            purpose="access",
            extra_claims={"ver": user.token_version}
        )
        return access_token, expiry, new_refresh_token, new_refresh_expiry

    async def logout_user(self, refresh_token: str, user_id: UUID | None = None) -> None:
        """Revoke a refresh token and remove from user's active set."""
        token_hash = self._token_hash(refresh_token)
        await self.cache_manager.redis.delete(self._refresh_key(token_hash))
        if user_id:
            await self.cache_manager.redis.srem(self._user_refresh_set_key(user_id), token_hash)

    async def get_current_user_from_token(self, token: str) -> CurrentUserInfo:
        """Validate an access token against the current account state."""
        user_info = self.token_manager.decode_token(token, required_purpose="access")
        user = await self.repository.get_by_id(user_info.id)
        if not user or not user.is_active or user_info.token_version != user.token_version:
            raise HTTPException(status_code=401, detail="Token is revoked or account is unavailable")
        return CurrentUserInfo(
            email=user.email,
            id=user.id,
            role=user.role
        )
    _google_jwks: dict | None = None
    _google_jwks_expires_at: float = 0
    _google_jwks_lock = Lock()
