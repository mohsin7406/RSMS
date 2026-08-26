"""Add before and after QC fields.

Revision ID: d4e5f6a7b890
Revises: c8d9e0f1a234
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "d4e5f6a7b890"
down_revision = "c8d9e0f1a234"
branch_labels = None
depends_on = None


_COLUMNS = (
    ("before_status", sa.Column("before_status", sa.String(length=20), nullable=False, server_default="Pending")),
    ("before_checklist", sa.Column("before_checklist", sa.JSON(), nullable=False, server_default="{}")),
    ("before_notes", sa.Column("before_notes", sa.Text(), nullable=True)),
    ("before_tested_by_id", sa.Column("before_tested_by_id", sa.Integer(), nullable=True)),
    ("before_tested_at", sa.Column("before_tested_at", sa.DateTime(), nullable=True)),
    ("before_photos", sa.Column("before_photos", sa.JSON(), nullable=False, server_default="[]")),
    ("after_status", sa.Column("after_status", sa.String(length=20), nullable=False, server_default="Pending")),
    ("after_checklist", sa.Column("after_checklist", sa.JSON(), nullable=False, server_default="{}")),
    ("after_notes", sa.Column("after_notes", sa.Text(), nullable=True)),
    ("after_tested_by_id", sa.Column("after_tested_by_id", sa.Integer(), nullable=True)),
    ("after_tested_at", sa.Column("after_tested_at", sa.DateTime(), nullable=True)),
    ("after_photos", sa.Column("after_photos", sa.JSON(), nullable=False, server_default="[]")),
)


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("repair_qc")}

    for name, column in _COLUMNS:
        if name not in existing_columns:
            op.add_column("repair_qc", column)

    # SQLite cannot ALTER TABLE to add/drop foreign keys directly. Rebuild the
    # table in batch mode so the migration works on both SQLite and other DBs.
    inspector = inspect(bind)
    existing_fks = {
        fk.get("name")
        for fk in inspector.get_foreign_keys("repair_qc")
        if fk.get("name")
    }
    missing_fks = []
    for constraint_name, local_column in (
        ("fk_repair_qc_before_user", "before_tested_by_id"),
        ("fk_repair_qc_after_user", "after_tested_by_id"),
    ):
        if constraint_name not in existing_fks:
            missing_fks.append((constraint_name, local_column))

    if missing_fks:
        with op.batch_alter_table("repair_qc", recreate="always") as batch_op:
            for constraint_name, local_column in missing_fks:
                batch_op.create_foreign_key(
                    constraint_name,
                    "user",
                    [local_column],
                    ["id"],
                )

    inspector = inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("repair_qc")}
    if "ix_repair_qc_before_status" not in existing_indexes:
        op.create_index("ix_repair_qc_before_status", "repair_qc", ["before_status"])
    if "ix_repair_qc_after_status" not in existing_indexes:
        op.create_index("ix_repair_qc_after_status", "repair_qc", ["after_status"])


def downgrade():
    with op.batch_alter_table("repair_qc", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_repair_qc_after_user", type_="foreignkey")
        batch_op.drop_constraint("fk_repair_qc_before_user", type_="foreignkey")

    op.drop_index("ix_repair_qc_after_status", table_name="repair_qc")
    op.drop_index("ix_repair_qc_before_status", table_name="repair_qc")
    for column in (
        "after_photos", "after_tested_at", "after_tested_by_id", "after_notes", "after_checklist", "after_status",
        "before_photos", "before_tested_at", "before_tested_by_id", "before_notes", "before_checklist", "before_status",
    ):
        op.drop_column("repair_qc", column)
