"""Add system settings and configurable QC checklist.

Revision ID: s1c2d3e4f567
Revises: r0b1c2d3e456
"""
from alembic import op
import sqlalchemy as sa

revision = "s1c2d3e4f567"
down_revision = "r0b1c2d3e456"
branch_labels = None
depends_on = None

DEFAULT_CHECKS = [
    "Power / boot",
    "Display / touch",
    "Face ID / Touch ID",
    "Cameras",
    "Microphone / speaker",
    "Charging",
    "Wi-Fi / Bluetooth",
    "Network / SIM",
    "Buttons",
    "Physical condition",
]

DEFAULT_SETTINGS = {
    "business_name": "FixZone",
    "business_tagline": "Mobile Repair at Your Doorstep",
    "business_phone": "",
    "business_email": "",
    "business_address": "",
    "business_gstin": "",
    "invoice_terms": "Warranty applies only to the repair/service mentioned on the invoice. Physical damage and liquid damage are excluded unless specifically stated.",
    "default_warranty_days": "0",
    "invoice_prefix": "INV",
    "job_prefix": "JOB",
}


def upgrade():
    op.create_table(
        "system_setting",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_system_setting_key", "system_setting", ["key"])
    op.create_table(
        "qc_checklist_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(150), nullable=False),
        sa.Column("stage", sa.String(20), nullable=False, server_default="both"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_qc_checklist_item_stage", "qc_checklist_item", ["stage"])
    op.create_index("ix_qc_checklist_item_active", "qc_checklist_item", ["active"])
    conn = op.get_bind()
    for idx, label in enumerate(DEFAULT_CHECKS, start=1):
        conn.execute(sa.text("INSERT INTO qc_checklist_item (label, stage, sort_order, active) VALUES (:label, 'both', :sort_order, 1)"), {"label": label, "sort_order": idx * 10})
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(sa.text("INSERT INTO system_setting (key, value) VALUES (:key, :value)"), {"key": key, "value": value})


def downgrade():
    op.drop_index("ix_qc_checklist_item_active", table_name="qc_checklist_item")
    op.drop_index("ix_qc_checklist_item_stage", table_name="qc_checklist_item")
    op.drop_table("qc_checklist_item")
    op.drop_index("ix_system_setting_key", table_name="system_setting")
    op.drop_table("system_setting")
