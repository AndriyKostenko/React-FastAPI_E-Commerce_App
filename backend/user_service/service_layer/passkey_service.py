from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self
from uuid import UUID

from fastapi import HTTPException
from pydantic import JsonValue
from sqlalchemy.exc import IntegrityError
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import options_to_json_dict, parse_authentication_credential_json
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from database_layer.webauthn_credential_repository import WebAuthnCredentialRepository
from models.user_models import User
from models.webauthn_credential_models import WebAuthnCredential
from schemas.user_schemas import CurrentUserInfo, PasskeyCeremonyOptions, PasskeySummary
from service_layer.passkey_ceremony_store import CeremonyPurpose, PasskeyCeremonyStore
from service_layer.session_issuer import IssuedSession
from service_layer.user_service import UserService
from shared.contracts.auth import AuthMethod
from shared.settings import Settings


@dataclass(frozen=True, slots=True)
class RelyingParty:
    """Who the passkeys belong to: the admin panel's host name and origins."""

    rp_id: str
    name: str
    origins: tuple[str, ...]

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(settings.WEBAUTHN_RP_ID, settings.WEBAUTHN_RP_NAME, tuple(settings.WEBAUTHN_ORIGINS))


class PasskeyService:
    """Admin passkeys: enrolment through an owner-issued link, and sign-in.

    An admin signs in with both factors: the password (``begin_sign_in``)
    earns a challenge, and only a passkey's signature over that challenge
    (``finish_sign_in``) earns a session, marked ``amr = [pwd, webauthn]``.
    User verification (the device's PIN or biometric) is required in both
    ceremonies, so a passkey alone, on an unlocked device, is not enough either.
    """

    def __init__(
        self,
        user_service: UserService,
        credentials: WebAuthnCredentialRepository,
        ceremonies: PasskeyCeremonyStore,
        relying_party: RelyingParty,
        enrolment_link_base: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._users = user_service
        self._credentials = credentials
        self._ceremonies = ceremonies
        self._rp = relying_party
        self._enrolment_link_base = enrolment_link_base.rstrip("/")
        self._now = clock or (lambda: datetime.now(timezone.utc))

    # ------------------------------ enrolment ------------------------------

    async def issue_enrolment_link(self, email: str) -> str:
        """For the owner only (the dev.sh tool): a one-time link to register a passkey.

        The token travels in the URL fragment, which browsers never send to a
        server, so it stays out of access logs and Referer headers.
        """
        user = await self._admin_by_email(email)
        token = await self._ceremonies.issue_enrolment_token(user.id)
        return f"{self._enrolment_link_base}/passkeys/enrol#token={token}"

    async def begin_enrolment(self, token: str) -> PasskeyCeremonyOptions:
        user_id = await self._ceremonies.enrolment_user(token)
        if user_id is None:
            raise HTTPException(status_code=401, detail="This enrolment link is invalid or has expired")
        user = await self._active_admin(user_id)
        existing = await self._credentials.list_for_user(user.id)
        options = generate_registration_options(
            rp_id=self._rp.rp_id,
            rp_name=self._rp.name,
            user_name=user.email,
            user_id=user.id.bytes,
            user_display_name=user.name,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
            # The same authenticator cannot be registered twice.
            exclude_credentials=[self._descriptor(credential) for credential in existing],
        )
        challenge_id = await self._ceremonies.open_challenge(
            CeremonyPurpose.ENROLMENT, user.id, options.challenge, binding=self._ceremonies.token_hash(token)
        )
        return PasskeyCeremonyOptions(challenge_id=challenge_id, options=options_to_json_dict(options))

    async def finish_enrolment(
        self, token: str, challenge_id: str, credential: dict[str, JsonValue], name: str
    ) -> PasskeySummary:
        pending = await self._ceremonies.take_challenge(challenge_id, CeremonyPurpose.ENROLMENT)
        if pending is None or pending.binding != self._ceremonies.token_hash(token):
            raise HTTPException(status_code=400, detail="This enrolment has expired; open the link again")
        try:
            verified = verify_registration_response(
                credential=credential,
                expected_challenge=pending.challenge,
                expected_rp_id=self._rp.rp_id,
                expected_origin=list(self._rp.origins),
                require_user_verification=True,
            )
        except WebAuthnException as exc:
            raise HTTPException(status_code=400, detail=f"The passkey could not be registered: {exc}")

        # Spent only now: a failed attempt leaves the link usable until it expires.
        if await self._ceremonies.consume_enrolment_token(token) != pending.user_id:
            raise HTTPException(status_code=401, detail="This enrolment link is invalid or has expired")
        user = await self._active_admin(pending.user_id)
        row = WebAuthnCredential(
            user_id=user.id,
            credential_id=verified.credential_id,
            public_key=verified.credential_public_key,
            sign_count=verified.sign_count,
            transports=self._transports(credential),
            aaguid=verified.aaguid,
            backed_up=verified.credential_backed_up,
            name=name.strip(),
        )
        try:
            await self._credentials.create(row)
        except IntegrityError:
            raise HTTPException(status_code=409, detail="This passkey is already registered")
        return PasskeySummary.model_validate(row)

    # ------------------------------- sign-in -------------------------------

    async def begin_sign_in(self, email: str, password: str) -> PasskeyCeremonyOptions:
        user = await self._users.verify_credentials(email, password)
        if not self._users.is_admin(user):
            raise HTTPException(status_code=403, detail="Passkey sign-in is for admin accounts")
        credentials = await self._credentials.list_for_user(user.id)
        if not credentials:
            raise HTTPException(
                status_code=403,
                detail="No passkey is registered for this account; ask the owner for an enrolment link",
            )
        options = generate_authentication_options(
            rp_id=self._rp.rp_id,
            allow_credentials=[self._descriptor(credential) for credential in credentials],
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        challenge_id = await self._ceremonies.open_challenge(CeremonyPurpose.SIGN_IN, user.id, options.challenge)
        return PasskeyCeremonyOptions(challenge_id=challenge_id, options=options_to_json_dict(options))

    async def finish_sign_in(
        self, challenge_id: str, credential: dict[str, JsonValue]
    ) -> tuple[CurrentUserInfo, IssuedSession]:
        pending = await self._ceremonies.take_challenge(challenge_id, CeremonyPurpose.SIGN_IN)
        if pending is None:
            raise HTTPException(status_code=401, detail="This sign-in has expired; start again")
        try:
            raw_id = parse_authentication_credential_json(credential).raw_id
        except WebAuthnException:
            raise HTTPException(status_code=400, detail="Malformed passkey response")

        # Only a passkey of the user who passed the password check counts.
        stored = await self._credentials.lock_for_sign_in(pending.user_id, raw_id)
        if stored is None:
            raise HTTPException(status_code=401, detail="Passkey sign-in failed")
        try:
            verified = verify_authentication_response(
                credential=credential,
                expected_challenge=pending.challenge,
                expected_rp_id=self._rp.rp_id,
                expected_origin=list(self._rp.origins),
                credential_public_key=stored.public_key,
                credential_current_sign_count=stored.sign_count,
                require_user_verification=True,
            )
        except WebAuthnException:
            # Which check failed (signature, origin, counter...) is for the logs
            # an operator reads, not for the caller.
            raise HTTPException(status_code=401, detail="Passkey sign-in failed")

        await self._credentials.record_use(stored, verified.new_sign_count, self._now())
        # The account is read again: it may have been deactivated or demoted
        # between the password step and this one.
        user = await self._active_admin(pending.user_id)
        session = await self._users.session_issuer.issue(user, [AuthMethod.PASSWORD, AuthMethod.PASSKEY])
        await self._users.record_sign_in(user.email, user.id)
        return CurrentUserInfo(email=user.email, id=user.id, role=user.role), session

    # --------------------------- owner operations --------------------------

    async def list_passkeys(self, email: str) -> list[PasskeySummary]:
        user = await self._admin_by_email(email)
        return [PasskeySummary.model_validate(row) for row in await self._credentials.list_for_user(user.id)]

    async def revoke_passkey(self, email: str, passkey_id: UUID) -> None:
        """Remove a passkey (a lost device) and end every session the admin has.

        The sessions go too: one may be running on the lost device itself.
        """
        user = await self._admin_by_email(email)
        if not await self._credentials.delete_for_user(user.id, passkey_id):
            raise HTTPException(status_code=404, detail="No such passkey for this account")
        await self._users.end_all_sessions(user)

    # ------------------------------- helpers -------------------------------

    async def _admin_by_email(self, email: str) -> User:
        user = await self._users.repository.get_by_field("email", email.strip().lower())
        if user is None or not self._users.is_admin(user):
            raise HTTPException(status_code=404, detail=f"No admin account for {email}")
        return user

    async def _active_admin(self, user_id: UUID) -> User:
        user = await self._users.repository.get_by_id(user_id)
        if user is None or not user.is_active or not self._users.is_admin(user):
            raise HTTPException(status_code=403, detail="This account cannot use admin passkeys")
        return user

    @staticmethod
    def _descriptor(credential: WebAuthnCredential) -> PublicKeyCredentialDescriptor:
        transports = [AuthenticatorTransport(t) for t in credential.transports if t in _KNOWN_TRANSPORTS]
        return PublicKeyCredentialDescriptor(id=credential.credential_id, transports=transports or None)

    @staticmethod
    def _transports(credential: dict[str, JsonValue]) -> list[str]:
        """The transports the browser reported for a new credential, if any."""
        response = credential.get("response")
        if not isinstance(response, dict):
            return []
        transports = response.get("transports")
        if not isinstance(transports, list):
            return []
        return [t for t in transports if isinstance(t, str) and t in _KNOWN_TRANSPORTS]


_KNOWN_TRANSPORTS = frozenset(transport.value for transport in AuthenticatorTransport)
