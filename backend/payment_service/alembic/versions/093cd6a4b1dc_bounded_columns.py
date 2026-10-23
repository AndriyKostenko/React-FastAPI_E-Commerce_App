"""bounded columns: lengths on every string column, CHECKs on counts and money

Revision ID: 093cd6a4b1dc
Revises: c5e2a8d4b716
Create Date: 2026-10-21 17:51:06.000000

Every bound is at or above the request schema that writes the column
(contracts.limits) and above the longest value stored when it was written.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '093cd6a4b1dc'
down_revision: Union[str, Sequence[str], None] = 'c5e2a8d4b716'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('outbox_events', 'event_type', type_=sa.String(length=64), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('outbox_events', 'last_error', type_=sa.String(length=2000), existing_type=sa.Text(), existing_nullable=True)
    op.create_check_constraint('ck_outbox_events_attempts', 'outbox_events', 'attempts >= 0')
    op.alter_column('payment_disputes', 'stripe_dispute_id', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('payment_disputes', 'currency', type_=sa.String(length=3), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('payment_disputes', 'reason', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('payment_disputes', 'status', type_=sa.String(length=64), existing_type=sa.String(), existing_nullable=False)
    op.create_check_constraint('ck_payment_disputes_amount_cents', 'payment_disputes', 'amount_cents >= 0')
    op.alter_column('payment_refunds', 'reason', type_=sa.String(length=5000), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('payment_refunds', 'status', type_=sa.String(length=64), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('payment_refunds', 'stripe_refund_id', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('payment_refunds', 'failure_reason', type_=sa.String(length=5000), existing_type=sa.String(), existing_nullable=True)
    op.create_check_constraint('ck_payment_refunds_amount_cents', 'payment_refunds', 'amount_cents >= 0')
    op.alter_column('payments', 'user_email', type_=sa.String(length=320), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('payments', 'stripe_payment_intent_id', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('payments', 'currency', type_=sa.String(length=3), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('payments', 'status', type_=sa.String(length=64), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('payments', 'failure_reason', type_=sa.String(length=5000), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('payments', 'tax_calculation_id', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('payments', 'tax_transaction_id', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=True)
    op.create_check_constraint('ck_payments_amounts', 'payments', 'amount >= 0 AND refunded_cents >= 0 AND capture_reduction_cents >= 0')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_payments_amounts', 'payments', type_='check')
    op.alter_column('payments', 'tax_transaction_id', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=True)
    op.alter_column('payments', 'tax_calculation_id', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=True)
    op.alter_column('payments', 'failure_reason', type_=sa.String(), existing_type=sa.String(length=5000), existing_nullable=True)
    op.alter_column('payments', 'status', type_=sa.String(), existing_type=sa.String(length=64), existing_nullable=False)
    op.alter_column('payments', 'currency', type_=sa.String(), existing_type=sa.String(length=3), existing_nullable=False)
    op.alter_column('payments', 'stripe_payment_intent_id', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=False)
    op.alter_column('payments', 'user_email', type_=sa.String(), existing_type=sa.String(length=320), existing_nullable=False)
    op.drop_constraint('ck_payment_refunds_amount_cents', 'payment_refunds', type_='check')
    op.alter_column('payment_refunds', 'failure_reason', type_=sa.String(), existing_type=sa.String(length=5000), existing_nullable=True)
    op.alter_column('payment_refunds', 'stripe_refund_id', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=True)
    op.alter_column('payment_refunds', 'status', type_=sa.String(), existing_type=sa.String(length=64), existing_nullable=False)
    op.alter_column('payment_refunds', 'reason', type_=sa.String(), existing_type=sa.String(length=5000), existing_nullable=False)
    op.drop_constraint('ck_payment_disputes_amount_cents', 'payment_disputes', type_='check')
    op.alter_column('payment_disputes', 'status', type_=sa.String(), existing_type=sa.String(length=64), existing_nullable=False)
    op.alter_column('payment_disputes', 'reason', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=False)
    op.alter_column('payment_disputes', 'currency', type_=sa.String(), existing_type=sa.String(length=3), existing_nullable=False)
    op.alter_column('payment_disputes', 'stripe_dispute_id', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=False)
    op.drop_constraint('ck_outbox_events_attempts', 'outbox_events', type_='check')
    op.alter_column('outbox_events', 'last_error', type_=sa.Text(), existing_type=sa.String(length=2000), existing_nullable=True)
    op.alter_column('outbox_events', 'event_type', type_=sa.String(), existing_type=sa.String(length=64), existing_nullable=False)
