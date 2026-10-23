"""bounded columns: lengths on every string column, CHECKs on counts and money

Revision ID: 437ed6a16519
Revises: b8e3f1a6c274
Create Date: 2026-10-21 17:51:08.000000

Every bound is at or above the request schema that writes the column
(contracts.limits) and above the longest value stored when it was written.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '437ed6a16519'
down_revision: Union[str, Sequence[str], None] = 'b8e3f1a6c274'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint('ck_cj_order_attempts_amounts', 'cj_order_attempts', 'cj_order_amount_usd >= 0 AND expected_max_amount_usd >= 0 AND payment_attempts >= 0')
    op.alter_column('outbox_events', 'event_type', type_=sa.String(length=64), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('outbox_events', 'last_error', type_=sa.String(length=2000), existing_type=sa.Text(), existing_nullable=True)
    op.create_check_constraint('ck_outbox_events_attempts', 'outbox_events', 'attempts >= 0')
    op.create_check_constraint('ck_supplier_configs_sync_interval', 'supplier_configs', 'sync_interval_minutes BETWEEN 1 AND 10080')
    op.alter_column('supplier_sync_states', 'error_message', type_=sa.String(length=5000), existing_type=sa.Text(), existing_nullable=True)
    op.create_check_constraint('ck_supplier_sync_states_counts', 'supplier_sync_states', 'products_fetched >= 0 AND products_emitted >= 0 AND total_batches >= 0 AND processed_batches >= 0 AND products_imported >= 0 AND products_updated >= 0 AND products_failed >= 0')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_supplier_sync_states_counts', 'supplier_sync_states', type_='check')
    op.alter_column('supplier_sync_states', 'error_message', type_=sa.Text(), existing_type=sa.String(length=5000), existing_nullable=True)
    op.drop_constraint('ck_supplier_configs_sync_interval', 'supplier_configs', type_='check')
    op.drop_constraint('ck_outbox_events_attempts', 'outbox_events', type_='check')
    op.alter_column('outbox_events', 'last_error', type_=sa.Text(), existing_type=sa.String(length=2000), existing_nullable=True)
    op.alter_column('outbox_events', 'event_type', type_=sa.String(), existing_type=sa.String(length=64), existing_nullable=False)
    op.drop_constraint('ck_cj_order_attempts_amounts', 'cj_order_attempts', type_='check')
