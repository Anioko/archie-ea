"""Add manufacturing domain hierarchy and specialization type.

Adds:
- ManufacturingDomainHierarchy table for hierarchical domains
- specialization_type field to ManufacturingCapability, UnifiedCapability, TechnicalCapability
- manufacturing_patterns field for L4 patterns
- manufacturing_domain_id FK to replace string enum
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade():
    # Create ManufacturingDomainHierarchy table
    op.create_table(
        "manufacturing_domain_hierarchy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("domain_patterns", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["manufacturing_domain_hierarchy.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(
        "ix_manufacturing_domain_hierarchy_code",
        "manufacturing_domain_hierarchy",
        ["code"],
        unique=True,
    )

    # Add columns to ManufacturingCapability
    op.add_column(
        "manufacturing_capabilities",
        sa.Column(
            "specialization_type",
            sa.String(length=50),
            nullable=True,
            server_default="MANUFACTURING",
        ),
    )
    op.add_column(
        "manufacturing_capabilities",
        sa.Column("manufacturing_domain_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "manufacturing_capabilities",
        sa.Column("manufacturing_patterns", postgresql.JSON(), nullable=True),
    )

    # Add FK constraint for manufacturing_domain_id
    op.create_foreign_key(
        "fk_manufacturing_capabilities_domain_id",
        "manufacturing_capabilities",
        "manufacturing_domain_hierarchy",
        ["manufacturing_domain_id"],
        ["id"],
    )

    # Add specialization_type to UnifiedCapability
    op.add_column(
        "unified_capabilities",
        sa.Column(
            "specialization_type", sa.String(length=50), nullable=True, server_default="BUSINESS"
        ),
    )

    # Add specialization_type to TechnicalCapability
    op.add_column(
        "technical_capabilities",
        sa.Column(
            "specialization_type", sa.String(length=50), nullable=True, server_default="TECHNICAL"
        ),
    )

    # Create indexes on specialization_type
    op.create_index(
        "ix_manufacturing_capabilities_specialization_type",
        "manufacturing_capabilities",
        ["specialization_type"],
    )
    op.create_index(
        "ix_unified_capabilities_specialization_type",
        "unified_capabilities",
        ["specialization_type"],
    )
    op.create_index(
        "ix_technical_capabilities_specialization_type",
        "technical_capabilities",
        ["specialization_type"],
    )


def downgrade():
    # Drop indexes
    op.drop_index(
        "ix_technical_capabilities_specialization_type", table_name="technical_capabilities"
    )
    op.drop_index("ix_unified_capabilities_specialization_type", table_name="unified_capabilities")
    op.drop_index(
        "ix_manufacturing_capabilities_specialization_type", table_name="manufacturing_capabilities"
    )

    # Drop FK
    op.drop_constraint(
        "fk_manufacturing_capabilities_domain_id", "manufacturing_capabilities", type_="foreignkey"
    )

    # Drop columns
    op.drop_column("technical_capabilities", "specialization_type")
    op.drop_column("unified_capabilities", "specialization_type")
    op.drop_column("manufacturing_capabilities", "manufacturing_patterns")
    op.drop_column("manufacturing_capabilities", "manufacturing_domain_id")
    op.drop_column("manufacturing_capabilities", "specialization_type")

    # Drop table
    op.drop_index(
        "ix_manufacturing_domain_hierarchy_code", table_name="manufacturing_domain_hierarchy"
    )
    op.drop_table("manufacturing_domain_hierarchy")
