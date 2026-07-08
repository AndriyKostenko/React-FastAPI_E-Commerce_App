"""initial supplier service

Revision ID: 8478ee630ebe
Revises: 
Create Date: 2026-07-08 14:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8478ee630ebe4f4c8f6ab7825755c3c0'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'supplier_configs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('supplier_id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('provider_type', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('sync_interval_minutes', sa.Integer(), nullable=False),
        sa.Column('default_category_name', sa.String(length=100), nullable=True),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('date_created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('date_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('supplier_id'),
    )
    op.create_index('idx_supplier_config_provider_type', 'supplier_configs', ['provider_type'], unique=False)
    op.create_index('idx_supplier_config_is_active', 'supplier_configs', ['is_active'], unique=False)

    op.create_table(
        'supplier_sync_states',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('supplier_id', sa.String(length=100), nullable=False),
        sa.Column('fetch_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('products_fetched', sa.Integer(), nullable=False),
        sa.Column('products_emitted', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('date_created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('date_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['supplier_id'], ['supplier_configs.supplier_id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_supplier_sync_state_supplier_id', 'supplier_sync_states', ['supplier_id'], unique=False)
    op.create_index('idx_supplier_sync_state_status', 'supplier_sync_states', ['status'], unique=False)

    op.create_table(
        'outbox_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('date_created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('date_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id'),
    )
    op.create_index('idx_outbox_events_event_type', 'outbox_events', ['event_type'], unique=False)
    op.create_index('idx_outbox_events_processed', 'outbox_events', ['processed'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_outbox_events_processed', table_name='outbox_events')
    op.drop_index('idx_outbox_events_event_type', table_name='outbox_events')
    op.drop_table('outbox_events')

    op.drop_index('idx_supplier_sync_state_status', table_name='supplier_sync_states')
    op.drop_index('idx_supplier_sync_state_supplier_id', table_name='supplier_sync_states')
    op.drop_table('supplier_sync_states')

    op.drop_index('idx_supplier_config_is_active', table_name='supplier_configs')
    op.drop_index('idx_supplier_config_provider_type', table_name='supplier_configs')
    op.drop_table('supplier_configs')
