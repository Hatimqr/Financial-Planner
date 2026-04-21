"""Add effect_span column to forecast_line_overrides.

``effect_span`` distinguishes single-month overrides (historical behaviour)
from multi-month step overrides that apply from their start month until
another override starts or the line's window ends.

Revision ID: 007
Revises: 006
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('forecast_line_overrides') as batch_op:
        batch_op.add_column(
            sa.Column(
                'effect_span',
                sa.String(length=16),
                nullable=False,
                server_default='single_month',
            )
        )
        batch_op.create_check_constraint(
            'ck_forecast_line_override_effect_span',
            "effect_span IN ('single_month', 'until_next')",
        )


def downgrade() -> None:
    with op.batch_alter_table('forecast_line_overrides') as batch_op:
        batch_op.drop_constraint(
            'ck_forecast_line_override_effect_span', type_='check'
        )
        batch_op.drop_column('effect_span')
