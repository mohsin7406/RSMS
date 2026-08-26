"""Add SMS delivery logs.

Revision ID: f8b9c0d1e234
Revises: f7a8b9c0d123
"""
from alembic import op
import sqlalchemy as sa

revision = "f8b9c0d1e234"
down_revision = "f7a8b9c0d123"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sms_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repair_id", sa.Integer(), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("event", sa.String(length=80), nullable=False),
        sa.Column("mobile", sa.String(length=30), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("provider_status", sa.Integer(), nullable=True),
        sa.Column("provider_response", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["repair_id"], ["repair_order.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"]),
    )


def downgrade():
    op.drop_table("sms_log")
