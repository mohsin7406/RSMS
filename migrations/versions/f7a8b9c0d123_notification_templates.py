"""Add editable notification templates.

Revision ID: f7a8b9c0d123
Revises: e5f6a7b8c901
"""
from alembic import op
import sqlalchemy as sa

revision = "f7a8b9c0d123"
down_revision = "e5f6a7b8c901"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_template",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel", sa.String(length=20), nullable=False, server_default="sms"),
        sa.Column("event", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("body", sa.Text(), nullable=False),
        sa.UniqueConstraint("channel", "event", name="uq_notification_template_channel_event"),
    )

    templates = sa.table(
        "notification_template",
        sa.column("channel", sa.String()),
        sa.column("event", sa.String()),
        sa.column("enabled", sa.Boolean()),
        sa.column("body", sa.Text()),
    )
    op.bulk_insert(templates, [
        {"channel": "sms", "event": "repair_created", "enabled": True, "body": "FixZone: Repair job {job_number} has been created for your {device}."},
        {"channel": "sms", "event": "received", "enabled": True, "body": "FixZone: Your {device} {job_number} has been received for repair."},
        {"channel": "sms", "event": "approval_required", "enabled": True, "body": "FixZone: Approval is required for your {device} repair {job_number}. Please contact us."},
        {"channel": "sms", "event": "technician_assigned", "enabled": True, "body": "FixZone: Technician assigned for your {device} repair {job_number}."},
        {"channel": "sms", "event": "repair_ready", "enabled": True, "body": "FixZone: Your {device} repair {job_number} is ready for collection/delivery."},
        {"channel": "sms", "event": "payment_received", "enabled": True, "body": "FixZone: Payment of ₹{amount} received for repair {job_number}. Thank you."},
        {"channel": "sms", "event": "delivered", "enabled": True, "body": "FixZone: Repair {job_number} has been delivered. Thank you for choosing FixZone."},
    ])


def downgrade():
    op.drop_table("notification_template")
