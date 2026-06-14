"""Add dual capability mapping for backward compatibility.

Adds:
- technical_capability_unified_mapping table for new UnifiedCapability mapping
- is_deprecated, deprecated_as_of, deprecated_in_favor_of_id to BusinessCapability
- deprecation_notes to BusinessCapability

Keeps legacy technical_capability_business_mapping table active.
Both mapping paths work simultaneously during migration period.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade():
    # Create new mapping table: Technical Capability <-> Unified Capability
    op.create_table(
        "technical_capability_unified_mapping",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("technical_capability_id", sa.Integer(), nullable=False),
        sa.Column("unified_capability_id", sa.Integer(), nullable=False),
        sa.Column(
            "relationship_type", sa.String(length=50), nullable=True, server_default="implements"
        ),
        sa.Column("strength", sa.String(length=20), nullable=True, server_default="medium"),
        sa.Column("mapping_source", sa.String(length=50), nullable=True, server_default="manual"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["technical_capability_id"], ["technical_capabilities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["unified_capability_id"], ["unified_capabilities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "technical_capability_id", "unified_capability_id", name="idx_tech_unified_cap_mapping"
        ),
    )

    # Add deprecation fields to BusinessCapability
    op.add_column(
        "business_capability",
        sa.Column("is_deprecated", sa.Boolean(), nullable=True, server_default="false"),
    )
    op.add_column(
        "business_capability", sa.Column("deprecated_as_of", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "business_capability", sa.Column("deprecated_in_favor_of_id", sa.Integer(), nullable=True)
    )
    op.add_column("business_capability", sa.Column("deprecation_notes", sa.Text(), nullable=True))

    # Add FK constraint for deprecated_in_favor_of_id
    op.create_foreign_key(
        "fk_business_capability_deprecated_in_favor_of",
        "business_capability",
        "unified_capabilities",
        ["deprecated_in_favor_of_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add indexes
    op.create_index(
        "ix_business_capability_is_deprecated", "business_capability", ["is_deprecated"]
    )
    op.create_index(
        "ix_technical_capability_unified_mapping",
        "technical_capability_unified_mapping",
        ["technical_capability_id", "unified_capability_id"],
    )


def downgrade():
    # Drop indexes
    op.drop_index(
        "ix_technical_capability_unified_mapping", table_name="technical_capability_unified_mapping"
    )
    op.drop_index("ix_business_capability_is_deprecated", table_name="business_capability")

    # Drop FK
    op.drop_constraint(
        "fk_business_capability_deprecated_in_favor_of", "business_capability", type_="foreignkey"
    )

    # Drop columns
    op.drop_column("business_capability", "deprecation_notes")
    op.drop_column("business_capability", "deprecated_in_favor_of_id")
    op.drop_column("business_capability", "deprecated_as_of")
    op.drop_column("business_capability", "is_deprecated")

    # Drop table
    op.drop_table("technical_capability_unified_mapping")
