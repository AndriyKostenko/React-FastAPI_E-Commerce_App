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


def downgrade() -> None:
    op.alter_column("users", "hashed_password", existing_type=sa.String(), nullable=False)
    op.drop_column("users", "token_version")
