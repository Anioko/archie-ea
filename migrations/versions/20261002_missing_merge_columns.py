"""Add missing columns from main merge: crud_operations, source_table/source_id/escalated_at

All four columns are also declared on their respective models, so
reconcile-schema's ADD COLUMN IF NOT EXISTS sweep (or init-db's create_all)
can already have added them by the time this revision runs -- a bare
op.add_column() then fails with "column already exists" (seen in CI on this
exact migration).  Use raw SQL with IF NOT EXISTS for every column,
matching 20261001_adr_canonical_cols.py's own idiom.

Revision ID: 20261002_missing_merge_columns
Revises: 20261001_adr_canonical_cols
Create Date: 2026-10-02
"""
from alembic import op
from sqlalchemy import text

revision = "20261002_missing_merge_columns"
down_revision = "20261001_adr_canonical_cols"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # crud_operations on archimate_relationships -- idempotent guard so a
    # second run or a prior reconcile-schema pass does not fail.
    bind.execute(text(
        "ALTER TABLE archimate_relationships "
        "ADD COLUMN IF NOT EXISTS crud_operations VARCHAR(4)"
    ))
    # Consolidation columns on ai_chat_crud_approvals
    bind.execute(text(
        "ALTER TABLE ai_chat_crud_approvals "
        "ADD COLUMN IF NOT EXISTS source_table VARCHAR(64)"
    ))
    bind.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_ai_chat_crud_approvals_source_table "
        "ON ai_chat_crud_approvals (source_table)"
    ))
    bind.execute(text(
        "ALTER TABLE ai_chat_crud_approvals "
        "ADD COLUMN IF NOT EXISTS source_id INTEGER"
    ))
    bind.execute(text(
        "ALTER TABLE ai_chat_crud_approvals "
        "ADD COLUMN IF NOT EXISTS escalated_at TIMESTAMP"
    ))


def downgrade():
    op.drop_column("ai_chat_crud_approvals", "escalated_at")
    op.drop_column("ai_chat_crud_approvals", "source_id")
    op.drop_index("ix_ai_chat_crud_approvals_source_table", table_name="ai_chat_crud_approvals")
    op.drop_column("ai_chat_crud_approvals", "source_table")
    op.drop_column("archimate_relationships", "crud_operations")