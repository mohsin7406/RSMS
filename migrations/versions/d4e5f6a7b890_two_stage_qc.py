"""Add before and after QC fields.

Revision ID: d4e5f6a7b890
Revises: c8d9e0f1a234
"""
from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b890"
down_revision = "c8d9e0f1a234"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("repair_qc", sa.Column("before_status", sa.String(length=20), nullable=False, server_default="Pending"))
    op.add_column("repair_qc", sa.Column("before_checklist", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("repair_qc", sa.Column("before_notes", sa.Text(), nullable=True))
    op.add_column("repair_qc", sa.Column("before_tested_by_id", sa.Integer(), nullable=True))
    op.add_column("repair_qc", sa.Column("before_tested_at", sa.DateTime(), nullable=True))
    op.add_column("repair_qc", sa.Column("before_photos", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("repair_qc", sa.Column("after_status", sa.String(length=20), nullable=False, server_default="Pending"))
    op.add_column("repair_qc", sa.Column("after_checklist", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("repair_qc", sa.Column("after_notes", sa.Text(), nullable=True))
    op.add_column("repair_qc", sa.Column("after_tested_by_id", sa.Integer(), nullable=True))
    op.add_column("repair_qc", sa.Column("after_tested_at", sa.DateTime(), nullable=True))
    op.add_column("repair_qc", sa.Column("after_photos", sa.JSON(), nullable=False, server_default="[]"))
    op.create_foreign_key("fk_repair_qc_before_user", "repair_qc", "user", ["before_tested_by_id"], ["id"])
    op.create_foreign_key("fk_repair_qc_after_user", "repair_qc", "user", ["after_tested_by_id"], ["id"])
    op.create_index("ix_repair_qc_before_status", "repair_qc", ["before_status"])
    op.create_index("ix_repair_qc_after_status", "repair_qc", ["after_status"])


def downgrade():
    op.drop_index("ix_repair_qc_after_status", table_name="repair_qc")
    op.drop_index("ix_repair_qc_before_status", table_name="repair_qc")
    op.drop_constraint("fk_repair_qc_after_user", "repair_qc", type_="foreignkey")
    op.drop_constraint("fk_repair_qc_before_user", "repair_qc", type_="foreignkey")
    for column in (
        "after_photos", "after_tested_at", "after_tested_by_id", "after_notes", "after_checklist", "after_status",
        "before_photos", "before_tested_at", "before_tested_by_id", "before_notes", "before_checklist", "before_status",
    ):
        op.drop_column("repair_qc", column)
