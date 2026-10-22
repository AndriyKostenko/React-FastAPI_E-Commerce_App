"""encrypted emails: orders.user_email stored encrypted, lookup hash beside it

Revision ID: b158124ae611
Revises: f27ad6a5e404
Create Date: 2026-10-22 12:00:00.000000

Existing addresses are encrypted in place with this service's
EMAIL_ENCRYPTION_KEY (EncryptedEmailMigration), so the key must be in its
Vault path before this runs; the downgrade decrypts them with the same key.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from infrastructure.database_layer.encrypted_email import EncryptedEmail, EncryptedEmailMigration


# revision identifiers, used by Alembic.
revision: str = 'b158124ae611'
down_revision: Union[str, Sequence[str], None] = 'f27ad6a5e404'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('orders', sa.Column('user_email_hash', sa.String(length=EncryptedEmail.LOOKUP_LENGTH), nullable=True))
    op.alter_column('orders', 'user_email', type_=sa.String(length=EncryptedEmail.STORED_LENGTH), existing_type=sa.String(length=320), existing_nullable=False)
    EncryptedEmailMigration(op.get_bind(), 'orders', 'user_email', lookup='user_email_hash').encrypt_rows()
    op.alter_column('orders', 'user_email_hash', existing_type=sa.String(length=EncryptedEmail.LOOKUP_LENGTH), nullable=False)
    op.create_index('idx_orders_user_email_hash', 'orders', ['user_email_hash'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_orders_user_email_hash', table_name='orders')
    EncryptedEmailMigration(op.get_bind(), 'orders', 'user_email').decrypt_rows()
    op.alter_column('orders', 'user_email', type_=sa.String(length=320), existing_type=sa.String(length=EncryptedEmail.STORED_LENGTH), existing_nullable=False)
    op.drop_column('orders', 'user_email_hash')
