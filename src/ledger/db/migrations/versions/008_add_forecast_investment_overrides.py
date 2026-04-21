"""Add forecast_investment_overrides table.

Mirrors forecast_line_overrides — per-month absolute-amount replacement
for an investment's monthly contribution, with single_month / until_next
effect spans.

Revision ID: 008
Revises: 007
Create Date: 2026-04-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'forecast_investment_overrides',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('investment_id', sa.Integer(), nullable=False),
        sa.Column('month_offset', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column(
            'effect_span',
            sa.String(length=16),
            nullable=False,
            server_default='single_month',
        ),
        sa.CheckConstraint(
            'month_offset >= 0',
            name='ck_forecast_investment_override_month_offset',
        ),
        sa.CheckConstraint(
            'amount >= 0',
            name='ck_forecast_investment_override_amount',
        ),
        sa.CheckConstraint(
            "effect_span IN ('single_month', 'until_next')",
            name='ck_forecast_investment_override_effect_span',
        ),
        sa.ForeignKeyConstraint(
            ['investment_id'],
            ['forecast_investments.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'investment_id',
            'month_offset',
            name='uq_forecast_investment_override_inv_month',
        ),
    )
    op.create_index(
        op.f('ix_forecast_investment_overrides_investment_id'),
        'forecast_investment_overrides',
        ['investment_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_forecast_investment_overrides_investment_id'),
        table_name='forecast_investment_overrides',
    )
    op.drop_table('forecast_investment_overrides')
