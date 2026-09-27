"""customer returns

return_requests: a customer asking to give back delivered units.
order_line_fulfillments.delivered_at: the return window runs from here;
lines already delivered take their last update as the best estimate.
order_refunds.return_request_id: the return a refund pays out.

Revision ID: e7b3c1f9a482
Revises: d4a9c6e1f305
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e7b3c1f9a482"
down_revision: Union[str, Sequence[str], None] = "d4a9c6e1f305"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "return_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("fault", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("lines", sa.JSON(), nullable=False),
        sa.Column("photos", sa.JSON(), nullable=False),
        sa.Column("refund_shipping", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("admin_note", sa.String(1000), nullable=True),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_created", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("date_updated", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_return_requests_order_id", "return_requests", ["order_id"])
    op.create_index("ix_return_requests_user_id", "return_requests", ["user_id"])
    op.create_index("idx_return_requests_status", "return_requests", ["status"])

    op.add_column(
        "order_line_fulfillments",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE order_line_fulfillments "
        "SET delivered_at = COALESCE(date_updated, date_created) "
        "WHERE status = 'delivered'"
    )

    op.add_column(
        "order_refunds",
        sa.Column("return_request_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_order_refunds_return_request_id", "order_refunds", "return_requests",
        ["return_request_id"], ["id"],
    )
    op.create_index("ix_order_refunds_return_request_id", "order_refunds", ["return_request_id"])


def downgrade() -> None:
    op.drop_index("ix_order_refunds_return_request_id", table_name="order_refunds")
    op.drop_constraint("fk_order_refunds_return_request_id", "order_refunds", type_="foreignkey")
    op.drop_column("order_refunds", "return_request_id")
    op.drop_column("order_line_fulfillments", "delivered_at")
    op.drop_index("idx_return_requests_status", table_name="return_requests")
    op.drop_index("ix_return_requests_user_id", table_name="return_requests")
    op.drop_index("ix_return_requests_order_id", table_name="return_requests")
    op.drop_table("return_requests")
