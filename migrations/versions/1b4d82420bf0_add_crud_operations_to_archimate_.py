"""Add crud_operations to archimate_relationships

Revision ID: 1b4d82420bf0
Revises: 20261001_adr_canonical_cols
Create Date: 2026-10-02 09:36:49.920413

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1b4d82420bf0'
down_revision = '20261001_adr_canonical_cols'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("archimate_relationships", sa.Column("crud_operations", sa.String(4), nullable=True))


def downgrade():
    op.drop_column("archimate_relationships", "crud_operations")
