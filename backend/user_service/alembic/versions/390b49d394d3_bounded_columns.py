"""bounded columns: lengths on every string column, CHECKs on counts and money

Revision ID: 390b49d394d3
Revises: b5e1c8d4f207
Create Date: 2026-10-21 17:51:04.000000

Every bound is at or above the request schema that writes the column
(contracts.limits) and above the longest value stored when it was written.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '390b49d394d3'
down_revision: Union[str, Sequence[str], None] = 'b5e1c8d4f207'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('outbox_events', 'event_type', type_=sa.String(length=64), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('outbox_events', 'last_error', type_=sa.String(length=2000), existing_type=sa.Text(), existing_nullable=True)
    op.create_check_constraint('ck_outbox_events_attempts', 'outbox_events', 'attempts >= 0')
    op.alter_column('users', 'email', type_=sa.String(length=320), existing_type=sa.String(length=100), existing_nullable=False)
    op.alter_column('users', 'hashed_password', type_=sa.String(length=255), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('users', 'phone_number', type_=sa.String(length=32), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('users', 'image', type_=sa.String(length=2048), existing_type=sa.String(), existing_nullable=True)
    op.create_check_constraint('ck_users_token_version', 'users', 'token_version >= 0')
    op.create_check_constraint('ck_webauthn_credentials_sign_count', 'webauthn_credentials', 'sign_count >= 0')
    op.create_check_constraint('ck_webauthn_credentials_transports', 'webauthn_credentials', 'cardinality(transports) <= 10')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_webauthn_credentials_transports', 'webauthn_credentials', type_='check')
    op.drop_constraint('ck_webauthn_credentials_sign_count', 'webauthn_credentials', type_='check')
    op.drop_constraint('ck_users_token_version', 'users', type_='check')
    op.alter_column('users', 'image', type_=sa.String(), existing_type=sa.String(length=2048), existing_nullable=True)
    op.alter_column('users', 'phone_number', type_=sa.String(), existing_type=sa.String(length=32), existing_nullable=True)
    op.alter_column('users', 'hashed_password', type_=sa.String(), existing_type=sa.String(length=255), existing_nullable=True)
    op.alter_column('users', 'email', type_=sa.String(length=100), existing_type=sa.String(length=320), existing_nullable=False)
    op.drop_constraint('ck_outbox_events_attempts', 'outbox_events', type_='check')
    op.alter_column('outbox_events', 'last_error', type_=sa.Text(), existing_type=sa.String(length=2000), existing_nullable=True)
    op.alter_column('outbox_events', 'event_type', type_=sa.String(), existing_type=sa.String(length=64), existing_nullable=False)
