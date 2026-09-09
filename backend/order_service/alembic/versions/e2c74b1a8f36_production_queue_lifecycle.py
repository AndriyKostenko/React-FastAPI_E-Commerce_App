"""production queue lifecycle

Adds the columns the in-house print queue needs to carry a job from a queued
garment to a delivered parcel: the dispatch details an operator enters, a
timestamp per step, and the flag that blocks an automatic refund when a job is
cancelled after the goods were already made or posted.

Revision ID: e2c74b1a8f36
Revises: b1f0c9d24a70
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2c74b1a8f36"
down_revision: Union[str, Sequence[str], None] = "b1f0c9d24a70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TIMESTAMPS = ("started_at", "printed_at", "shipped_at", "delivered_at", "cancelled_at")


def upgrade() -> None:
    # Dispatch details, entered by the operator when the parcel is posted.
    op.add_column(
        "custom_production_jobs",
        sa.Column("tracking_number", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "custom_production_jobs",
        sa.Column("carrier", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "custom_production_jobs",
        sa.Column("tracking_url", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "custom_production_jobs", sa.Column("notes", sa.Text(), nullable=True)
    )

    for column in _TIMESTAMPS:
        op.add_column(
            "custom_production_jobs",
            sa.Column(column, sa.DateTime(timezone=True), nullable=True),
        )

    op.add_column(
        "custom_production_jobs",
        sa.Column("cancellation_reason", sa.String(length=500), nullable=True),
    )

    # Existing rows predate the queue and have consumed nothing, so False is
    # the correct backfill as well as the correct default.
    op.add_column(
        "custom_production_jobs",
        sa.Column(
            "reconciliation_required",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_custom_production_reconciliation",
        "custom_production_jobs",
        ["reconciliation_required"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_custom_production_reconciliation", table_name="custom_production_jobs"
    )
    op.drop_column("custom_production_jobs", "reconciliation_required")
    op.drop_column("custom_production_jobs", "cancellation_reason")
    for column in reversed(_TIMESTAMPS):
        op.drop_column("custom_production_jobs", column)
    op.drop_column("custom_production_jobs", "notes")
    op.drop_column("custom_production_jobs", "tracking_url")
    op.drop_column("custom_production_jobs", "carrier")
    op.drop_column("custom_production_jobs", "tracking_number")
