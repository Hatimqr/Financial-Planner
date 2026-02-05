"""Add budgets table for budget tracking.

Revision ID: 002
Revises: 001
Create Date: 2024-12-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create budgets table
    op.create_table(
        'budgets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('period', sa.String(length=20), nullable=False),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("period IN ('monthly', 'quarterly', 'yearly')", name='ck_budget_period'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_budgets_account_id'), 'budgets', ['account_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_budgets_account_id'), table_name='budgets')
    op.drop_table('budgets')
