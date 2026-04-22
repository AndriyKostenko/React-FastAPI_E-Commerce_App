"""create_payments_and_outbox_tables

Revision ID: fcec369746e3
Revises: 
Create Date: 2026-04-22 14:44:36.145487

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fcec369746e3'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_email', sa.String(), nullable=False),
        sa.Column('stripe_payment_intent_id', sa.String(), nullable=False, unique=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('failure_reason', sa.String(), nullable=True),
        sa.Column('date_created', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('date_updated', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint('id'),
    )
    op.create_index('idx_payments_order_id', 'payments', ['order_id'])
    op.create_index('idx_payments_status', 'payments', ['status'])
    op.create_index('idx_payments_stripe_payment_intent_id', 'payments', ['stripe_payment_intent_id'])

    op.create_table(
        'payment_outbox_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('date_created', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('date_updated', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint('id'),
    )
    op.create_index('idx_outbox_events_event_type', 'payment_outbox_events', ['event_type'])
    op.create_index('idx_outbox_events_processed', 'payment_outbox_events', ['processed'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_outbox_events_processed', table_name='payment_outbox_events')
    op.drop_index('idx_outbox_events_event_type', table_name='payment_outbox_events')
    op.drop_table('payment_outbox_events')

    op.drop_index('idx_payments_stripe_payment_intent_id', table_name='payments')
    op.drop_index('idx_payments_status', table_name='payments')
    op.drop_index('idx_payments_order_id', table_name='payments')
    op.drop_table('payments')
