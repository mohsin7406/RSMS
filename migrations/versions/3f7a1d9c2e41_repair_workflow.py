"""add production repair workflow fields

Revision ID: 3f7a1d9c2e41
Revises: 9c1f4a2b7e10
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

revision = "3f7a1d9c2e41"
down_revision = "9c1f4a2b7e10"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("repair_order") as batch_op:
        batch_op.add_column(sa.Column("job_number", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("assigned_technician_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("brand", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("model", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("imei", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("serial_number", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("diagnosis", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("repair_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("priority", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("service_type", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("estimated_amount", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("final_amount", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("amount_paid", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("payment_status", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("payment_method", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("customer_approved", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("warranty_days", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("delivered_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch_op.create_foreign_key("fk_repair_order_technician", "user", ["assigned_technician_id"], ["id"])

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id FROM repair_order WHERE job_number IS NULL ORDER BY id")).fetchall()
    today = datetime.utcnow().strftime("%Y%m%d")
    for sequence, (repair_id,) in enumerate(rows, start=1):
        connection.execute(
            sa.text("UPDATE repair_order SET job_number=:job, priority='Normal', service_type='In-Shop', estimated_amount=0, final_amount=0, amount_paid=0, payment_status='Unpaid', customer_approved=0, warranty_days=0, updated_at=:now WHERE id=:id"),
            {"job": f"JOB-{today}-{sequence:04d}", "now": datetime.utcnow(), "id": repair_id},
        )
    connection.commit()

    with op.batch_alter_table("repair_order") as batch_op:
        batch_op.alter_column("job_number", nullable=False)
        batch_op.alter_column("status", server_default="Pending")
        batch_op.alter_column("priority", nullable=False, server_default="Normal")
        batch_op.alter_column("service_type", nullable=False, server_default="In-Shop")
        batch_op.alter_column("estimated_amount", nullable=False, server_default="0")
        batch_op.alter_column("final_amount", nullable=False, server_default="0")
        batch_op.alter_column("amount_paid", nullable=False, server_default="0")
        batch_op.alter_column("payment_status", nullable=False, server_default="Unpaid")
        batch_op.alter_column("customer_approved", nullable=False, server_default=sa.text("0"))
        batch_op.alter_column("warranty_days", nullable=False, server_default="0")
        batch_op.alter_column("updated_at", nullable=False, server_default=sa.func.now())
        batch_op.create_index("ix_repair_order_job_number", ["job_number"], unique=True)
        batch_op.create_index("ix_repair_order_brand", ["brand"], unique=False)
        batch_op.create_index("ix_repair_order_imei", ["imei"], unique=False)
        batch_op.create_index("ix_repair_order_deleted_at", ["deleted_at"], unique=False)


def downgrade():
    with op.batch_alter_table("repair_order") as batch_op:
        batch_op.drop_index("ix_repair_order_deleted_at")
        batch_op.drop_index("ix_repair_order_imei")
        batch_op.drop_index("ix_repair_order_brand")
        batch_op.drop_index("ix_repair_order_job_number")
        batch_op.drop_constraint("fk_repair_order_technician", type_="foreignkey")
        for column in [
            "deleted_at", "updated_at", "delivered_at", "warranty_days", "customer_approved",
            "payment_method", "payment_status", "amount_paid", "final_amount", "estimated_amount",
            "service_type", "priority", "repair_notes", "diagnosis", "serial_number", "imei",
            "model", "brand", "assigned_technician_id", "job_number",
        ]:
            batch_op.drop_column(column)
