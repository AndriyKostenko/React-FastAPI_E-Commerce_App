"""
cj_order_attempts.user_email is stored encrypted and read back in plain text,
against the real supplier test database. It may be empty; nothing looks an
attempt up by address.
"""

from collections.abc import AsyncGenerator
from logging import getLogger
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from enums.cj_order_enums import CJOrderAttemptStatus
from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from models.base import Base
from models.cj_order_attempt_models import CJOrderAttempt
from settings import get_settings

BUYER = "ann.lee@example.com"


@pytest.fixture
async def db() -> AsyncGenerator[TestDatabaseSessionManager, None]:
    manager = TestDatabaseSessionManager(
        database_url=get_settings().SUPPLIER_SERVICE_TEST_DATABASE_URL, logger=getLogger("test")
    )
    await manager.init_db(Base.metadata)
    yield manager
    await manager.truncate_all_tables(Base.metadata)
    await manager.close()


async def test_the_address_is_stored_encrypted_and_read_back(db: TestDatabaseSessionManager) -> None:
    order_with, order_without = uuid4(), uuid4()
    async with db.transaction() as session:
        session.add_all([
            CJOrderAttempt(order_id=order_with, user_id=uuid4(), user_email=BUYER, status=CJOrderAttemptStatus.CREATING),
            CJOrderAttempt(order_id=order_without, user_id=uuid4(), user_email=None, status=CJOrderAttemptStatus.CREATING),
        ])
    async with db.transaction() as session:
        stored = dict((await session.execute(text("SELECT order_id, user_email FROM cj_order_attempts"))).all())
        attempts = {a.order_id: a for a in (await session.execute(select(CJOrderAttempt))).scalars()}
    assert stored[order_with].startswith("e1.") and "ann" not in stored[order_with].lower()
    assert stored[order_without] is None
    assert attempts[order_with].user_email == BUYER
    assert attempts[order_without].user_email is None
