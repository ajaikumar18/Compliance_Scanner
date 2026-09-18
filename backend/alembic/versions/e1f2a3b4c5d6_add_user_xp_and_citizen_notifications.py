"""add_user_xp_and_citizen_notifications

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-09-18 19:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add xp column to users table (default: 100)
    op.add_column('users', sa.Column('xp', sa.Integer(), nullable=False, server_default='100'))

    # Create citizen_notifications table
    op.create_table(
        'citizen_notifications',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('scan_id', sa.Integer(), sa.ForeignKey('scans.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('notification_type', sa.String(length=50), nullable=False, server_default='system_notice'),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('xp_change', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('citizen_notifications')
    op.drop_column('users', 'xp')
