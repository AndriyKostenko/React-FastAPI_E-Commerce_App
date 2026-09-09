"""baseline order schema

The schema order_service had before it owned any migrations, when tables were
bootstrapped by ``init_db``/``create_all``. It is reproduced here exactly so an
existing database can be brought under Alembic with

    alembic stamp b1f0c9d24a70

and then upgraded normally. A fresh database runs this migration for real.

Revision ID: b1f0c9d24a70
Revises:
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID


revision: str = "b1f0c9d24a70"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamp_columns() -> list[sa.Column]:
    """The TimestampMixin pair every table in this service carries."""
    return [
        sa.Column(
            "date_created",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "date_updated",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "order_addresses",
        sa.Column("id", PostgresUUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PostgresUUID(as_uuid=True), nullable=False),
        sa.Column("street", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("province", sa.String(), nullable=True),
        sa.Column("postal_code", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("country_code", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_order_addresses_user_id", "order_addresses", ["user_id"])

    op.create_table(
        "orders",
        sa.Column("id", PostgresUUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PostgresUUID(as_uuid=True), nullable=False),
        sa.Column("user_email", sa.String(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("delivery_status", sa.String(), nullable=False),
        sa.Column("payment_intent_id", sa.String(), nullable=True),
        sa.Column("address_id", PostgresUUID(as_uuid=True), nullable=False),
        sa.Column("cj_order_number", sa.String(), nullable=True),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_intent_id"),
        sa.ForeignKeyConstraint(["address_id"], ["order_addresses.id"]),
    )
    op.create_index("idx_users_id", "orders", ["user_id"])
    op.create_index("idx_orders_status", "orders", ["status"])
    op.create_index("idx_orders_delivery_status", "orders", ["delivery_status"])
    op.create_index("idx_orders_date_created", "orders", ["date_created"])

    op.create_table(
        "order_items",
        sa.Column("id", PostgresUUID(as_uuid=True), nullable=False),
        sa.Column("order_id", PostgresUUID(as_uuid=True), nullable=False),
        sa.Column("product_id", PostgresUUID(as_uuid=True), nullable=False),
        sa.Column("variant_id", PostgresUUID(as_uuid=True), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
    )
    op.create_index("idx_order_items_order_id", "order_items", ["order_id"])
    op.create_index("idx_order_items_product_id", "order_items", ["product_id"])
    op.create_index("idx_order_items_variant_id", "order_items", ["variant_id"])

    op.create_table(
        "order_line_fulfillments",
        sa.Column("id", PostgresUUID(as_uuid=True), nullable=False),
        sa.Column("order_item_id", PostgresUUID(as_uuid=True), nullable=False),
        sa.Column("fulfillment_type", sa.String(length=20), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("supplier_id", sa.String(length=100), nullable=True),
        sa.Column("customization", sa.JSON(), nullable=True),
        sa.Column("variant_snapshot", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_item_id"),
        sa.ForeignKeyConstraint(
            ["order_item_id"], ["order_items.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "idx_order_line_fulfillments_order_item",
        "order_line_fulfillments",
        ["order_item_id"],
        unique=True,
    )
    op.create_index(
        "idx_order_line_fulfillments_type",
        "order_line_fulfillments",
        ["fulfillment_type"],
    )

    op.create_table(
        "custom_production_jobs",
        sa.Column("id", PostgresUUID(as_uuid=True), nullable=False),
        sa.Column("order_id", PostgresUUID(as_uuid=True), nullable=False),
        sa.Column("order_item_id", PostgresUUID(as_uuid=True), nullable=False),
        sa.Column("specifications", sa.JSON(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_item_id"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["order_item_id"], ["order_items.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("idx_custom_production_order", "custom_production_jobs", ["order_id"])
    op.create_index("idx_custom_production_status", "custom_production_jobs", ["status"])

    op.create_table(
        "order_saga_states",
        sa.Column("order_id", PostgresUUID(as_uuid=True), nullable=False),
        sa.Column("inventory_status", sa.String(length=30), nullable=False),
        sa.Column("payment_status", sa.String(length=30), nullable=False),
        sa.Column("fulfillment_status", sa.String(length=30), nullable=False),
        sa.Column("cancellation_reason", sa.String(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("order_id"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", PostgresUUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_outbox_events_event_type", "outbox_events", ["event_type"])
    op.create_index("idx_outbox_events_processed", "outbox_events", ["processed"])
    op.create_index(
        "idx_outbox_events_retry", "outbox_events", ["processed", "next_retry_at"]
    )


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("order_saga_states")
    op.drop_table("custom_production_jobs")
    op.drop_table("order_line_fulfillments")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("order_addresses")
