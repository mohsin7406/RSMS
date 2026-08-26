"""Add role permissions and ensure booking repair link.

Revision ID: i1e2f3a4b567
Revises: h0d1e2f3a456
"""
from alembic import op
import sqlalchemy as sa

revision = "i1e2f3a4b567"
down_revision = "h0d1e2f3a456"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    booking_columns = {column["name"] for column in inspector.get_columns("booking")}
    if "repair_id" not in booking_columns:
        with op.batch_alter_table("booking") as batch_op:
            batch_op.add_column(sa.Column("repair_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key("fk_booking_repair_id_repair_order", "repair_order", ["repair_id"], ["id"])
            batch_op.create_index("ix_booking_repair_id", ["repair_id"])

    if "role_permission" not in inspector.get_table_names():
        op.create_table(
            "role_permission",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("role", sa.String(length=30), nullable=False),
            sa.Column("permission", sa.String(length=60), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("role", "permission", name="uq_role_permission_role_permission"),
        )
        op.create_index("ix_role_permission_role", "role_permission", ["role"])
        op.create_index("ix_role_permission_permission", "role_permission", ["permission"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "role_permission" in inspector.get_table_names():
        op.drop_index("ix_role_permission_permission", table_name="role_permission")
        op.drop_index("ix_role_permission_role", table_name="role_permission")
        op.drop_table("role_permission")

    booking_columns = {column["name"] for column in inspector.get_columns("booking")}
    if "repair_id" in booking_columns:
        with op.batch_alter_table("booking") as batch_op:
            batch_op.drop_index("ix_booking_repair_id")
            batch_op.drop_constraint("fk_booking_repair_id_repair_order", type_="foreignkey")
            batch_op.drop_column("repair_id")
