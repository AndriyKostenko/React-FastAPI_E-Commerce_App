"""encrypted emails: users.email stored encrypted, unique lookup hash beside it

Revision ID: 2683f5822ca0
Revises: 390b49d394d3
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
revision: str = '2683f5822ca0'
down_revision: Union[str, Sequence[str], None] = '390b49d394d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('email_hash', sa.String(length=EncryptedEmail.LOOKUP_LENGTH), nullable=True))
    op.alter_column('users', 'email', type_=sa.String(length=EncryptedEmail.STORED_LENGTH), existing_type=sa.String(length=320), existing_nullable=False)
    EncryptedEmailMigration(op.get_bind(), 'users', 'email', lookup='email_hash').encrypt_rows()
    op.alter_column('users', 'email_hash', existing_type=sa.String(length=EncryptedEmail.LOOKUP_LENGTH), nullable=False)
    # Uniqueness moves to the hash: the ciphertext of one address never repeats.
    op.drop_constraint('users_email_key', 'users', type_='unique')
    op.create_unique_constraint('uq_users_email_hash', 'users', ['email_hash'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_users_email_hash', 'users', type_='unique')
    EncryptedEmailMigration(op.get_bind(), 'users', 'email').decrypt_rows()
    op.alter_column('users', 'email', type_=sa.String(length=320), existing_type=sa.String(length=EncryptedEmail.STORED_LENGTH), existing_nullable=False)
    op.create_unique_constraint('users_email_key', 'users', ['email'])
    op.drop_column('users', 'email_hash')
