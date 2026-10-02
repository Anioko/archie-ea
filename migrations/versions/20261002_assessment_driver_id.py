"""Add driver_id FK to assessments table.

An Assessment is conducted against a Driver; this column records that link.
Nullable: historical assessments predate this column and have no driver to
attribute.

Revision ID: 20261002_assessment_driver_id
Revises: 20261001_approval_nullable
Create Date: 2026-10-02
"""
from alembic import op
from sqlalchemy import text

revision = "20261002_assessment_driver_id"
down_revision = "20261001_approval_nullable"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    bind.execute(text(
        "ALTER TABLE assessments ADD COLUMN driver_id INTEGER"
    ))
    bind.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_assessments_driver_id ON assessments (driver_id)"
    ))
    bind.execute(text(
        "ALTER TABLE assessments ADD CONSTRAINT fk_assessments_driver_id "
        "FOREIGN KEY (driver_id) REFERENCES drivers (id)"
    ))


def downgrade():
    bind = op.get_bind()
    bind.execute(text(
        "ALTER TABLE assessments DROP CONSTRAINT IF EXISTS fk_assessments_driver_id"
    ))
    bind.execute(text(
        "DROP INDEX IF EXISTS ix_assessments_driver_id"
    ))
    bind.execute(text(
        "ALTER TABLE assessments DROP COLUMN IF EXISTS driver_id"
    ))