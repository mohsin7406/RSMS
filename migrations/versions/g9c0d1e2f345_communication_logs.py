"""Add unified communication logs.

Revision ID: g9c0d1e2f345
Revises: f8b9c0d1e234
"""
from alembic import op
import sqlalchemy as sa

revision = "g9c0d1e2f345"
down_revision = "f8b9c0d1e234"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "communication_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False, server_default="opened"),
        sa.Column("repair_id", sa.Integer(), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("mobile", sa.String(length=30), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["repair_id"], ["repair_order.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
    )
    op.create_index("ix_communication_log_channel", "communication_log", ["channel"])
    op.create_index("ix_communication_log_repair_id", "communication_log", ["repair_id"])
    op.create_index("ix_communication_log_customer_id", "communication_log", ["customer_id"])
    op.create_index("ix_communication_log_user_id", "communication_log", ["user_id"])
    op.create_index("ix_communication_log_created_at", "communication_log", ["created_at"])


def downgrade():
    op.drop_table("communication_log")
