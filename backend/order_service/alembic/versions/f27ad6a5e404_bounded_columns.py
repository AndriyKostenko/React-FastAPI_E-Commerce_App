"""bounded columns: lengths on every string column, CHECKs on counts and money

Revision ID: f27ad6a5e404
Revises: f3a8d2c6b519
Create Date: 2026-10-21 17:51:06.000000

Every bound is at or above the request schema that writes the column
(contracts.limits) and above the longest value stored when it was written.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f27ad6a5e404'
down_revision: Union[str, Sequence[str], None] = 'f3a8d2c6b519'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('custom_production_jobs', 'notes', type_=sa.String(length=10000), existing_type=sa.Text(), existing_nullable=True)
    op.create_check_constraint('ck_custom_production_jobs_quantity', 'custom_production_jobs', 'quantity BETWEEN 1 AND 99')
    op.alter_column('order_addresses', 'street', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('order_addresses', 'city', type_=sa.String(length=100), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('order_addresses', 'province', type_=sa.String(length=64), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('order_addresses', 'postal_code', type_=sa.String(length=10), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('order_addresses', 'country', type_=sa.String(length=64), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('order_addresses', 'country_code', type_=sa.String(length=2), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('order_addresses', 'name', type_=sa.String(length=100), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('order_addresses', 'phone', type_=sa.String(length=32), existing_type=sa.String(), existing_nullable=True)
    op.create_check_constraint('ck_order_items_quantity', 'order_items', 'quantity BETWEEN 1 AND 99')
    op.create_check_constraint('ck_order_items_price', 'order_items', 'price > 0')
    op.alter_column('order_line_fulfillments', 'supplier_id', type_=sa.String(length=255), existing_type=sa.String(length=100), existing_nullable=True)
    op.alter_column('order_line_fulfillments', 'tracking_number', type_=sa.String(length=255), existing_type=sa.String(length=100), existing_nullable=True)
    op.alter_column('order_line_fulfillments', 'carrier', type_=sa.String(length=500), existing_type=sa.String(length=100), existing_nullable=True)
    op.alter_column('order_line_fulfillments', 'tracking_url', type_=sa.String(length=2048), existing_type=sa.String(length=512), existing_nullable=True)
    op.create_check_constraint('ck_order_refunds_lines', 'order_refunds', 'json_array_length(lines) <= 50')
    op.create_check_constraint('ck_order_refunds_amounts', 'order_refunds', 'amount >= 0 AND tax_amount >= 0')
    op.alter_column('order_saga_states', 'cancellation_reason', type_=sa.String(length=5000), existing_type=sa.String(), existing_nullable=True)
    op.create_check_constraint('ck_order_saga_states_version', 'order_saga_states', 'version >= 0')
    op.alter_column('orders', 'user_email', type_=sa.String(length=320), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('orders', 'tax_calculation_id', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('orders', 'shipping_logistic_name', type_=sa.String(length=500), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('orders', 'currency', type_=sa.String(length=3), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('orders', 'status', type_=sa.String(length=30), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('orders', 'delivery_status', type_=sa.String(length=30), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('orders', 'payment_intent_id', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('orders', 'cj_order_number', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=True)
    op.create_check_constraint('ck_orders_amounts', 'orders', 'amount >= 0 AND subtotal_amount >= 0 AND shipping_amount >= 0 AND tax_amount >= 0 AND shipping_cost_usd >= 0')
    op.alter_column('outbox_events', 'event_type', type_=sa.String(length=64), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('outbox_events', 'last_error', type_=sa.String(length=2000), existing_type=sa.Text(), existing_nullable=True)
    op.create_check_constraint('ck_outbox_events_attempts', 'outbox_events', 'attempts >= 0')
    op.alter_column('return_requests', 'description', type_=sa.String(length=2000), existing_type=sa.Text(), existing_nullable=False)
    op.create_check_constraint('ck_return_requests_lines', 'return_requests', 'json_array_length(lines) BETWEEN 1 AND 50')
    op.create_check_constraint('ck_return_requests_photos', 'return_requests', 'json_array_length(photos) <= 100')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_return_requests_photos', 'return_requests', type_='check')
    op.drop_constraint('ck_return_requests_lines', 'return_requests', type_='check')
    op.alter_column('return_requests', 'description', type_=sa.Text(), existing_type=sa.String(length=2000), existing_nullable=False)
    op.drop_constraint('ck_outbox_events_attempts', 'outbox_events', type_='check')
    op.alter_column('outbox_events', 'last_error', type_=sa.Text(), existing_type=sa.String(length=2000), existing_nullable=True)
    op.alter_column('outbox_events', 'event_type', type_=sa.String(), existing_type=sa.String(length=64), existing_nullable=False)
    op.drop_constraint('ck_orders_amounts', 'orders', type_='check')
    op.alter_column('orders', 'cj_order_number', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=True)
    op.alter_column('orders', 'payment_intent_id', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=True)
    op.alter_column('orders', 'delivery_status', type_=sa.String(), existing_type=sa.String(length=30), existing_nullable=False)
    op.alter_column('orders', 'status', type_=sa.String(), existing_type=sa.String(length=30), existing_nullable=False)
    op.alter_column('orders', 'currency', type_=sa.String(), existing_type=sa.String(length=3), existing_nullable=False)
    op.alter_column('orders', 'shipping_logistic_name', type_=sa.String(), existing_type=sa.String(length=500), existing_nullable=True)
    op.alter_column('orders', 'tax_calculation_id', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=True)
    op.alter_column('orders', 'user_email', type_=sa.String(), existing_type=sa.String(length=320), existing_nullable=False)
    op.drop_constraint('ck_order_saga_states_version', 'order_saga_states', type_='check')
    op.alter_column('order_saga_states', 'cancellation_reason', type_=sa.String(), existing_type=sa.String(length=5000), existing_nullable=True)
    op.drop_constraint('ck_order_refunds_amounts', 'order_refunds', type_='check')
    op.drop_constraint('ck_order_refunds_lines', 'order_refunds', type_='check')
    op.alter_column('order_line_fulfillments', 'tracking_url', type_=sa.String(length=512), existing_type=sa.String(length=2048), existing_nullable=True)
    op.alter_column('order_line_fulfillments', 'carrier', type_=sa.String(length=100), existing_type=sa.String(length=500), existing_nullable=True)
    op.alter_column('order_line_fulfillments', 'tracking_number', type_=sa.String(length=100), existing_type=sa.String(length=255), existing_nullable=True)
    op.alter_column('order_line_fulfillments', 'supplier_id', type_=sa.String(length=100), existing_type=sa.String(length=255), existing_nullable=True)
    op.drop_constraint('ck_order_items_price', 'order_items', type_='check')
    op.drop_constraint('ck_order_items_quantity', 'order_items', type_='check')
    op.alter_column('order_addresses', 'phone', type_=sa.String(), existing_type=sa.String(length=32), existing_nullable=True)
    op.alter_column('order_addresses', 'name', type_=sa.String(), existing_type=sa.String(length=100), existing_nullable=True)
    op.alter_column('order_addresses', 'country_code', type_=sa.String(), existing_type=sa.String(length=2), existing_nullable=True)
    op.alter_column('order_addresses', 'country', type_=sa.String(), existing_type=sa.String(length=64), existing_nullable=True)
    op.alter_column('order_addresses', 'postal_code', type_=sa.String(), existing_type=sa.String(length=10), existing_nullable=True)
    op.alter_column('order_addresses', 'province', type_=sa.String(), existing_type=sa.String(length=64), existing_nullable=True)
    op.alter_column('order_addresses', 'city', type_=sa.String(), existing_type=sa.String(length=100), existing_nullable=True)
    op.alter_column('order_addresses', 'street', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=True)
    op.drop_constraint('ck_custom_production_jobs_quantity', 'custom_production_jobs', type_='check')
    op.alter_column('custom_production_jobs', 'notes', type_=sa.Text(), existing_type=sa.String(length=10000), existing_nullable=True)
