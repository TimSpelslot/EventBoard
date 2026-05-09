"""Add sort_order to events table

Revision ID: 20260510_0006
Revises: 20260507_0005
Create Date: 2026-05-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260510_0006'
down_revision = '20260507_0005'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('events', sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('events', 'sort_order')
