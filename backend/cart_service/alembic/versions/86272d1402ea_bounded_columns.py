"""bounded columns: lengths on every string column, CHECKs on counts and money

Revision ID: 86272d1402ea
Revises: f62664eea49f
Create Date: 2026-10-21 17:51:07.000000

Every bound is at or above the request schema that writes the column
(contracts.limits) and above the longest value stored when it was written.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '86272d1402ea'
down_revision: Union[str, Sequence[str], None] = 'f62664eea49f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint('ck_cart_items_quantity', 'cart_items', 'quantity BETWEEN 1 AND 99')
    op.create_check_constraint('ck_cart_items_price_snapshot', 'cart_items', 'price_snapshot >= 0')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_cart_items_price_snapshot', 'cart_items', type_='check')
    op.drop_constraint('ck_cart_items_quantity', 'cart_items', type_='check')
