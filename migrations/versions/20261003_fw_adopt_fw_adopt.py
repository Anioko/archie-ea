"""framework_adoption_harmonisation_regulatory_change

Revision ID: 20261003_fw_adopt
Revises: 20261001_approval_nullable
Create Date: 2026-10-03 00:34:30.660416

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20261003_fw_adopt'
down_revision = '20261001_approval_nullable'
branch_labels = None
depends_on = None


def upgrade():
    # Harmonisation columns on compliance_controls
    op.add_column('compliance_controls', sa.Column('harmonized_control_id', sa.Integer(), nullable=True))
    op.add_column('compliance_controls', sa.Column('harmonization_status', sa.String(length=20), nullable=True))
    op.add_column('compliance_controls', sa.Column('harmonization_notes', sa.Text(), nullable=True))
    op.create_index(op.f('ix_compliance_controls_harmonized_control_id'), 'compliance_controls', ['harmonized_control_id'], unique=False)
    op.create_foreign_key(None, 'compliance_controls', 'compliance_controls', ['harmonized_control_id'], ['id'])

    # Framework adoptions (tenant-hybrid)
    op.create_table('framework_adoptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('scope', sa.String(length=16), nullable=True),
        sa.Column('framework_id', sa.Integer(), nullable=False),
        sa.Column('reference_adoption_id', sa.Integer(), nullable=True),
        sa.Column('adopted_by_id', sa.Integer(), nullable=True),
        sa.Column('adopted_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('tailoring_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['adopted_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['framework_id'], ['regulatory_frameworks.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reference_adoption_id'], ['framework_adoptions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'framework_id', name='uq_org_framework_adoption'),
    )
    op.create_index(op.f('ix_framework_adoptions_framework_id'), 'framework_adoptions', ['framework_id'], unique=False)
    op.create_index(op.f('ix_framework_adoptions_organization_id'), 'framework_adoptions', ['organization_id'], unique=False)
    op.create_index(op.f('ix_framework_adoptions_scope'), 'framework_adoptions', ['scope'], unique=False)

    # Adopted controls (tenant-hybrid)
    op.create_table('adopted_controls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('scope', sa.String(length=16), nullable=True),
        sa.Column('adoption_id', sa.Integer(), nullable=False),
        sa.Column('control_id', sa.Integer(), nullable=False),
        sa.Column('tailoring_notes', sa.Text(), nullable=True),
        sa.Column('implementation_status', sa.String(length=20), nullable=True),
        sa.Column('evidence_url', sa.String(length=500), nullable=True),
        sa.Column('verified_date', sa.DateTime(), nullable=True),
        sa.Column('verified_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['adoption_id'], ['framework_adoptions.id'], ),
        sa.ForeignKeyConstraint(['control_id'], ['compliance_controls.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['verified_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'adoption_id', 'control_id', name='uq_org_adoption_control'),
    )
    op.create_index(op.f('ix_adopted_controls_adoption_id'), 'adopted_controls', ['adoption_id'], unique=False)
    op.create_index(op.f('ix_adopted_controls_control_id'), 'adopted_controls', ['control_id'], unique=False)
    op.create_index(op.f('ix_adopted_controls_organization_id'), 'adopted_controls', ['organization_id'], unique=False)
    op.create_index(op.f('ix_adopted_controls_scope'), 'adopted_controls', ['scope'], unique=False)

    # Regulatory changes
    op.create_table('regulatory_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('framework_id', sa.Integer(), nullable=False),
        sa.Column('change_type', sa.String(length=30), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('effective_date', sa.Date(), nullable=True),
        sa.Column('source_url', sa.String(length=500), nullable=True),
        sa.Column('recorded_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['framework_id'], ['regulatory_frameworks.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recorded_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_regulatory_changes_framework_id'), 'regulatory_changes', ['framework_id'], unique=False)
    op.create_index(op.f('ix_regulatory_changes_organization_id'), 'regulatory_changes', ['organization_id'], unique=False)

    # Regulatory change impacts
    op.create_table('regulatory_change_impacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('change_id', sa.Integer(), nullable=False),
        sa.Column('element_type', sa.String(length=50), nullable=False),
        sa.Column('element_id', sa.Integer(), nullable=False),
        sa.Column('element_name', sa.String(length=500), nullable=True),
        sa.Column('impact_assessment', sa.Text(), nullable=True),
        sa.Column('owner_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['change_id'], ['regulatory_changes.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_regulatory_change_impacts_change_id'), 'regulatory_change_impacts', ['change_id'], unique=False)
    op.create_index(op.f('ix_regulatory_change_impacts_organization_id'), 'regulatory_change_impacts', ['organization_id'], unique=False)


def downgrade():
    op.drop_table('regulatory_change_impacts')
    op.drop_table('regulatory_changes')
    op.drop_table('adopted_controls')
    op.drop_table('framework_adoptions')

    op.drop_constraint(None, 'compliance_controls', type_='foreignkey')
    op.drop_index(op.f('ix_compliance_controls_harmonized_control_id'), table_name='compliance_controls')
    op.drop_column('compliance_controls', 'harmonization_notes')
    op.drop_column('compliance_controls', 'harmonization_status')
    op.drop_column('compliance_controls', 'harmonized_control_id')