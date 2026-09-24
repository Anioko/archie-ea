"""Add organization_id to organization_units and application_ownership

Revision ID: add_org_id_ownership_units
Revises:
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_org_id_ownership_units'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('organization_units',
        sa.Column('organization_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_org_units_org', 'organization_units', 'organizations',
        ['organization_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_organization_units_organization_id', 'organization_units',
        ['organization_id'])

    op.add_column('application_ownership',
        sa.Column('organization_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_app_ownership_org', 'application_ownership', 'organizations',
        ['organization_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_application_ownership_organization_id', 'application_ownership',
        ['organization_id'])


def downgrade():
    op.drop_index('ix_application_ownership_organization_id', table_name='application_ownership')
    op.drop_constraint('fk_app_ownership_org', 'application_ownership', type_='foreignkey')
    op.drop_column('application_ownership', 'organization_id')

    op.drop_index('ix_organization_units_organization_id', table_name='organization_units')
    op.drop_constraint('fk_org_units_org', 'organization_units', type_='foreignkey')
    op.drop_column('organization_units', 'organization_id')