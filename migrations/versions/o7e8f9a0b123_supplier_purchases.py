"""Add supplier purchase bills.
Revision ID: o7e8f9a0b123
Revises: n6d7e8f9a012
"""
from alembic import op
import sqlalchemy as sa
revision="o7e8f9a0b123"; down_revision="n6d7e8f9a012"; branch_labels=None; depends_on=None

def upgrade():
    op.create_table("purchase",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("purchase_number",sa.String(50),nullable=False),sa.Column("supplier_id",sa.Integer(),sa.ForeignKey("supplier.id"),nullable=False),sa.Column("bill_number",sa.String(100)),sa.Column("purchase_date",sa.Date(),nullable=False),sa.Column("notes",sa.Text()),sa.Column("created_by",sa.Integer(),sa.ForeignKey("user.id")),sa.Column("created_at",sa.DateTime(),server_default=sa.func.now(),nullable=False),sa.UniqueConstraint("purchase_number"))
    op.create_index("ix_purchase_purchase_number","purchase",["purchase_number"]); op.create_index("ix_purchase_supplier_id","purchase",["supplier_id"]); op.create_index("ix_purchase_bill_number","purchase",["bill_number"]); op.create_index("ix_purchase_purchase_date","purchase",["purchase_date"])
    op.create_table("purchase_item",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("purchase_id",sa.Integer(),sa.ForeignKey("purchase.id"),nullable=False),sa.Column("part_id",sa.Integer(),sa.ForeignKey("part.id"),nullable=False),sa.Column("quantity",sa.Numeric(12,2),nullable=False),sa.Column("unit_cost",sa.Numeric(12,2),nullable=False))
    op.create_index("ix_purchase_item_purchase_id","purchase_item",["purchase_id"]); op.create_index("ix_purchase_item_part_id","purchase_item",["part_id"])

def downgrade():
    op.drop_index("ix_purchase_item_part_id",table_name="purchase_item"); op.drop_index("ix_purchase_item_purchase_id",table_name="purchase_item"); op.drop_table("purchase_item"); op.drop_index("ix_purchase_purchase_date",table_name="purchase"); op.drop_index("ix_purchase_bill_number",table_name="purchase"); op.drop_index("ix_purchase_supplier_id",table_name="purchase"); op.drop_index("ix_purchase_purchase_number",table_name="purchase"); op.drop_table("purchase")
