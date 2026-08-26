"""Add supplier purchase returns.
Revision ID: p8f9a0b1c234
Revises: o7e8f9a0b123
"""
from alembic import op
import sqlalchemy as sa
revision="p8f9a0b1c234"; down_revision="o7e8f9a0b123"; branch_labels=None; depends_on=None

def upgrade():
    op.create_table("purchase_return",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("return_number",sa.String(50),nullable=False),sa.Column("purchase_id",sa.Integer(),sa.ForeignKey("purchase.id"),nullable=False),sa.Column("purchase_item_id",sa.Integer(),sa.ForeignKey("purchase_item.id"),nullable=False),sa.Column("quantity",sa.Numeric(12,2),nullable=False),sa.Column("unit_cost",sa.Numeric(12,2),nullable=False),sa.Column("reason",sa.Text(),nullable=False),sa.Column("created_by",sa.Integer(),sa.ForeignKey("user.id")),sa.Column("created_at",sa.DateTime(),server_default=sa.func.now(),nullable=False),sa.UniqueConstraint("return_number"))
    op.create_index("ix_purchase_return_return_number","purchase_return",["return_number"]); op.create_index("ix_purchase_return_purchase_id","purchase_return",["purchase_id"]); op.create_index("ix_purchase_return_purchase_item_id","purchase_return",["purchase_item_id"]); op.create_index("ix_purchase_return_created_at","purchase_return",["created_at"])

def downgrade():
    op.drop_index("ix_purchase_return_created_at",table_name="purchase_return"); op.drop_index("ix_purchase_return_purchase_item_id",table_name="purchase_return"); op.drop_index("ix_purchase_return_purchase_id",table_name="purchase_return"); op.drop_index("ix_purchase_return_return_number",table_name="purchase_return"); op.drop_table("purchase_return")
