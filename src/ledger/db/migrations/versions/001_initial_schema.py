"""Initial schema with accounts, entries, and postings tables.

Revision ID: 001
Revises:
Create Date: 2024-12-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create accounts table
    op.create_table(
        'accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('is_placeholder', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("type IN ('asset', 'liability', 'equity', 'income', 'expense')", name='ck_account_type'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_accounts_name'), 'accounts', ['name'], unique=True)

    # Create entries table
    op.create_table(
        'entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('payee', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'cleared', 'reconciled')", name='ck_entry_status'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_entries_date'), 'entries', ['date'], unique=False)

    # Create postings table
    op.create_table(
        'postings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entry_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('memo', sa.String(length=255), nullable=True),
        sa.Column('reconciled_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['entry_id'], ['entries.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_postings_account_id'), 'postings', ['account_id'], unique=False)
    op.create_index(op.f('ix_postings_entry_id'), 'postings', ['entry_id'], unique=False)

    # Note: Double-entry balance validation is performed in the service layer
    # rather than via database trigger to avoid issues with partial transaction states


def downgrade() -> None:
    op.drop_index(op.f('ix_postings_entry_id'), table_name='postings')
    op.drop_index(op.f('ix_postings_account_id'), table_name='postings')
    op.drop_table('postings')
    op.drop_index(op.f('ix_entries_date'), table_name='entries')
    op.drop_table('entries')
    op.drop_index(op.f('ix_accounts_name'), table_name='accounts')
    op.drop_table('accounts')
