"""order money columns numeric

orders.amount and order_items.price were double precision. Refunds add these
up, and binary floats cannot represent most cent amounts exactly, so they are
now NUMERIC(10, 2) like the order's other money columns.

Revision ID: 8d2f6a1c3e57
Revises: 4c1d7e9a2b50
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8d2f6a1c3e57"
down_revision: Union[str, Sequence[str], None] = "4c1d7e9a2b50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (("orders", "amount"), ("order_items", "price"))


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.Numeric(10, 2),
            existing_type=sa.Float(),
            existing_nullable=False,
            postgresql_using=f"round({column}::numeric, 2)",
        )


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.Float(),
            existing_type=sa.Numeric(10, 2),
            existing_nullable=False,
            postgresql_using=f"{column}::double precision",
        )
