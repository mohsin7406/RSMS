"""Add inventory categories and suppliers.

Revision ID: n6d7e8f9a012
Revises: m5c6d7e8f901
"""
from alembic import op
import sqlalchemy as sa

revision = "n6d7e8f9a012"
down_revision = "m5c6d7e8f901"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("inventory_category",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name"))
    op.create_index("ix_inventory_category_name", "inventory_category", ["name"])
    op.create_index("ix_inventory_category_active", "inventory_category", ["active"])
    op.create_table("supplier",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(30)), sa.Column("whatsapp", sa.String(30)), sa.Column("gstin", sa.String(30)),
        sa.Column("address", sa.Text()), sa.Column("notes", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name"))
    op.create_index("ix_supplier_name", "supplier", ["name"])
    op.create_index("ix_supplier_active", "supplier", ["active"])
    conn = op.get_bind()
    for (name,) in conn.execute(sa.text("SELECT DISTINCT category FROM part WHERE category IS NOT NULL AND trim(category) <> ''")):
        conn.execute(sa.text("INSERT OR IGNORE INTO inventory_category (name, active) VALUES (:name, 1)"), {"name": name.strip()})
    for (name,) in conn.execute(sa.text("SELECT DISTINCT supplier FROM part WHERE supplier IS NOT NULL AND trim(supplier) <> ''")):
        conn.execute(sa.text("INSERT OR IGNORE INTO supplier (name, active) VALUES (:name, 1)"), {"name": name.strip()})


def downgrade():
    op.drop_index("ix_supplier_active", table_name="supplier"); op.drop_index("ix_supplier_name", table_name="supplier"); op.drop_table("supplier")
    op.drop_index("ix_inventory_category_active", table_name="inventory_category"); op.drop_index("ix_inventory_category_name", table_name="inventory_category"); op.drop_table("inventory_category")
