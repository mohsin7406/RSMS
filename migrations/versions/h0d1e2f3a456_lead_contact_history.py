"""Add lead contact history and booking link.

Revision ID: h0d1e2f3a456
Revises: f8b9c0d1e234
"""
from alembic import op
import sqlalchemy as sa

revision = "h0d1e2f3a456"
down_revision = "f8b9c0d1e234"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("lead") as batch_op:
        batch_op.add_column(sa.Column("booking_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_lead_booking_id_booking", "booking", ["booking_id"], ["id"])
        batch_op.create_index("ix_lead_booking_id", ["booking_id"])

    op.create_table(
        "lead_contact",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("contacted_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
    )
    op.create_index("ix_lead_contact_lead_id", "lead_contact", ["lead_id"])
    op.create_index("ix_lead_contact_user_id", "lead_contact", ["user_id"])
    op.create_index("ix_lead_contact_contacted_at", "lead_contact", ["contacted_at"])


def downgrade():
    op.drop_table("lead_contact")
    with op.batch_alter_table("lead") as batch_op:
        batch_op.drop_index("ix_lead_booking_id")
        batch_op.drop_constraint("fk_lead_booking_id_booking", type_="foreignkey")
        batch_op.drop_column("booking_id")
