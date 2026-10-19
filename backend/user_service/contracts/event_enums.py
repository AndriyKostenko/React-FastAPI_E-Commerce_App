from enum import StrEnum


class UserEvents(StrEnum):
    USER_REGISTERED = "user.registered"
    USER_EMAIL_VERIFIED = "user.email.verified"
    USER_LOGGED_IN = "user.logged.in"
    USER_PASSWORD_RESET_REQUEST = "user.password.reset.request"
    USER_PASSWORD_RESET_SUCCESS = "user.password.reset.success"
    # Someone registered with an email that already has a verified account.
    USER_REGISTRATION_EXISTING = "user.registration.existing"
    USER_DELETED = "user.deleted"
