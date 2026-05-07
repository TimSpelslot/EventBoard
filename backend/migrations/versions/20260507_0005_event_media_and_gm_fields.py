"""Add event image, table media/description, and optional session GM/description

Revision ID: 20260507_0005
Revises: 20260507_0004
Create Date: 2026-05-07

"""

from alembic import op
import sqlalchemy as sa


revision = '20260507_0005'
down_revision = '20260507_0004'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('events', sa.Column('image_url', sa.String(length=1024), nullable=True))

    op.add_column('event_tables', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('event_tables', sa.Column('image_url', sa.String(length=1024), nullable=True))

    op.add_column('event_sessions', sa.Column('gamemaster_name', sa.String(length=255), nullable=True))

    # Make session descriptions optional.
    with op.batch_alter_table('event_sessions') as batch_op:
        batch_op.alter_column('short_description', existing_type=sa.Text(), nullable=True)


def downgrade():
    with op.batch_alter_table('event_sessions') as batch_op:
        batch_op.alter_column('short_description', existing_type=sa.Text(), nullable=False)

    op.drop_column('event_sessions', 'gamemaster_name')

    op.drop_column('event_tables', 'image_url')
    op.drop_column('event_tables', 'description')

    op.drop_column('events', 'image_url')
