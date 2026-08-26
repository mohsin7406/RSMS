"""Add job-specific purchases.

Revision ID: k3a4b5c6d789
Revises: j2f3a4b5c678
"""

from alembic import op
import sqlalchemy as sa


revision = "k3a4b5c6d789"
down_revision = "j2f3a4b5c678"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job_purchase",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repair_id", sa.Integer(), nullable=False),
        sa.Column("item_name", sa.String(length=160), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="1"),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("supplier", sa.String(length=160), nullable=True),
        sa.Column("reference", sa.String(length=160), nullable=True),
        sa.Column("added_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["repair_id"], ["repair_order.id"]),
        sa.ForeignKeyConstraint(["added_by_id"], ["user.id"]),
    )
    op.create_index("ix_job_purchase_repair_id", "job_purchase", ["repair_id"])
    op.create_index("ix_job_purchase_added_by_id", "job_purchase", ["added_by_id"])
    op.create_index("ix_job_purchase_created_at", "job_purchase", ["created_at"])


def downgrade():
    op.drop_index("ix_job_purchase_created_at", table_name="job_purchase")
    op.drop_index("ix_job_purchase_added_by_id", table_name="job_purchase")
    op.drop_index("ix_job_purchase_repair_id", table_name="job_purchase")
    op.drop_table("job_purchase")
