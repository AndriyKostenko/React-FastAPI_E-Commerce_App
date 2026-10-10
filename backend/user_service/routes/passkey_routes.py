from fastapi import APIRouter, Request, status

from dependencies.dependencies import passkey_service_dependency
from managers import rate_limited, settings
from schemas.user_schemas import (
    PasskeyCeremonyOptions,
    PasskeyEnrolmentFinish,
    PasskeyEnrolmentStart,
    PasskeySignInFinish,
    PasskeySignInStart,
    PasskeySummary,
    UserLoginDetails,
)

passkey_routes = APIRouter(tags=["passkeys"])

# Admin accounts sign in only here: POST /login refuses them. As in
# user_routes, these limits are a backstop behind the gateway's stricter ones.


@passkey_routes.post("/login/passkey/options",
                     summary="Admin sign-in, step 1: the password earns a passkey challenge",
                     response_model=PasskeyCeremonyOptions,
                     status_code=status.HTTP_200_OK)
@rate_limited(times=10, seconds=60, identifier_param="data")
async def begin_passkey_sign_in(request: Request, data: PasskeySignInStart,
                                passkey_service: passkey_service_dependency) -> PasskeyCeremonyOptions:
    return await passkey_service.begin_sign_in(data.email, data.password)


@passkey_routes.post("/login/passkey/verify",
                     summary="Admin sign-in, step 2: the passkey's signature earns the session",
                     response_model=UserLoginDetails,
                     status_code=status.HTTP_200_OK)
@rate_limited(times=10, seconds=60)
async def finish_passkey_sign_in(request: Request, data: PasskeySignInFinish,
                                 passkey_service: passkey_service_dependency) -> UserLoginDetails:
    user, session = await passkey_service.finish_sign_in(data.challenge_id, data.credential)
    return UserLoginDetails(
        access_token=session.access_token,
        token_type=settings.TOKEN_TYPE,
        token_expiry=session.access_expiry,
        refresh_token=session.refresh_token,
        refresh_token_expiry=session.refresh_expiry,
        user_id=user.id,
        user_email=user.email,
        user_role=user.role,
    )


@passkey_routes.post("/passkeys/enrolment/options",
                     summary="Passkey enrolment, step 1: options for the link's admin",
                     response_model=PasskeyCeremonyOptions,
                     status_code=status.HTTP_200_OK)
@rate_limited(times=10, seconds=60)
async def begin_passkey_enrolment(request: Request, data: PasskeyEnrolmentStart,
                                  passkey_service: passkey_service_dependency) -> PasskeyCeremonyOptions:
    return await passkey_service.begin_enrolment(data.token)


@passkey_routes.post("/passkeys/enrolment/verify",
                     summary="Passkey enrolment, step 2: register the new credential",
                     response_model=PasskeySummary,
                     status_code=status.HTTP_201_CREATED)
@rate_limited(times=10, seconds=60)
async def finish_passkey_enrolment(request: Request, data: PasskeyEnrolmentFinish,
                                   passkey_service: passkey_service_dependency) -> PasskeySummary:
    return await passkey_service.finish_enrolment(data.token, data.challenge_id, data.credential, data.name)
