"""
A search term is matched as typed: "%" and "_" are not LIKE wildcards.
Against the real user test database, through the repository every service's
copy of ``AdvancedQueryMixin.get_all`` shares.
"""

from collections.abc import AsyncGenerator

import pytest

from database_layer.user_repository import UserRepository
from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from models.base import Base
from models.user_models import User


@pytest.fixture
async def users(test_database_session_manager: TestDatabaseSessionManager) -> AsyncGenerator[TestDatabaseSessionManager, None]:
    await test_database_session_manager.init_db(Base.metadata)
    async with test_database_session_manager.transaction() as session:
        for name, email in (("Ann_Lee", "ann.lee@example.com"), ("AnnXLee", "annxlee@example.com"),
                            ("Sale 100%", "sale@example.com"), ("Sale 1000", "sale1000@example.com")):
            session.add(User(name=name, email=email, hashed_password=None, role="user",
                             is_verified=True, is_active=True, token_version=1))
    yield test_database_session_manager
    await test_database_session_manager.truncate_all_tables(Base.metadata)


async def _names(manager: TestDatabaseSessionManager, **query) -> list[str]:
    async with manager.transaction() as session:
        found = await UserRepository(session=session).get_all(**query)
        return sorted(user.name for user in found)


@pytest.mark.parametrize(
    "term,expected",
    [
        ("n_L", ["Ann_Lee"]),  # "_" matched any character: AnnXLee came back too
        ("100%", ["Sale 100%"]),  # "%" matched anything: Sale 1000 came back too
        ("%", ["Sale 100%"]),
        ("_", ["Ann_Lee"]),
    ],
)
async def test_search_matches_wildcard_characters_literally(users, term: str, expected: list[str]) -> None:
    assert await _names(users, search_term=term, search_fields=["name"]) == expected


async def test_a_string_filter_matches_them_literally_too(users) -> None:
    assert await _names(users, filters={"name": "n_L"}) == ["Ann_Lee"]


async def test_search_is_still_case_insensitive(users) -> None:
    assert await _names(users, search_term="ann", search_fields=["name"]) == ["AnnXLee", "Ann_Lee"]
