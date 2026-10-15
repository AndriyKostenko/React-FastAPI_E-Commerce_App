"""line parcel tracking

order_line_fulfillments.tracking_number / carrier / tracking_url / shipped_at:
the parcel each line left in, so the customer's order page can show tracking
for every channel. Lines of in-house jobs already posted take their job's
dispatch details; CJ and warehouse lines shipped before this have none.

Revision ID: f3a8d2c6b519
Revises: e7b3c1f9a482
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a8d2c6b519"
down_revision: Union[str, Sequence[str], None] = "e7b3c1f9a482"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("order_line_fulfillments", sa.Column("tracking_number", sa.String(length=100), nullable=True))
    op.add_column("order_line_fulfillments", sa.Column("carrier", sa.String(length=100), nullable=True))
    op.add_column("order_line_fulfillments", sa.Column("tracking_url", sa.String(length=512), nullable=True))
    op.add_column("order_line_fulfillments", sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE order_line_fulfillments AS line
           SET tracking_number = job.tracking_number,
               carrier = job.carrier,
               tracking_url = job.tracking_url,
               shipped_at = job.shipped_at
          FROM custom_production_jobs AS job
         WHERE job.order_item_id = line.order_item_id
           AND job.tracking_number IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("order_line_fulfillments", "shipped_at")
    op.drop_column("order_line_fulfillments", "tracking_url")
    op.drop_column("order_line_fulfillments", "carrier")
    op.drop_column("order_line_fulfillments", "tracking_number")
