from enum import StrEnum


class AuthCookies(StrEnum):
    ACCESS_COOKIE = "access_token"
    REFRESH_COOKIE = "refresh_token"
