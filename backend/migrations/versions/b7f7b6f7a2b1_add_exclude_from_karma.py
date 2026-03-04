"""add exclude_from_karma to adventures

Revision ID: b7f7b6f7a2b1
Revises: fix_assignments_top_three
Create Date: 2026-01-21 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7f7b6f7a2b1"
down_revision = "fix_assignments_top_three"
branch_labels = None
depends_on = None


def _column_exists(bind, table_name, column_name):
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade():
    bind = op.get_bind()
    if not _column_exists(bind, "adventures", "exclude_from_karma"):
        with op.batch_alter_table("adventures", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "exclude_from_karma",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("0"),
                )
            )


def downgrade():
    bind = op.get_bind()
    if _column_exists(bind, "adventures", "exclude_from_karma"):
        with op.batch_alter_table("adventures", schema=None) as batch_op:
            batch_op.drop_column("exclude_from_karma")
