"""Add specialization_type to ApplicationCapabilityMapping.

Adds APPLICATION specialization_type marker to complete 4-specialization-type system:
- TECHNICAL (TechnicalCapability)
- BUSINESS (UnifiedCapability)
- MANUFACTURING (ManufacturingCapability)
- APPLICATION (ApplicationCapabilityMapping)
"""

import sqlalchemy as sa
from alembic import op


def upgrade():
    # Add specialization_type column to ApplicationCapabilityMapping
    op.add_column(
        "application_capability_mapping",
        sa.Column(
            "specialization_type", sa.String(length=50), nullable=True, server_default="APPLICATION"
        ),
    )

    # Create index for efficient queries
    op.create_index(
        "ix_application_capability_mapping_specialization_type",
        "application_capability_mapping",
        ["specialization_type"],
    )


def downgrade():
    # Drop index
    op.drop_index(
        "ix_application_capability_mapping_specialization_type",
        table_name="application_capability_mapping",
    )

    # Drop column
    op.drop_column("application_capability_mapping", "specialization_type")
