"""product variant option names

products.variant_option_names: what each dash-separated part of a variant key
names, in order (the supplier's ["Size", "Color"] for "M-Red"). Filled by the
next supplier sync; empty until then.

Revision ID: d4a7e2c9b1f8
Revises: c2f8a4d1e7b9
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4a7e2c9b1f8"
down_revision: Union[str, Sequence[str], None] = "c2f8a4d1e7b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "variant_option_names",
            postgresql.ARRAY(sa.String(length=50)),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "variant_option_names")
