"""supplier import reliability

Revision ID: c31a7d9e2f40
Revises: a04c24166d7a
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c31a7d9e2f40"
down_revision: Union[str, Sequence[str], None] = "a04c24166d7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("idx_product_pid", table_name="products")
    op.add_column("products", sa.Column("supplier_id", sa.String(length=100), nullable=True))
    op.add_column("products", sa.Column("supplier_category_id", sa.String(length=200), nullable=True))
    op.create_index("idx_product_pid", "products", ["pid"], unique=False)
    op.create_index("idx_product_supplier_pid", "products", ["supplier_id", "pid"], unique=True)

    op.add_column(
        "product_variants",
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "supplier_import_batches",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("supplier_id", sa.String(length=100), nullable=False),
        sa.Column("fetch_id", sa.UUID(), nullable=False),
        sa.Column("batch_id", sa.UUID(), nullable=False),
        sa.Column("batch_number", sa.Integer(), nullable=False),
        sa.Column("total_batches", sa.Integer(), nullable=False),
        sa.Column("imported", sa.Integer(), nullable=False),
        sa.Column("updated", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("date_created", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("date_updated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_supplier_import_batch_event_id"),
        sa.UniqueConstraint("supplier_id", "batch_id", name="uq_supplier_import_batch_supplier_batch"),
    )
    op.create_index("idx_supplier_import_batch_fetch_id", "supplier_import_batches", ["fetch_id"])

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_created", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("date_updated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index("idx_outbox_events_event_type", "outbox_events", ["event_type"])
    op.create_index("idx_outbox_events_processed", "outbox_events", ["processed"])
    op.create_index("idx_outbox_events_retry", "outbox_events", ["processed", "next_retry_at"])


def downgrade() -> None:
    op.drop_index("idx_outbox_events_retry", table_name="outbox_events")
    op.drop_index("idx_outbox_events_processed", table_name="outbox_events")
    op.drop_index("idx_outbox_events_event_type", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index("idx_supplier_import_batch_fetch_id", table_name="supplier_import_batches")
    op.drop_table("supplier_import_batches")
    op.drop_column("product_variants", "active")
    op.drop_index("idx_product_supplier_pid", table_name="products")
    op.drop_index("idx_product_pid", table_name="products")
    op.drop_column("products", "supplier_category_id")
    op.drop_column("products", "supplier_id")
    op.create_index("idx_product_pid", "products", ["pid"], unique=True)
