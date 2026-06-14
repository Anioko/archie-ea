"""
Database Migration: Add tenant_id to Architecture Assistant Models
Sprint 1.2: Multi-Tenancy Implementation

File: migrations/versions/XXXX_add_tenant_id_to_architecture_models.py

This migration adds tenant_id column to all Architecture Assistant models
to enable multi-tenant data isolation.

CRITICAL: This is a breaking change. Requires data migration for existing records.

Usage:
    flask db upgrade    # Apply migration
    flask db downgrade  # Rollback migration
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision = "add_tenant_id_arch_models"
down_revision = "previous_migration_id"  # Update with your previous migration
branch_labels = None
depends_on = None


def upgrade():
    """Add tenant_id to all architecture models"""

    # List of all tables that need tenant_id
    tables = [
        "architecture_sessions",
        "capability_gap_analysis",
        "solution_options",
        "option_comparisons",
        "arb_submission_drafts",
        "solution_option_scoring",
        "solution_cost_models",
        "solution_deployments",
        "solution_outcomes",
        "solution_stakeholders",
    ]

    print("\n" + "=" * 60)
    print("ADDING TENANT_ID TO ARCHITECTURE MODELS")
    print("=" * 60 + "\n")

    for table in tables:
        print(f"Processing table: {table}")

        # Step 1: Add tenant_id column (nullable initially)
        print(f"  → Adding tenant_id column...")
        op.add_column(table, sa.Column("tenant_id", sa.Integer(), nullable=True))

        # Step 2: Set default tenant_id for existing records
        # WARNING: This assumes tenant_id=1 exists. Adjust as needed.
        print(f"  → Setting default tenant_id for existing records...")
        op.execute(f"UPDATE {table} SET tenant_id = 1 WHERE tenant_id IS NULL")

        # Step 3: Make tenant_id non-nullable
        print(f"  → Making tenant_id non-nullable...")
        op.alter_column(table, "tenant_id", nullable=False)

        # Step 4: Add foreign key constraint
        print(f"  → Adding foreign key constraint...")
        op.create_foreign_key(f"fk_{table}_tenant", table, "tenants", ["tenant_id"], ["id"])

        # Step 5: Add index for performance
        print(f"  → Adding index...")
        op.create_index(f"idx_{table}_tenant_id", table, ["tenant_id"])

        print(f"  ✓ {table} updated\n")

    # Add composite indexes for common queries
    print("Adding composite indexes...")

    op.create_index(
        "idx_arch_sessions_tenant_created", "architecture_sessions", ["tenant_id", "created_at"]
    )

    op.create_index(
        "idx_arch_sessions_tenant_status", "architecture_sessions", ["tenant_id", "status"]
    )

    op.create_index(
        "idx_solution_options_tenant_session", "solution_options", ["tenant_id", "session_id"]
    )

    print("\n" + "=" * 60)
    print("✓ MIGRATION COMPLETE")
    print("=" * 60 + "\n")


def downgrade():
    """Remove tenant_id from all architecture models"""

    tables = [
        "architecture_sessions",
        "capability_gap_analysis",
        "solution_options",
        "option_comparisons",
        "arb_submission_drafts",
        "solution_option_scoring",
        "solution_cost_models",
        "solution_deployments",
        "solution_outcomes",
        "solution_stakeholders",
    ]

    print("\n" + "=" * 60)
    print("REMOVING TENANT_ID FROM ARCHITECTURE MODELS")
    print("=" * 60 + "\n")

    # Drop composite indexes first
    op.drop_index("idx_arch_sessions_tenant_created", "architecture_sessions")
    op.drop_index("idx_arch_sessions_tenant_status", "architecture_sessions")
    op.drop_index("idx_solution_options_tenant_session", "solution_options")

    for table in tables:
        print(f"Processing table: {table}")

        # Drop index
        op.drop_index(f"idx_{table}_tenant_id", table)

        # Drop foreign key
        op.drop_constraint(f"fk_{table}_tenant", table, type_="foreignkey")

        # Drop column
        op.drop_column(table, "tenant_id")

        print(f"  ✓ {table} reverted\n")

    print("\n" + "=" * 60)
    print("✓ ROLLBACK COMPLETE")
    print("=" * 60 + "\n")
