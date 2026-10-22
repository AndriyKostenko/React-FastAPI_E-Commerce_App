"""encrypted emails: cj_order_attempts.user_email stored encrypted

Revision ID: 3c6d68b48411
Revises: 437ed6a16519
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
revision: str = '3c6d68b48411'
down_revision: Union[str, Sequence[str], None] = '437ed6a16519'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('cj_order_attempts', 'user_email', type_=sa.String(length=EncryptedEmail.STORED_LENGTH), existing_type=sa.String(length=320), existing_nullable=True)
    EncryptedEmailMigration(op.get_bind(), 'cj_order_attempts', 'user_email').encrypt_rows()


def downgrade() -> None:
    """Downgrade schema."""
    EncryptedEmailMigration(op.get_bind(), 'cj_order_attempts', 'user_email').decrypt_rows()
    op.alter_column('cj_order_attempts', 'user_email', type_=sa.String(length=320), existing_type=sa.String(length=EncryptedEmail.STORED_LENGTH), existing_nullable=True)
