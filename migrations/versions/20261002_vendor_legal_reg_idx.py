"""Create partial unique index on vendor_organizations.legal_registration_number.

The column is nullable and standard UNIQUE constraints treat NULL as distinct,
so a partial index ensures uniqueness of non-NULL values only. The model
declares this in __table_args__ with postgresql_where, but db.create_all()
does not honour that dialect-specific option, so the index must be created
by a migration (or deploy-schema.sh for existing databases).

Revision ID: 20261002_vendor_legal_reg_idx
Revises: 20261001_approval_nullable
Create Date: 2026-10-02
"""
from alembic import op
from sqlalchemy import text

revision = "20261002_vendor_legal_reg_idx"
down_revision = "20261001_approval_nullable"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    bind.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_vendor_legal_reg "
        "ON vendor_organizations(legal_registration_number) "
        "WHERE legal_registration_number IS NOT NULL"
    ))


def downgrade():
    bind = op.get_bind()
    bind.execute(text("DROP INDEX IF EXISTS uq_vendor_legal_reg"))