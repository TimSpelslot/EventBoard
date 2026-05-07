"""Add priority column to event_session_participants

Revision ID: 20260505_0003
Revises: 20260505_0002
Create Date: 2026-05-05

"""
from alembic import op
import sqlalchemy as sa

revision = '20260505_0003'
down_revision = '20260505_0002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'event_session_participants',
        sa.Column('priority', sa.Integer(), nullable=True)
    )


def downgrade():
    op.drop_column('event_session_participants', 'priority')
