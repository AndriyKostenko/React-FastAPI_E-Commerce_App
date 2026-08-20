"""add supplier import progress counters

Revision ID: b19f6c4d8a21
Revises: 8478ee630ebe
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b19f6c4d8a21"
down_revision: Union[str, Sequence[str], None] = "8478ee630ebe4f4c8f6ab7825755c3c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("supplier_sync_states", sa.Column("total_batches", sa.Integer(), server_default="0", nullable=False))
    op.add_column("supplier_sync_states", sa.Column("processed_batches", sa.Integer(), server_default="0", nullable=False))
    op.add_column("supplier_sync_states", sa.Column("products_imported", sa.Integer(), server_default="0", nullable=False))
    op.add_column("supplier_sync_states", sa.Column("products_updated", sa.Integer(), server_default="0", nullable=False))
    op.add_column("supplier_sync_states", sa.Column("products_failed", sa.Integer(), server_default="0", nullable=False))
    op.add_column(
        "supplier_sync_states",
        sa.Column("acknowledged_batch_ids", sa.JSON(), server_default="[]", nullable=False),
    )
    op.create_index("idx_supplier_sync_state_fetch_id", "supplier_sync_states", ["fetch_id"], unique=True)
    op.create_index(
        "uq_supplier_sync_state_active_supplier",
        "supplier_sync_states",
        ["supplier_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('running', 'awaiting_import', 'awaiting_import_with_errors', 'importing')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_supplier_sync_state_active_supplier", table_name="supplier_sync_states")
    op.drop_index("idx_supplier_sync_state_fetch_id", table_name="supplier_sync_states")
    op.drop_column("supplier_sync_states", "products_failed")
    op.drop_column("supplier_sync_states", "acknowledged_batch_ids")
    op.drop_column("supplier_sync_states", "products_updated")
    op.drop_column("supplier_sync_states", "products_imported")
    op.drop_column("supplier_sync_states", "processed_batches")
    op.drop_column("supplier_sync_states", "total_batches")
