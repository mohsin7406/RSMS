"""production indexes and password hash size

Revision ID: 9c1f4a2b7e10
Revises: 38459182bdc3
"""
from alembic import op
import sqlalchemy as sa


revision = "9c1f4a2b7e10"
down_revision = "38459182bdc3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=128),
            type_=sa.String(length=255),
            existing_nullable=False,
        )
        batch_op.create_index("ix_user_email", ["email"], unique=False)
        batch_op.create_index("ix_user_role", ["role"], unique=False)

    with op.batch_alter_table("customer") as batch_op:
        batch_op.create_index("ix_customer_name", ["name"], unique=False)
        batch_op.create_index("ix_customer_email", ["email"], unique=False)
        batch_op.create_index("ix_customer_phone", ["phone"], unique=False)
        batch_op.create_index("ix_customer_created_at", ["created_at"], unique=False)

    with op.batch_alter_table("repair_order") as batch_op:
        batch_op.create_index("ix_repair_order_customer_id", ["customer_id"], unique=False)
        batch_op.create_index("ix_repair_order_device", ["device"], unique=False)
        batch_op.create_index("ix_repair_order_status", ["status"], unique=False)
        batch_op.create_index("ix_repair_order_created_at", ["created_at"], unique=False)


def downgrade():
    with op.batch_alter_table("repair_order") as batch_op:
        batch_op.drop_index("ix_repair_order_created_at")
        batch_op.drop_index("ix_repair_order_status")
        batch_op.drop_index("ix_repair_order_device")
        batch_op.drop_index("ix_repair_order_customer_id")

    with op.batch_alter_table("customer") as batch_op:
        batch_op.drop_index("ix_customer_created_at")
        batch_op.drop_index("ix_customer_phone")
        batch_op.drop_index("ix_customer_email")
        batch_op.drop_index("ix_customer_name")

    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_index("ix_user_role")
        batch_op.drop_index("ix_user_email")
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=255),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
