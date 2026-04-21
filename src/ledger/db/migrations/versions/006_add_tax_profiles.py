"""Add tax_profiles table + tax_profile_id FK on forecast_lines.

Tax profiles are reusable templates (name, jurisdiction, apply_income_tax,
apply_ni). A forecast_line can optionally reference one via tax_profile_id.
ON DELETE RESTRICT so a profile in use cannot be silently orphaned —
callers must detach references first.

Revision ID: 006
Revises: 005
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tax_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('jurisdiction', sa.String(length=20), nullable=False),
        sa.Column('apply_income_tax', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('apply_ni', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "jurisdiction IN ('scotland', 'ruk')",
            name='ck_tax_profile_jurisdiction',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_tax_profile_name'),
    )

    # SQLite requires batch mode for ALTER TABLE with FK.
    with op.batch_alter_table('forecast_lines') as batch_op:
        batch_op.add_column(
            sa.Column('tax_profile_id', sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_forecast_lines_tax_profile_id',
            'tax_profiles',
            ['tax_profile_id'],
            ['id'],
            ondelete='RESTRICT',
        )
        batch_op.create_index(
            'ix_forecast_lines_tax_profile_id',
            ['tax_profile_id'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('forecast_lines') as batch_op:
        batch_op.drop_index('ix_forecast_lines_tax_profile_id')
        batch_op.drop_constraint(
            'fk_forecast_lines_tax_profile_id', type_='foreignkey'
        )
        batch_op.drop_column('tax_profile_id')

    op.drop_table('tax_profiles')
