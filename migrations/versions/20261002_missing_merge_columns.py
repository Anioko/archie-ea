"""Add missing columns from main merge: crud_operations, source_table/source_id/escalated_at

Revision ID: 20261002_missing_merge_columns
Revises: 20261001_adr_canonical_cols
Create Date: 2026-10-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20261002_missing_merge_columns"
down_revision = "20261001_adr_canonical_cols"
branch_labels = None
depends_on = None


def upgrade():
    # crud_operations on archimate_relationships
    op.add_column(
        "archimate_relationships",
        sa.Column("crud_operations", sa.String(4), nullable=True),
    )
    # Consolidation columns on ai_chat_crud_approvals
    op.add_column(
        "ai_chat_crud_approvals",
        sa.Column("source_table", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_ai_chat_crud_approvals_source_table",
        "ai_chat_crud_approvals",
        ["source_table"],
    )
    op.add_column(
        "ai_chat_crud_approvals",
        sa.Column("source_id", sa.Integer, nullable=True),
    )
    op.add_column(
        "ai_chat_crud_approvals",
        sa.Column("escalated_at", sa.DateTime, nullable=True),
    )


def downgrade():
    op.drop_column("ai_chat_crud_approvals", "escalated_at")
    op.drop_column("ai_chat_crud_approvals", "source_id")
    op.drop_index("ix_ai_chat_crud_approvals_source_table", table_name="ai_chat_crud_approvals")
    op.drop_column("ai_chat_crud_approvals", "source_table")
    op.drop_column("archimate_relationships", "crud_operations")