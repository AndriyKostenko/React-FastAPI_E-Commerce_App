"""Add the user token-version counter used for session invalidation.

Revision ID: 20260813_01
Revises:
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("users", "token_version", server_default=None)
    op.alter_column("users", "hashed_password", existing_type=sa.String(), nullable=True)
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("users", "role", existing_type=sa.String(), nullable=False, server_default="user")
    op.create_check_constraint("ck_users_role", "users", "role IN ('user', 'admin')")
    op.add_column("outbox_events", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("outbox_events", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("outbox_events", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_outbox_events_retry", "outbox_events", ["processed", "next_retry_at"])


def downgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_index("idx_outbox_events_retry", table_name="outbox_events")
    op.drop_column("outbox_events", "next_retry_at")
    op.drop_column("outbox_events", "last_error")
    op.drop_column("outbox_events", "attempts")
    op.alter_column("users", "role", existing_type=sa.String(), nullable=True, server_default=None)
    op.drop_column("users", "deleted_at")
    op.alter_column("users", "hashed_password", existing_type=sa.String(), nullable=False)
    op.drop_column("users", "token_version")
