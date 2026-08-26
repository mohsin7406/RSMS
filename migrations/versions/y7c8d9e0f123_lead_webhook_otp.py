"""Add lead webhook OTP tracking and logs.
Revision ID: y7c8d9e0f123
Revises: x6b7c8d9e012
"""
from alembic import op
import sqlalchemy as sa

revision="y7c8d9e0f123"
down_revision="x6b7c8d9e012"
branch_labels=None
depends_on=None

def upgrade():
    with op.batch_alter_table("lead") as batch:
        batch.add_column(sa.Column("source_url",sa.Text(),nullable=True))
        batch.add_column(sa.Column("otp_status",sa.String(30),nullable=True))
        batch.add_column(sa.Column("otp_verified_at",sa.DateTime(),nullable=True))
        batch.create_index("ix_lead_otp_status",["otp_status"])
    op.create_table(
        "webhook_log",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("endpoint",sa.String(100),nullable=False),
        sa.Column("event_status",sa.String(40),nullable=True),
        sa.Column("phone",sa.String(30),nullable=True),
        sa.Column("source_url",sa.Text(),nullable=True),
        sa.Column("lead_id",sa.Integer(),sa.ForeignKey("lead.id"),nullable=True),
        sa.Column("result",sa.String(30),nullable=False),
        sa.Column("response_code",sa.Integer(),nullable=False),
        sa.Column("payload",sa.Text(),nullable=True),
        sa.Column("message",sa.Text(),nullable=True),
        sa.Column("created_at",sa.DateTime(),server_default=sa.func.now(),nullable=False),
    )
    op.create_index("ix_webhook_log_endpoint","webhook_log",["endpoint"])
    op.create_index("ix_webhook_log_event_status","webhook_log",["event_status"])
    op.create_index("ix_webhook_log_phone","webhook_log",["phone"])
    op.create_index("ix_webhook_log_lead_id","webhook_log",["lead_id"])
    op.create_index("ix_webhook_log_result","webhook_log",["result"])
    op.create_index("ix_webhook_log_created_at","webhook_log",["created_at"])

def downgrade():
    op.drop_table("webhook_log")
    with op.batch_alter_table("lead") as batch:
        batch.drop_index("ix_lead_otp_status")
        batch.drop_column("otp_verified_at")
        batch.drop_column("otp_status")
        batch.drop_column("source_url")
