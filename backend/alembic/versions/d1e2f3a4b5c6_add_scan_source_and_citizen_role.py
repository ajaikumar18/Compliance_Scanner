"""add_scan_source_and_citizen_role

Revision ID: d1e2f3a4b5c6
Revises: 447fa3d957bf
Create Date: 2026-09-18 18:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = '447fa3d957bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add source column to scans table (default: 'inspector')
    op.add_column('scans', sa.Column('source', sa.String(length=50), nullable=False, server_default='inspector'))
    # Add claimed_violation_type column to scans table
    op.add_column('scans', sa.Column('claimed_violation_type', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('scans', 'claimed_violation_type')
    op.drop_column('scans', 'source')
