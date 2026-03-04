"""add notify_create_adventure_reminder to users

Revision ID: add_create_adv_rem
Revises: add_notif_fcm
Create Date: 2026-02-28

"""
from alembic import op
import sqlalchemy as sa


revision = "add_create_adv_rem"
down_revision = "add_notif_fcm"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("notify_create_adventure_reminder", sa.Boolean(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("notify_create_adventure_reminder")
