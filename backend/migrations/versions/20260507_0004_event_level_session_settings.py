"""Add event-level session settings

Revision ID: 20260507_0004
Revises: 20260505_0003
Create Date: 2026-05-07

"""
from alembic import op
import sqlalchemy as sa

revision = '20260507_0004'
down_revision = '20260505_0003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('events', sa.Column('placement_mode', sa.String(length=32), nullable=False, server_default='delayed'))
    op.add_column('events', sa.Column('release_assignments', sa.Boolean(), nullable=False, server_default=sa.false()))

    # Backfill session values from event defaults where possible for consistency.
    op.execute(
        """
        UPDATE event_sessions
        SET placement_mode = 'delayed'
        WHERE placement_mode IS NULL OR placement_mode = ''
        """
    )


def downgrade():
    op.drop_column('events', 'release_assignments')
    op.drop_column('events', 'placement_mode')
