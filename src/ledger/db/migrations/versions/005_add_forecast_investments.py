"""Add forecast_investments table.

Revision ID: 005
Revises: 004
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'forecast_investments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('starting_balance', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('monthly_contribution', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('annual_growth_rate', sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('notes', sa.String(), nullable=True),
        sa.CheckConstraint(
            'starting_balance >= 0',
            name='ck_forecast_investment_starting_balance',
        ),
        sa.CheckConstraint(
            'monthly_contribution >= 0',
            name='ck_forecast_investment_monthly_contribution',
        ),
        sa.ForeignKeyConstraint(
            ['profile_id'], ['forecast_profiles.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_forecast_investments_profile_id'),
        'forecast_investments',
        ['profile_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_forecast_investments_profile_id'),
        table_name='forecast_investments',
    )
    op.drop_table('forecast_investments')
