"""Add expense approval workflow.
Revision ID: v4f5a6b7c890
Revises: u3e4f5a6b789
"""
from alembic import op
import sqlalchemy as sa
revision="v4f5a6b7c890";down_revision="u3e4f5a6b789";branch_labels=None;depends_on=None

def upgrade():
    with op.batch_alter_table('expense') as batch:
        batch.add_column(sa.Column('status',sa.String(20),nullable=False,server_default='Approved'))
        batch.add_column(sa.Column('approved_by',sa.Integer(),nullable=True))
        batch.add_column(sa.Column('approved_at',sa.DateTime(),nullable=True))
        batch.create_foreign_key('fk_expense_approved_by_user','user',['approved_by'],['id'])
        batch.create_index('ix_expense_status',['status'])

def downgrade():
    with op.batch_alter_table('expense') as batch:
        batch.drop_index('ix_expense_status');batch.drop_constraint('fk_expense_approved_by_user',type_='foreignkey');batch.drop_column('approved_at');batch.drop_column('approved_by');batch.drop_column('status')
