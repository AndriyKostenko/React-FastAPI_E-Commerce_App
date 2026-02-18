from passlib.context import CryptContext

from shared.settings import Settings


class PasswordManager:
    """
    Handles password hashing and verification
    """

    def __init__(self, settings: Settings) -> None:
        self.settings: Settings = settings
        self.pwd_context: CryptContext = CryptContext(
            schemes=[self.settings.CRYPT_CONTEXT_SCHEME],
            deprecated="auto"
        )

    def hash_password(self, password: str) -> str:
        """Hashing a plain-text password"""
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verifying password against the hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
