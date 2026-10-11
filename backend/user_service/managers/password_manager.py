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

    def dummy_hash(self) -> str:
        """Returns a pre-computed valid hash for constant-time dummy verification."""
        # Precomputed bcrypt hash of a dummy password to burn time on invalid user logins
        return "$2b$12$e86g11Ntkc7GhpBcqoVv.eP/O3a0gY1k9wL5iZf9Lh5f3mJzKzL1a"

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verifying password against the hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
