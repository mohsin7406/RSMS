"""Add inventory part usage returns.

Revision ID: m5c6d7e8f901
Revises: l4b5c6d7e890
"""

from alembic import op
import sqlalchemy as sa


revision = "m5c6d7e8f901"
down_revision = "l4b5c6d7e890"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "part_usage_return",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usage_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("processed_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["usage_id"], ["part_usage.id"]),
        sa.ForeignKeyConstraint(["processed_by_id"], ["user.id"]),
    )
    op.create_index("ix_part_usage_return_usage_id", "part_usage_return", ["usage_id"])
    op.create_index("ix_part_usage_return_processed_by_id", "part_usage_return", ["processed_by_id"])
    op.create_index("ix_part_usage_return_created_at", "part_usage_return", ["created_at"])


def downgrade():
    op.drop_index("ix_part_usage_return_created_at", table_name="part_usage_return")
    op.drop_index("ix_part_usage_return_processed_by_id", table_name="part_usage_return")
    op.drop_index("ix_part_usage_return_usage_id", table_name="part_usage_return")
    op.drop_table("part_usage_return")
