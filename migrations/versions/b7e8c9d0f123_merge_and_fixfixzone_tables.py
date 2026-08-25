"""merge migration branches and add production business tables

Revision ID: b7e8c9d0f123
Revises: 3f7a1d9c2e41, a2e4b8c6d901
"""
from alembic import op
import sqlalchemy as sa

revision = "b7e8c9d0f123"
down_revision = ("3f7a1d9c2e41", "a2e4b8c6d901")
branch_labels = None
depends_on = None


def _index(name, table, column):
    op.create_index(name, table, [column], unique=False)


def upgrade():
    op.create_table(
        "repair_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repair_id", sa.Integer(), sa.ForeignKey("repair_order.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    _index("ix_repair_audit_logs_repair_id", "repair_audit_logs", "repair_id")
    _index("ix_repair_audit_logs_user_id", "repair_audit_logs", "user_id")
    _index("ix_repair_audit_logs_action", "repair_audit_logs", "action")
    _index("ix_repair_audit_logs_created_at", "repair_audit_logs", "created_at")

    op.create_table(
        "part",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("brand", sa.String(80), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("category", sa.String(80), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("reorder_level", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cost_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("selling_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("supplier", sa.String(150), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    _index("ix_part_sku", "part", "sku")
    _index("ix_part_name", "part", "name")
    _index("ix_part_category", "part", "category")
    _index("ix_part_active", "part", "active")

    op.create_table(
        "part_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repair_id", sa.Integer(), sa.ForeignKey("repair_order.id"), nullable=False),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("part.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="1"),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    _index("ix_part_usage_repair_id", "part_usage", "repair_id")
    _index("ix_part_usage_part_id", "part_usage", "part_id")

    op.create_table(
        "stock_movement",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("part.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("movement_type", sa.String(30), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    _index("ix_stock_movement_part_id", "stock_movement", "part_id")
    _index("ix_stock_movement_user_id", "stock_movement", "user_id")
    _index("ix_stock_movement_movement_type", "stock_movement", "movement_type")
    _index("ix_stock_movement_created_at", "stock_movement", "created_at")

    op.create_table(
        "repair_qc",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repair_id", sa.Integer(), sa.ForeignKey("repair_order.id"), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Pending"),
        sa.Column("checklist", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tested_by_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("tested_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    _index("ix_repair_qc_repair_id", "repair_qc", "repair_id")
    _index("ix_repair_qc_status", "repair_qc", "status")
    _index("ix_repair_qc_tested_by_id", "repair_qc", "tested_by_id")

    op.create_table(
        "warranty_claim",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repair_id", sa.Integer(), sa.ForeignKey("repair_order.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Open"),
        sa.Column("issue", sa.Text(), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("handled_by_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
    )
    _index("ix_warranty_claim_repair_id", "warranty_claim", "repair_id")
    _index("ix_warranty_claim_customer_id", "warranty_claim", "customer_id")
    _index("ix_warranty_claim_status", "warranty_claim", "status")
    _index("ix_warranty_claim_handled_by_id", "warranty_claim", "handled_by_id")

    op.create_table(
        "lead",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("email", sa.String(120), nullable=True),
        sa.Column("device", sa.String(100), nullable=True),
        sa.Column("issue", sa.Text(), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("area", sa.String(120), nullable=True),
        sa.Column("service_type", sa.String(30), nullable=False, server_default="Doorstep"),
        sa.Column("status", sa.String(30), nullable=False, server_default="New"),
        sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    for name, col in [("name","name"),("phone","phone"),("source","source"),("area","area"),("status","status"),("assigned_to_id","assigned_to_id"),("customer_id","customer_id"),("created_at","created_at")]:
        _index(f"ix_lead_{name}", "lead", col)

    op.create_table(
        "booking",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_number", sa.String(32), nullable=False, unique=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("technician_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("repair_id", sa.Integer(), sa.ForeignKey("repair_order.id"), nullable=True),
        sa.Column("service_type", sa.String(30), nullable=False, server_default="Doorstep"),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("area", sa.String(120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="Scheduled"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    for name, col in [("booking_number","booking_number"),("customer_id","customer_id"),("technician_id","technician_id"),("repair_id","repair_id"),("scheduled_at","scheduled_at"),("area","area"),("status","status")]:
        _index(f"ix_booking_{name}", "booking", col)

    op.create_table(
        "service_confirmations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repair_id", sa.Integer(), sa.ForeignKey("repair_order.id"), nullable=False, unique=True),
        sa.Column("confirmation_type", sa.String(30), nullable=False, server_default="Customer Approval"),
        sa.Column("customer_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("otp_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("otp_hash", sa.String(255), nullable=True),
        sa.Column("confirmation_note", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_by_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    _index("ix_service_confirmations_repair_id", "service_confirmations", "repair_id")
    _index("ix_service_confirmations_confirmed_by_id", "service_confirmations", "confirmed_by_id")

    op.create_table(
        "repair_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repair_id", sa.Integer(), sa.ForeignKey("repair_order.id"), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("photo_type", sa.String(20), nullable=False, server_default="Other"),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("caption", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    _index("ix_repair_photos_repair_id", "repair_photos", "repair_id")
    _index("ix_repair_photos_uploaded_by_id", "repair_photos", "uploaded_by_id")
    _index("ix_repair_photos_created_at", "repair_photos", "created_at")


def downgrade():
    for name, table in [
        ("ix_repair_photos_created_at", "repair_photos"), ("ix_repair_photos_uploaded_by_id", "repair_photos"), ("ix_repair_photos_repair_id", "repair_photos"),
    ]:
        op.drop_index(name, table_name=table)
    op.drop_table("repair_photos")

    op.drop_index("ix_service_confirmations_confirmed_by_id", table_name="service_confirmations")
    op.drop_index("ix_service_confirmations_repair_id", table_name="service_confirmations")
    op.drop_table("service_confirmations")

    for name in ["ix_booking_status","ix_booking_area","ix_booking_scheduled_at","ix_booking_repair_id","ix_booking_technician_id","ix_booking_customer_id","ix_booking_booking_number"]:
        op.drop_index(name, table_name="booking")
    op.drop_table("booking")

    for name in ["ix_lead_created_at","ix_lead_customer_id","ix_lead_assigned_to_id","ix_lead_status","ix_lead_area","ix_lead_source","ix_lead_phone","ix_lead_name"]:
        op.drop_index(name, table_name="lead")
    op.drop_table("lead")

    for name in ["ix_warranty_claim_handled_by_id","ix_warranty_claim_status","ix_warranty_claim_customer_id","ix_warranty_claim_repair_id"]:
        op.drop_index(name, table_name="warranty_claim")
    op.drop_table("warranty_claim")

    for name in ["ix_repair_qc_tested_by_id","ix_repair_qc_status","ix_repair_qc_repair_id"]:
        op.drop_index(name, table_name="repair_qc")
    op.drop_table("repair_qc")

    for name in ["ix_stock_movement_created_at","ix_stock_movement_movement_type","ix_stock_movement_user_id","ix_stock_movement_part_id"]:
        op.drop_index(name, table_name="stock_movement")
    op.drop_table("stock_movement")

    for name in ["ix_part_usage_part_id","ix_part_usage_repair_id"]:
        op.drop_index(name, table_name="part_usage")
    op.drop_table("part_usage")

    for name in ["ix_part_active","ix_part_category","ix_part_name","ix_part_sku"]:
        op.drop_index(name, table_name="part")
    op.drop_table("part")

    for name in ["ix_repair_audit_logs_created_at","ix_repair_audit_logs_action","ix_repair_audit_logs_user_id","ix_repair_audit_logs_repair_id"]:
        op.drop_index(name, table_name="repair_audit_logs")
    op.drop_table("repair_audit_logs")
