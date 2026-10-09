"""catalogue image mirrors

catalogue_image_mirrors: supplier (CJ) images copied into the catalogue
object store, one row per source URL. Once a row is mirrored, products,
product_images and product_variants hold its object key instead of the URL.

Revision ID: c2f8a4d1e7b9
Revises: 9b4d2e7f1a63
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c2f8a4d1e7b9"
down_revision: Union[str, Sequence[str], None] = "9b4d2e7f1a63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalogue_image_mirrors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=True),
        sa.Column("content_type", sa.String(length=64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mirrored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_created", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("date_updated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'mirrored', 'failed')", name="ck_catalogue_image_mirrors_status"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_catalogue_image_mirrors_source_url", "catalogue_image_mirrors", ["source_url"], unique=True
    )
    op.create_index("idx_catalogue_image_mirrors_status", "catalogue_image_mirrors", ["status"])


def downgrade() -> None:
    op.drop_index("idx_catalogue_image_mirrors_status", table_name="catalogue_image_mirrors")
    op.drop_index("idx_catalogue_image_mirrors_source_url", table_name="catalogue_image_mirrors")
    op.drop_table("catalogue_image_mirrors")
