"""add is_story_adventure to adventures

Revision ID: add_is_story_adventure
Revises: b7f7b6f7a2b1
Create Date: 2026-01-21 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_is_story_adventure"
down_revision = "b7f7b6f7a2b1"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("adventures")]
    if "is_story_adventure" not in columns:
        with op.batch_alter_table("adventures", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "is_story_adventure",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("0"),
                )
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("adventures")]
    if "is_story_adventure" in columns:
        with op.batch_alter_table("adventures", schema=None) as batch_op:
            batch_op.drop_column("is_story_adventure")
