"""Add gateway fields to llm_interactions, create model_providers

Revision ID: add_gateway_fields_and_model_providers
Revises: wft069_workflow_instance_archimate_elements
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "add_gateway_fields_and_model_providers"
down_revision = "wft069_workflow_instance_archimate_elements"
branch_labels = None
depends_on = None


def upgrade():
    # Add gateway columns to llm_interactions
    try:
        op.add_column("llm_interactions", sa.Column("organization_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_llm_interactions_organization_id",
            "llm_interactions", "organizations",
            ["organization_id"], ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_llm_interactions_organization_id", "llm_interactions", ["organization_id"])
    except Exception:
        pass

    try:
        op.add_column("llm_interactions", sa.Column("prompt_version", sa.String(32), nullable=True))
    except Exception:
        pass

    try:
        op.add_column("llm_interactions", sa.Column("retention_setting", sa.String(50), nullable=True))
    except Exception:
        pass

    # Create model_providers table
    try:
        op.create_table(
            "model_providers",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(100), nullable=False),
            sa.Column("model_version", sa.String(255), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=True),
            sa.Column("is_platform_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("is_allowed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "provider", "model_version", "organization_id",
                name="uq_model_provider_org",
            ),
        )
        op.create_index("ix_model_providers_provider", "model_providers", ["provider"])
        op.create_index("ix_model_providers_organization_id", "model_providers", ["organization_id"])
    except Exception:
        pass


def downgrade():
    try:
        op.drop_constraint("fk_llm_interactions_organization_id", "llm_interactions", type_="foreignkey")
    except Exception:
        pass
    try:
        op.drop_index("ix_llm_interactions_organization_id", table_name="llm_interactions")
    except Exception:
        pass
    try:
        op.drop_column("llm_interactions", "organization_id")
    except Exception:
        pass
    try:
        op.drop_column("llm_interactions", "prompt_version")
    except Exception:
        pass
    try:
        op.drop_column("llm_interactions", "retention_setting")
    except Exception:
    pass

    try:
        op.drop_table("model_providers")
    except Exception:
        pass