"""harden customer confirmation security

Revision ID: c8d9e0f1a234
Revises: b7e8c9d0f123
"""
from alembic import op
import sqlalchemy as sa

revision = "c8d9e0f1a234"
down_revision = "b7e8c9d0f123"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("service_confirmations") as batch_op:
        batch_op.add_column(sa.Column("public_token", sa.String(length=96), nullable=True))
        batch_op.add_column(sa.Column("otp_expires_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("otp_attempts", sa.Integer(), nullable=False, server_default="0"))
        batch_op.create_index("ix_service_confirmations_public_token", ["public_token"], unique=True)


def downgrade():
    with op.batch_alter_table("service_confirmations") as batch_op:
        batch_op.drop_index("ix_service_confirmations_public_token")
        batch_op.drop_column("otp_attempts")
        batch_op.drop_column("otp_expires_at")
        batch_op.drop_column("public_token")
