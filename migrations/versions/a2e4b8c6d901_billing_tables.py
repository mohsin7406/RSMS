"""billing tables

Revision ID: a2e4b8c6d901
Revises: 9c1f4a2b7e10
"""
from alembic import op
import sqlalchemy as sa

revision = "a2e4b8c6d901"
down_revision = "9c1f4a2b7e10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "invoice",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_number", sa.String(length=32), nullable=False),
        sa.Column("repair_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["repair_id"], ["repair_order.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_number"),
        sa.UniqueConstraint("repair_id"),
    )
    op.create_index("ix_invoice_invoice_number", "invoice", ["invoice_number"], unique=False)
    op.create_index("ix_invoice_repair_id", "invoice", ["repair_id"], unique=False)
    op.create_index("ix_invoice_customer_id", "invoice", ["customer_id"], unique=False)
    op.create_index("ix_invoice_status", "invoice", ["status"], unique=False)

    op.create_table(
        "payment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_number", sa.String(length=32), nullable=False),
        sa.Column("repair_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=30), nullable=False),
        sa.Column("payment_type", sa.String(length=20), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("received_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["repair_id"], ["repair_order.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoice.id"]),
        sa.ForeignKeyConstraint(["received_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_number"),
    )
    op.create_index("ix_payment_payment_number", "payment", ["payment_number"], unique=False)
    op.create_index("ix_payment_repair_id", "payment", ["repair_id"], unique=False)
    op.create_index("ix_payment_invoice_id", "payment", ["invoice_id"], unique=False)
    op.create_index("ix_payment_received_by_id", "payment", ["received_by_id"], unique=False)
    op.create_index("ix_payment_created_at", "payment", ["created_at"], unique=False)


def downgrade():
    op.drop_index("ix_payment_created_at", table_name="payment")
    op.drop_index("ix_payment_received_by_id", table_name="payment")
    op.drop_index("ix_payment_invoice_id", table_name="payment")
    op.drop_index("ix_payment_repair_id", table_name="payment")
    op.drop_index("ix_payment_payment_number", table_name="payment")
    op.drop_table("payment")
    op.drop_index("ix_invoice_status", table_name="invoice")
    op.drop_index("ix_invoice_customer_id", table_name="invoice")
    op.drop_index("ix_invoice_repair_id", table_name="invoice")
    op.drop_index("ix_invoice_invoice_number", table_name="invoice")
    op.drop_table("invoice")
