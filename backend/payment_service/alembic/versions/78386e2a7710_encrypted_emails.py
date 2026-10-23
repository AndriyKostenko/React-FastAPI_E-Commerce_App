"""encrypted emails: payments.user_email stored encrypted

Revision ID: 78386e2a7710
Revises: 093cd6a4b1dc
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
revision: str = '78386e2a7710'
down_revision: Union[str, Sequence[str], None] = '093cd6a4b1dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('payments', 'user_email', type_=sa.String(length=EncryptedEmail.STORED_LENGTH), existing_type=sa.String(length=320), existing_nullable=False)
    EncryptedEmailMigration(op.get_bind(), 'payments', 'user_email').encrypt_rows()


def downgrade() -> None:
    """Downgrade schema."""
    EncryptedEmailMigration(op.get_bind(), 'payments', 'user_email').decrypt_rows()
    op.alter_column('payments', 'user_email', type_=sa.String(length=320), existing_type=sa.String(length=EncryptedEmail.STORED_LENGTH), existing_nullable=False)
