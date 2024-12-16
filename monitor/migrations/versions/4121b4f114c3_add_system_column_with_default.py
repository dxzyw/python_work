"""add system column with default

Revision ID: 4121b4f114c3
Revises: 
Create Date: 2024-12-13 17:04:24.479947

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4121b4f114c3'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('monitor_config', schema=None) as batch_op:
        batch_op.add_column(sa.Column('system', sa.String(length=100), nullable=False))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('monitor_config', schema=None) as batch_op:
        batch_op.drop_column('system')

    # ### end Alembic commands ###