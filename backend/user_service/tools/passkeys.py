"""
Admin passkeys, for the owner (``./local/dev.sh admin ...``).

    enrol  <email>               print a one-time link to register a passkey
    list   <email>               the admin's passkeys
    revoke <email> <passkey-id>  remove one (a lost device) and end the admin's sessions

This is the only way a passkey is first registered, and the recovery path:
it needs this machine's Vault identity and database, which a stolen password
does not give anyone.
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import HTTPException

from database_layer.user_repository import UserRepository
from database_layer.webauthn_credential_repository import WebAuthnCredentialRepository
from managers import SERVICE_NAME, ResourceManager, settings
from models.outbox_models import OutboxEvent
from service_layer.outbox_event_service import OutboxEventService
from service_layer.passkey_ceremony_store import PasskeyCeremonyStore
from service_layer.passkey_service import PasskeyService, RelyingParty
from service_layer.user_service import UserService
from shared.database_layer.outbox_repository import OutboxRepository


async def _with_passkey_service(action: Callable[[PasskeyService], Awaitable[int]]) -> int:
    # SQL echo (DEBUG_MODE) would bury the link in log lines.
    quiet = settings.model_copy(update={"DEBUG_MODE": False})
    async with ResourceManager(app_settings=quiet) as resources:
        async with resources.database.transaction() as session:
            user_service = UserService(
                repository=UserRepository(session=session),
                password_manager=resources.password_manager,
                token_manager=resources.token_manager,
                cache_manager=resources.cache,
                outbox_event_service=OutboxEventService(
                    repository=OutboxRepository(session=session, model=OutboxEvent)
                ),
                http_client=resources.google_http_client,
                settings=resources.settings,
                session_registry=resources.session_registry,
            )
            service = PasskeyService(
                user_service=user_service,
                credentials=WebAuthnCredentialRepository(session=session),
                ceremonies=PasskeyCeremonyStore(
                    cache=resources.cache,
                    challenge_ttl_seconds=resources.settings.PASSKEY_CHALLENGE_TTL_SECONDS,
                    enrolment_ttl_seconds=resources.settings.PASSKEY_ENROLMENT_TTL_MINUTES * 60,
                ),
                relying_party=RelyingParty.from_settings(resources.settings),
                enrolment_link_base=resources.settings.ADMIN_PANEL_URL,
            )
            return await action(service)


async def _enrol(service: PasskeyService, email: str) -> int:
    link = await service.issue_enrolment_link(email)
    print(f"One-time passkey enrolment link for {email} (valid 15 minutes, single use):")
    print(f"  {link}")
    print("Open it in the browser on the device the passkey will live on.")
    return 0


async def _list(service: PasskeyService, email: str) -> int:
    passkeys = await service.list_passkeys(email)
    if not passkeys:
        print(f"{email} has no passkey: it cannot sign in to the admin panel.")
        return 0
    for passkey in passkeys:
        last_used = passkey.last_used_at.isoformat(timespec="seconds") if passkey.last_used_at else "never"
        synced = "synced" if passkey.backed_up else "device-bound"
        print(f"{passkey.id}  {passkey.name:<24} {synced:<13} added {passkey.date_created:%Y-%m-%d}  last used {last_used}")
    return 0


async def _revoke(service: PasskeyService, email: str, passkey_id: UUID) -> int:
    await service.revoke_passkey(email, passkey_id)
    print(f"Removed passkey {passkey_id} and ended every session of {email}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="dev.sh admin", description="Admin passkeys")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("enrol").add_argument("email")
    commands.add_parser("list").add_argument("email")
    revoke = commands.add_parser("revoke")
    revoke.add_argument("email")
    revoke.add_argument("passkey_id", type=UUID)
    args = parser.parse_args()
    # The service's lifecycle logging (connections opened and closed) is noise here.
    logging.getLogger(SERVICE_NAME).setLevel(logging.ERROR)

    actions: dict[str, Callable[[PasskeyService], Awaitable[int]]] = {
        "enrol": lambda service: _enrol(service, args.email),
        "list": lambda service: _list(service, args.email),
        "revoke": lambda service: _revoke(service, args.email, args.passkey_id),
    }
    try:
        return asyncio.run(_with_passkey_service(actions[args.command]))
    except HTTPException as exc:
        print(exc.detail, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
