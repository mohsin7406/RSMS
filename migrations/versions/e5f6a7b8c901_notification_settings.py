"""Add SMS and WhatsApp notification settings.

Revision ID: e5f6a7b8c901
Revises: d4e5f6a7b890
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c901"
down_revision = "d4e5f6a7b890"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_setting",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("api_url", sa.String(length=500), nullable=True),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("sender_id", sa.String(length=100), nullable=True),
        sa.Column("account_id", sa.String(length=200), nullable=True),
        sa.Column("phone_number_id", sa.String(length=200), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.UniqueConstraint("channel", name="uq_notification_setting_channel"),
    )


def downgrade():
    op.drop_table("notification_setting")
