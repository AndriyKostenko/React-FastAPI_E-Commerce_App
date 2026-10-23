"""
EmailCipher: the stored form of an address and the hash that finds it.
The same module is copied into order-, payment- and supplier-service
(ci/check_copies.py keeps the copies identical).
"""

import base64
import os

import pytest

from infrastructure.database_layer.encrypted_email import EncryptedEmail
from infrastructure.utils.email_cipher import EmailCipher, EmailCipherError


def _key() -> bytes:
    return os.urandom(EmailCipher.KEY_BYTES)


@pytest.fixture
def cipher() -> EmailCipher:
    return EmailCipher(key=_key(), lookup_key=_key())


class TestEncryption:
    def test_round_trip(self, cipher: EmailCipher) -> None:
        stored = cipher.encrypt("ann.lee@example.com")
        assert cipher.decrypt(stored) == "ann.lee@example.com"

    def test_the_stored_form_never_contains_the_address(self, cipher: EmailCipher) -> None:
        stored = cipher.encrypt("ann.lee@example.com")
        assert stored.startswith("e1.")
        assert "ann" not in stored.lower() and "example" not in stored.lower()

    def test_one_address_encrypts_differently_every_time(self, cipher: EmailCipher) -> None:
        # A random nonce per write: equal ciphertexts would show which rows share an address.
        assert cipher.encrypt("ann@example.com") != cipher.encrypt("ann@example.com")

    def test_a_long_international_address_fits_the_column(self, cipher: EmailCipher) -> None:
        # 320 characters, each four bytes in UTF-8: the longest the column must hold.
        longest = "𝒶" * 300 + "@" + "𝒷" * 15 + ".com"
        assert len(longest) == 320
        assert len(cipher.encrypt(longest)) <= EncryptedEmail.STORED_LENGTH

    def test_a_tampered_value_is_refused(self, cipher: EmailCipher) -> None:
        scheme, key_id, body = cipher.encrypt("ann@example.com").split(".")
        flipped = body[:-2] + ("A" if body[-2] != "A" else "B") + body[-1]
        with pytest.raises(EmailCipherError):
            cipher.decrypt(f"{scheme}.{key_id}.{flipped}")

    def test_a_plain_address_is_refused_without_echoing_it(self, cipher: EmailCipher) -> None:
        with pytest.raises(EmailCipherError) as refused:
            cipher.decrypt("ann@example.com")
        assert "ann@example.com" not in str(refused.value)


class TestRotation:
    def test_old_keys_still_decrypt_and_the_new_key_encrypts(self) -> None:
        old, new = _key(), _key()
        written_before = EmailCipher(key=old).encrypt("ann@example.com")
        rotated = EmailCipher(key=new, old_keys=[old])
        assert rotated.decrypt(written_before) == "ann@example.com"
        assert EmailCipher(key=new).decrypt(rotated.encrypt("ann@example.com")) == "ann@example.com"

    def test_a_value_from_an_unknown_key_names_that_key(self) -> None:
        stored = EmailCipher(key=_key()).encrypt("ann@example.com")
        key_id = stored.split(".")[1]
        with pytest.raises(EmailCipherError, match=key_id):
            EmailCipher(key=_key()).decrypt(stored)


class TestLookupHash:
    def test_case_and_surrounding_space_do_not_matter(self, cipher: EmailCipher) -> None:
        assert cipher.lookup_hash(" Ann@Example.COM ") == cipher.lookup_hash("ann@example.com")

    def test_different_addresses_differ(self, cipher: EmailCipher) -> None:
        assert cipher.lookup_hash("ann@example.com") != cipher.lookup_hash("ann@example.org")

    def test_it_depends_on_the_key(self) -> None:
        # Without the key, hashing a list of known addresses matches nothing.
        one, other = EmailCipher(key=_key(), lookup_key=_key()), EmailCipher(key=_key(), lookup_key=_key())
        assert one.lookup_hash("ann@example.com") != other.lookup_hash("ann@example.com")

    def test_without_a_lookup_key_it_says_which_setting_is_missing(self) -> None:
        with pytest.raises(EmailCipherError, match="EMAIL_LOOKUP_KEY"):
            EmailCipher(key=_key()).lookup_hash("ann@example.com")


class TestKeysFromSettings:
    def test_a_key_of_the_wrong_length_is_refused_by_name(self) -> None:
        short = base64.b64encode(os.urandom(16)).decode()
        with pytest.raises(EmailCipherError, match="EMAIL_ENCRYPTION_KEY must be 32 bytes"):
            EmailCipher._decode_key(short, "EMAIL_ENCRYPTION_KEY")

    def test_a_key_that_is_not_base64_is_refused_by_name(self) -> None:
        with pytest.raises(EmailCipherError, match="EMAIL_LOOKUP_KEY is not base64"):
            EmailCipher._decode_key("not base64!", "EMAIL_LOOKUP_KEY")

    def test_this_service_has_working_keys(self) -> None:
        # The process's own cipher, from this service's settings (Vault locally, CI's run keys).
        cipher = EmailCipher.current()
        assert cipher.decrypt(cipher.encrypt("ann@example.com")) == "ann@example.com"
        assert len(cipher.lookup_hash("ann@example.com")) == 64
