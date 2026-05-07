"""add event session participants

Revision ID: 20260505_0002
Revises: 20260505_0001
Create Date: 2026-05-05 00:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260505_0002'
down_revision = '20260505_0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'event_session_participants',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_session_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('guest_player_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='waitlist'),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('added_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['event_session_id'], ['event_sessions.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['guest_player_id'], ['guest_players.id']),
        sa.ForeignKeyConstraint(['added_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_session_id', 'user_id', name='unique_session_user_participant'),
        sa.UniqueConstraint('event_session_id', 'guest_player_id', name='unique_session_guest_participant'),
    )


def downgrade():
    op.drop_table('event_session_participants')
