"""add supplier outbox retry columns

Revision ID: d72e91ab4f03
Revises: b19f6c4d8a21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d72e91ab4f03"
down_revision: Union[str, Sequence[str], None] = "b19f6c4d8a21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("outbox_events", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column(
        "outbox_events",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_outbox_events_retry",
        "outbox_events",
        ["processed", "next_retry_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_outbox_events_retry", table_name="outbox_events")
    op.drop_column("outbox_events", "next_retry_at")
    op.drop_column("outbox_events", "last_error")
    op.drop_column("outbox_events", "attempts")
