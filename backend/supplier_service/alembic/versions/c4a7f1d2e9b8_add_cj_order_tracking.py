"""add cj order attempt tracking columns

The ``cj_order_attempts`` table was originally bootstrapped by
``init_db``/``create_all`` rather than by Alembic, so this revision creates it
when it is absent and only adds the columns that are actually missing. That
keeps existing dev databases and a fresh deployment on the same head.

Revision ID: c4a7f1d2e9b8
Revises: d72e91ab4f03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4a7f1d2e9b8"
down_revision: Union[str, Sequence[str], None] = "d72e91ab4f03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE = "cj_order_attempts"
POLL_INDEX = "idx_cj_order_attempt_poll"

# Column objects bind to the table they are added to, so each call site needs
# its own instances rather than a shared module-level list.
NEW_COLUMN_NAMES = (
    "user_email",
    "cj_order_status",
    "tracking_number",
    "logistic_name",
    "shipped_at",
    "delivered_at",
    "last_polled_at",
)


def _new_columns() -> list[sa.Column]:
    return [
        sa.Column("user_email", sa.String(length=320), nullable=True),
        sa.Column("cj_order_status", sa.String(length=60), nullable=True),
        sa.Column("tracking_number", sa.String(length=200), nullable=True),
        sa.Column("logistic_name", sa.String(length=200), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}


def _index_names() -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(TABLE)}


def _create_table() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("cj_order_number", sa.String(length=200), nullable=True),
        sa.Column("last_error", sa.String(length=2000), nullable=True),
        *_new_columns(),
        sa.Column(
            "date_created",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "date_updated",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index("idx_cj_order_attempt_status", TABLE, ["status"])


def upgrade() -> None:
    if TABLE not in _table_names():
        _create_table()
    else:
        existing = _column_names()
        for column in _new_columns():
            if column.name not in existing:
                op.add_column(TABLE, column)

    if POLL_INDEX not in _index_names():
        op.create_index(POLL_INDEX, TABLE, ["status", "last_polled_at"])


def downgrade() -> None:
    if TABLE not in _table_names():
        return
    if POLL_INDEX in _index_names():
        op.drop_index(POLL_INDEX, table_name=TABLE)

    existing = _column_names()
    for name in reversed(NEW_COLUMN_NAMES):
        if name in existing:
            op.drop_column(TABLE, name)
