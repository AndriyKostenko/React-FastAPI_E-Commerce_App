"""
users.email is stored encrypted; email_hash, a keyed hash, finds an account.
Against the real user test database: what a row holds, the lookups the service
makes by address, one account per address, the migration that encrypts
existing rows, and the admin users list.
"""

from collections.abc import AsyncGenerator

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select, text

from database_layer.user_repository import UserRepository
from infrastructure.database_layer.encrypted_email import EncryptedColumnComparisonError, EncryptedEmailMigration
from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from infrastructure.utils.email_cipher import EmailCipher
from models.base import Base
from models.user_models import User
from settings import get_test_settings

test_settings = get_test_settings()

ANN = "ann.lee@example.com"
BOB = "bob.stone@example.com"


def _user(name: str, email: str) -> User:
    return User(name=name, email=email, hashed_password=None, role="user",
                is_verified=True, is_active=True, token_version=1)


@pytest.fixture
async def users(test_database_session_manager: TestDatabaseSessionManager) -> AsyncGenerator[TestDatabaseSessionManager, None]:
    await test_database_session_manager.init_db(Base.metadata)
    async with test_database_session_manager.transaction() as session:
        session.add_all([_user("Ann Lee", ANN), _user("Bob Stone", BOB)])
    yield test_database_session_manager
    await test_database_session_manager.truncate_all_tables(Base.metadata)


async def _stored(manager: TestDatabaseSessionManager, name: str) -> tuple[str, str]:
    async with manager.transaction() as session:
        row = (await session.execute(
            text("SELECT email, email_hash FROM users WHERE name = :name"), {"name": name}
        )).one()
        return row.email, row.email_hash


async def _found(manager: TestDatabaseSessionManager, email: str) -> str | None:
    async with manager.transaction() as session:
        user = await UserRepository(session).get_by_field("email", email)
        return user.name if user else None


class TestStoredForm:
    async def test_the_row_holds_ciphertext_and_the_keyed_hash(self, users: TestDatabaseSessionManager) -> None:
        stored, lookup = await _stored(users, "Ann Lee")
        assert stored.startswith("e1.") and "ann" not in stored.lower()
        assert lookup == EmailCipher.current().lookup_hash(ANN)

    async def test_the_model_reads_the_address_back(self, users: TestDatabaseSessionManager) -> None:
        async with users.transaction() as session:
            ann = (await session.execute(select(User).where(User.name == "Ann Lee"))).scalar_one()
        assert ann.email == ANN


class TestLookups:
    async def test_an_address_finds_its_account_whatever_the_case(self, users: TestDatabaseSessionManager) -> None:
        assert await _found(users, ANN) == "Ann Lee"
        assert await _found(users, " Ann.Lee@Example.COM ") == "Ann Lee"

    async def test_an_unknown_address_finds_nothing(self, users: TestDatabaseSessionManager) -> None:
        assert await _found(users, "nobody@example.com") is None

    async def test_a_second_account_for_an_address_is_refused(self, users: TestDatabaseSessionManager) -> None:
        # The unique hash decides, as the unique email column did.
        async with users.transaction() as session:
            assert await UserRepository(session).add_unless_email_taken(_user("Ann Again", "ANN.LEE@example.com")) is None

    async def test_changing_the_address_moves_the_lookup(self, users: TestDatabaseSessionManager) -> None:
        async with users.transaction() as session:
            repository = UserRepository(session)
            ann = await repository.get_by_field("email", ANN)
            await repository.update_by_id(ann.id, {"email": "ann.new@example.com"})
        assert await _found(users, ANN) is None
        assert await _found(users, "ann.new@example.com") == "Ann Lee"
        assert (await _stored(users, "Ann Lee"))[1] == EmailCipher.current().lookup_hash("ann.new@example.com")

    @pytest.mark.parametrize(
        "comparison",
        [
            lambda: User.email.ilike("%ann%"),
            lambda: User.email.contains("example"),
            lambda: User.email.in_([ANN, BOB]),
            lambda: User.email > "a",
        ],
    )
    def test_anything_but_equality_is_refused(self, comparison) -> None:
        # Against ciphertext it would quietly match nothing.
        with pytest.raises(EncryptedColumnComparisonError):
            comparison()


class TestMigration:
    async def test_plain_rows_are_encrypted_in_place_and_decrypt_back(self, users: TestDatabaseSessionManager) -> None:
        # A row as it was before the migration: plain address, no hash yet.
        async with users.transaction() as session:
            await session.execute(text(
                "INSERT INTO users (id, name, email, email_hash, role, is_active, is_verified, token_version) "
                "VALUES (gen_random_uuid(), 'Old Timer', 'old.timer@example.com', 'pending', 'user', true, true, 1)"
            ))

        def migration(sync_session) -> EncryptedEmailMigration:
            return EncryptedEmailMigration(sync_session.connection(), "users", "email", lookup="email_hash")

        async with users.transaction() as session:
            # Only the plain row: rows already encrypted are left alone.
            assert await session.run_sync(lambda s: migration(s).encrypt_rows()) == 1
        assert await _found(users, "old.timer@example.com") == "Old Timer"

        async with users.transaction() as session:
            assert await session.run_sync(lambda s: migration(s).decrypt_rows()) == 3
        assert (await _stored(users, "Old Timer"))[0] == "old.timer@example.com"
        assert (await _stored(users, "Ann Lee"))[0] == ANN


class TestAdminUsersList:
    async def test_a_whole_address_finds_its_account(self, users: TestDatabaseSessionManager, integration_client: AsyncClient) -> None:
        response = await integration_client.get(f"{test_settings.API}/users", params={"search_term": "ANN.LEE@example.com"})
        assert response.status_code == status.HTTP_200_OK
        assert [user["email"] for user in response.json()] == [ANN]

    async def test_part_of_an_address_no_longer_matches(self, users: TestDatabaseSessionManager, integration_client: AsyncClient) -> None:
        # Both addresses end in example.com; only names and phones are searched for parts.
        response = await integration_client.get(f"{test_settings.API}/users", params={"search_term": "example.com"})
        assert response.json() == []
        response = await integration_client.get(f"{test_settings.API}/users", params={"search_term": "Stone"})
        assert [user["email"] for user in response.json()] == [BOB]

    async def test_the_email_filter_is_exact(self, users: TestDatabaseSessionManager, integration_client: AsyncClient) -> None:
        response = await integration_client.get(f"{test_settings.API}/users", params={"email": BOB})
        assert [user["name"] for user in response.json()] == ["Bob Stone"]

    async def test_sorting_by_email_is_refused(self, integration_client: AsyncClient) -> None:
        response = await integration_client.get(f"{test_settings.API}/users", params={"sort_by": "email"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_the_admin_schema_hides_the_lookup_hash(self, integration_client: AsyncClient) -> None:
        response = await integration_client.get(f"{test_settings.API}/admin/schema/users")
        paths = [field["path"] for field in response.json()["fields"]]
        assert "email" in paths and "email_hash" not in paths
