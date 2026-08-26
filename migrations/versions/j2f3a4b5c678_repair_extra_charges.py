"""Add repair extra charges.

Revision ID: j2f3a4b5c678
Revises: i1e2f3a4b567
"""
from alembic import op
import sqlalchemy as sa

revision = "j2f3a4b5c678"
down_revision = "i1e2f3a4b567"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "repair_extra_charge",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repair_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("added_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["repair_id"], ["repair_order.id"]),
        sa.ForeignKeyConstraint(["added_by_id"], ["user.id"]),
    )
    op.create_index("ix_repair_extra_charge_repair_id", "repair_extra_charge", ["repair_id"])
    op.create_index("ix_repair_extra_charge_added_by_id", "repair_extra_charge", ["added_by_id"])
    op.create_index("ix_repair_extra_charge_created_at", "repair_extra_charge", ["created_at"])


def downgrade():
    op.drop_index("ix_repair_extra_charge_created_at", table_name="repair_extra_charge")
    op.drop_index("ix_repair_extra_charge_added_by_id", table_name="repair_extra_charge")
    op.drop_index("ix_repair_extra_charge_repair_id", table_name="repair_extra_charge")
    op.drop_table("repair_extra_charge")
