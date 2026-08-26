"""Add safe purchase void state.

Revision ID: r0b1c2d3e456
Revises: q9a0b1c2d345
"""
from alembic import op
import sqlalchemy as sa

revision = "r0b1c2d3e456"
down_revision = "q9a0b1c2d345"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("purchase") as batch:
        batch.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="Active"))
        batch.add_column(sa.Column("void_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("voided_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("voided_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_purchase_status", ["status"])
        batch.create_foreign_key("fk_purchase_voided_by_user", "user", ["voided_by"], ["id"])


def downgrade():
    with op.batch_alter_table("purchase") as batch:
        batch.drop_constraint("fk_purchase_voided_by_user", type_="foreignkey")
        batch.drop_index("ix_purchase_status")
        batch.drop_column("voided_at")
        batch.drop_column("voided_by")
        batch.drop_column("void_reason")
        batch.drop_column("status")
