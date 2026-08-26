"""Add composite indexes for production query paths.
Revision ID: z8d9e0f1a234
Revises: y7c8d9e0f123
"""
from alembic import op

revision="z8d9e0f1a234"
down_revision="y7c8d9e0f123"
branch_labels=None
depends_on=None

INDEXES=(
    ("ix_repair_active_status_created","repair_order",["deleted_at","status","created_at"]),
    ("ix_repair_tech_status_created","repair_order",["assigned_technician_id","status","created_at"]),
    ("ix_repair_customer_created","repair_order",["customer_id","created_at"]),
    ("ix_booking_status_scheduled","booking",["status","scheduled_at"]),
    ("ix_booking_repair_status","booking",["repair_id","status"]),
    ("ix_lead_status_created","lead",["status","created_at"]),
    ("ix_lead_phone_created","lead",["phone","created_at"]),
    ("ix_lead_assigned_status","lead",["assigned_to_id","status"]),
    ("ix_part_active_name","part",["active","name"]),
    ("ix_purchase_supplier_status_date","purchase",["supplier_id","status","purchase_date"]),
    ("ix_purchase_status_date","purchase",["status","purchase_date"]),
    ("ix_expense_status_date","expense",["status","expense_date"]),
    ("ix_stock_allocation_status_id","stock_allocation",["status","id"]),
    ("ix_stock_allocation_part_status","stock_allocation",["part_id","status"]),
    ("ix_audit_entity_created","audit_event",["entity_type","entity_id","created_at"]),
    ("ix_webhook_endpoint_created","webhook_log",["endpoint","created_at"]),
)

def upgrade():
    for name,table,columns in INDEXES:
        op.create_index(name,table,columns,unique=False)

def downgrade():
    for name,table,_ in reversed(INDEXES):
        op.drop_index(name,table_name=table)
