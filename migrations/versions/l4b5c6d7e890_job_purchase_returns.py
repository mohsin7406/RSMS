"""Add job purchase return tracking.

Revision ID: l4b5c6d7e890
Revises: k3a4b5c6d789
"""

from alembic import op
import sqlalchemy as sa


revision = "l4b5c6d7e890"
down_revision = "k3a4b5c6d789"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job_purchase_return",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("destination", sa.String(length=20), nullable=False),
        sa.Column("inventory_part_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("processed_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["purchase_id"], ["job_purchase.id"]),
        sa.ForeignKeyConstraint(["inventory_part_id"], ["part.id"]),
        sa.ForeignKeyConstraint(["processed_by_id"], ["user.id"]),
    )
    op.create_index("ix_job_purchase_return_purchase_id", "job_purchase_return", ["purchase_id"])
    op.create_index("ix_job_purchase_return_destination", "job_purchase_return", ["destination"])
    op.create_index("ix_job_purchase_return_inventory_part_id", "job_purchase_return", ["inventory_part_id"])
    op.create_index("ix_job_purchase_return_processed_by_id", "job_purchase_return", ["processed_by_id"])
    op.create_index("ix_job_purchase_return_created_at", "job_purchase_return", ["created_at"])


def downgrade():
    op.drop_index("ix_job_purchase_return_created_at", table_name="job_purchase_return")
    op.drop_index("ix_job_purchase_return_processed_by_id", table_name="job_purchase_return")
    op.drop_index("ix_job_purchase_return_inventory_part_id", table_name="job_purchase_return")
    op.drop_index("ix_job_purchase_return_destination", table_name="job_purchase_return")
    op.drop_index("ix_job_purchase_return_purchase_id", table_name="job_purchase_return")
    op.drop_table("job_purchase_return")
