"""
Unit tests for PasswordManager.

Uses a minimal settings stub so no .env or live services are required.
"""
from shared.managers.password_manager import PasswordManager


class TestHashPassword:
    def test_returns_non_empty_hash_string(self, password_manager: PasswordManager) -> None:
        hashed = password_manager.hash_password("my_plain_password")
        assert isinstance(hashed, str) and len(hashed) > 0

    def test_hash_differs_from_plain_text(self, password_manager: PasswordManager) -> None:
        hashed = password_manager.hash_password("my_plain_password")
        assert hashed != "my_plain_password"

    def test_same_password_produces_different_hashes(self, password_manager: PasswordManager) -> None:
        """bcrypt always uses a random salt, so two hashes must differ."""
        hash1 = password_manager.hash_password("same_password")
        hash2 = password_manager.hash_password("same_password")
        assert hash1 != hash2

    def test_hash_has_bcrypt_prefix(self, password_manager: PasswordManager) -> None:
        hashed = password_manager.hash_password("any_password")
        assert hashed.startswith("$2b$")


class TestVerifyPassword:
    def test_returns_true_for_correct_password(self, password_manager: PasswordManager) -> None:
        hashed = password_manager.hash_password("correct_password")
        assert password_manager.verify_password("correct_password", hashed) is True
        assert password_manager.verify_password("incorrect_password", hashed) is False

    def test_returns_false_for_wrong_password(self, password_manager: PasswordManager) -> None:
        hashed = password_manager.hash_password("correct_password")
        assert password_manager.verify_password("wrong_password", hashed) is False

    def test_returns_false_for_empty_input(self, password_manager: PasswordManager) -> None:
        hashed = password_manager.hash_password("some_password")
        assert password_manager.verify_password("", hashed) is False

    def test_hash_and_verify_round_trip(self, password_manager: PasswordManager) -> None:
        password = "complex!P@ssw0rd"
        hashed = password_manager.hash_password(password)
        assert password_manager.verify_password(password, hashed) is True
