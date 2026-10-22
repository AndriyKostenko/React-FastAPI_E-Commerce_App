"""bounded columns: lengths on every string column, CHECKs on counts and money

Revision ID: a1091c6e414a
Revises: fe33062051ed
Create Date: 2026-10-21 17:51:07.000000

Every bound is at or above the request schema that writes the column
(contracts.limits) and above the longest value stored when it was written.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1091c6e414a'
down_revision: Union[str, Sequence[str], None] = 'fe33062051ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('outbox_events', 'event_type', type_=sa.String(length=64), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('outbox_events', 'last_error', type_=sa.String(length=2000), existing_type=sa.Text(), existing_nullable=True)
    op.create_check_constraint('ck_outbox_events_attempts', 'outbox_events', 'attempts >= 0')
    op.create_check_constraint('ck_shipping_methods_estimated_days', 'shipping_methods', 'estimated_days BETWEEN 0 AND 365')
    op.create_check_constraint('ck_shipping_methods_base_cost', 'shipping_methods', 'base_cost >= 0')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_shipping_methods_base_cost', 'shipping_methods', type_='check')
    op.drop_constraint('ck_shipping_methods_estimated_days', 'shipping_methods', type_='check')
    op.drop_constraint('ck_outbox_events_attempts', 'outbox_events', type_='check')
    op.alter_column('outbox_events', 'last_error', type_=sa.Text(), existing_type=sa.String(length=2000), existing_nullable=True)
    op.alter_column('outbox_events', 'event_type', type_=sa.String(), existing_type=sa.String(length=64), existing_nullable=False)
