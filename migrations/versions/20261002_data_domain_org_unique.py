"""Replace global unique index on data_domains.name with per-organisation constraint.

The global ``ix_data_domains_name`` unique index prevented two organisations
from each having a default "General" data domain.  Domain names must be unique
within an organisation, not across the whole platform.

Revision ID: 20261002_data_domain_org_unique
Revises: 20261001_approval_nullable
Create Date: 2026-10-02
"""
from alembic import op

revision = "20261002_data_domain_org_unique"
down_revision = "20261001_approval_nullable"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index(op.f("ix_data_domains_name"), table_name="data_domains")
    op.create_unique_constraint(
        "uq_data_domains_org_name", "data_domains", ["organization_id", "name"]
    )


def downgrade():
    op.drop_constraint("uq_data_domains_org_name", "data_domains", type_="unique")
    op.create_index(
        op.f("ix_data_domains_name"), "data_domains", ["name"], unique=True
    )