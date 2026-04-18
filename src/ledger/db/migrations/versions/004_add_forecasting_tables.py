"""Add forecasting tables: profiles, lines, and per-month overrides.

Revision ID: 004
Revises: 003
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'forecast_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('horizon_months', sa.Integer(), nullable=False),
        sa.Column('opening_balance', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint('horizon_months > 0', name='ck_forecast_profile_horizon'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'forecast_lines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('start_month_offset', sa.Integer(), nullable=False),
        sa.Column('end_month_offset', sa.Integer(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('notes', sa.String(), nullable=True),
        sa.CheckConstraint("kind IN ('inflow', 'outflow')", name='ck_forecast_line_kind'),
        sa.CheckConstraint('amount >= 0', name='ck_forecast_line_amount'),
        sa.CheckConstraint('start_month_offset >= 0', name='ck_forecast_line_start_offset'),
        sa.CheckConstraint(
            'end_month_offset >= start_month_offset',
            name='ck_forecast_line_end_offset',
        ),
        sa.ForeignKeyConstraint(
            ['profile_id'], ['forecast_profiles.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_forecast_lines_profile_id'),
        'forecast_lines',
        ['profile_id'],
        unique=False,
    )

    op.create_table(
        'forecast_line_overrides',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('line_id', sa.Integer(), nullable=False),
        sa.Column('month_offset', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('notes', sa.String(), nullable=True),
        sa.CheckConstraint(
            'month_offset >= 0', name='ck_forecast_line_override_month_offset'
        ),
        sa.CheckConstraint('amount >= 0', name='ck_forecast_line_override_amount'),
        sa.ForeignKeyConstraint(
            ['line_id'], ['forecast_lines.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'line_id', 'month_offset', name='uq_forecast_line_override_line_month'
        ),
    )
    op.create_index(
        op.f('ix_forecast_line_overrides_line_id'),
        'forecast_line_overrides',
        ['line_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_forecast_line_overrides_line_id'),
        table_name='forecast_line_overrides',
    )
    op.drop_table('forecast_line_overrides')
    op.drop_index(op.f('ix_forecast_lines_profile_id'), table_name='forecast_lines')
    op.drop_table('forecast_lines')
    op.drop_table('forecast_profiles')
