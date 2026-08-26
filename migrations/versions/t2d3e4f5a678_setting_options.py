"""Add configurable production setting options.
Revision ID: t2d3e4f5a678
Revises: s1c2d3e4f567
"""
from alembic import op
import sqlalchemy as sa
revision="t2d3e4f5a678"; down_revision="s1c2d3e4f567"; branch_labels=None; depends_on=None

def upgrade():
    op.create_table("setting_option",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("group",sa.String(50),nullable=False),sa.Column("value",sa.String(120),nullable=False),sa.Column("label",sa.String(160),nullable=False),sa.Column("sort_order",sa.Integer(),nullable=False,server_default="100"),sa.Column("active",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("created_at",sa.DateTime(),server_default=sa.func.now(),nullable=False),sa.UniqueConstraint("group","value",name="uq_setting_option_group_value"))
    op.create_index("ix_setting_option_group","setting_option",["group"])
    table=sa.table("setting_option",sa.column("group",sa.String),sa.column("value",sa.String),sa.column("label",sa.String),sa.column("sort_order",sa.Integer),sa.column("active",sa.Boolean))
    rows=[]
    defaults={"payment_methods":["Cash","UPI","Card","Bank Transfer","Other"],"service_types":["Doorstep","In Store"],"lead_sources":["Website","Phone","WhatsApp","Google","Referral","Walk-in","Other"],"expense_categories":["Petrol","Porter","Technician Travel","Advertising","Office","Job Expense","Miscellaneous"],"cancellation_reasons":["Customer Cancelled","No Response","Price Issue","Duplicate","Out of Service Area","Part Unavailable","Other"],"stock_adjustment_reasons":["Physical Count","Damaged","Lost","Correction","Return","Other"]}
    for group,values in defaults.items():
        for idx,value in enumerate(values): rows.append({"group":group,"value":value,"label":value,"sort_order":(idx+1)*10,"active":True})
    op.bulk_insert(table,rows)

def downgrade():
    op.drop_index("ix_setting_option_group",table_name="setting_option"); op.drop_table("setting_option")
