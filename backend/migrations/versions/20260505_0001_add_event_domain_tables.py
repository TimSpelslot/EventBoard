"""add event domain tables

Revision ID: 20260505_0001
Revises:
Create Date: 2026-05-05 00:01:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260505_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('notification_days_before', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('allow_event_admin_notifications', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'guest_players',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'event_days',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'date', name='unique_event_day_date')
    )

    op.create_table(
        'event_memberships',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('can_send_notifications', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'user_id', name='unique_event_user_membership')
    )

    op.create_table(
        'event_tables',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_day_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['event_day_id'], ['event_days.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_day_id', 'name', name='unique_event_day_table_name')
    )

    op.create_table(
        'event_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('short_description', sa.Text(), nullable=False),
        sa.Column('event_day_id', sa.Integer(), nullable=False),
        sa.Column('event_table_id', sa.Integer(), nullable=False),
        sa.Column('host_user_id', sa.Integer(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('max_players', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('placement_mode', sa.String(length=32), nullable=False, server_default='delayed'),
        sa.Column('release_assignments', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('release_reminder_days', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['event_day_id'], ['event_days.id']),
        sa.ForeignKeyConstraint(['event_table_id'], ['event_tables.id']),
        sa.ForeignKeyConstraint(['host_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('event_sessions')
    op.drop_table('event_tables')
    op.drop_table('event_memberships')
    op.drop_table('event_days')
    op.drop_table('guest_players')
    op.drop_table('events')