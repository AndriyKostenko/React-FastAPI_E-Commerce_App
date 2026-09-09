"""retain ordered artwork

Records which stored print files a paid order still depends on. product_service
owns the artwork object while order_service owns the reference, so without this
table a cleanup job sweeping unreferenced generation drafts cannot tell a paid
order's print file from an abandoned preview.

Revision ID: d5e8f1a3b7c9
Revises: c31a7d9e2f40
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d5e8f1a3b7c9"
down_revision: Union[str, Sequence[str], None] = "c31a7d9e2f40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "retained_artwork",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artwork_key", sa.String(length=512), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.String(length=500), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_retained_artwork_key", "retained_artwork", ["artwork_key"])
    op.create_index("idx_retained_artwork_order", "retained_artwork", ["order_id"])
    op.create_index("idx_retained_artwork_released", "retained_artwork", ["released_at"])


def downgrade() -> None:
    op.drop_index("idx_retained_artwork_released", table_name="retained_artwork")
    op.drop_index("idx_retained_artwork_order", table_name="retained_artwork")
    op.drop_index("idx_retained_artwork_key", table_name="retained_artwork")
    op.drop_table("retained_artwork")
