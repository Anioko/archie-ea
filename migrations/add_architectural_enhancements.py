"""
Add Architectural Enhancement Fields
Phase 3: Strategic Alignment, Dependency Mapping, Gap Analysis

Migration adds comprehensive architectural metadata fields to support:
- Solution architect needs: Strategic alignment, investment prioritization, gap analysis
- Software architect needs: Quality attributes, patterns, governance
- Deep architectural analysis and predictive modeling
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade():
    """Add architectural enhancement fields to existing tables"""

    # Extend archimate_capabilities table
    with op.batch_alter_table("archimate_capabilities", schema=None) as batch_op:
        # Strategic Alignment Fields
        batch_op.add_column(sa.Column("strategic_importance", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("investment_priority", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("strategic_objective", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("target_maturity", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("current_maturity", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("maturity_gap", sa.Integer, nullable=True))

        # Dependency Mapping Fields
        batch_op.add_column(sa.Column("depends_on", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("enables", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("criticality_score", sa.Float, nullable=True))
        batch_op.add_column(sa.Column("dependency_complexity", sa.String(20), nullable=True))

        # Gap Analysis Fields
        batch_op.add_column(sa.Column("has_capability_gap", sa.Boolean, default=False))
        batch_op.add_column(sa.Column("gap_description", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("gap_impact", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("remediation_plan", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("estimated_remediation_cost", sa.Float, nullable=True))

        # Architectural Pattern Fields
        batch_op.add_column(sa.Column("reference_architecture_id", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("design_patterns", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("architectural_principles", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("technology_constraints", sa.Text, nullable=True))

        # Quality Attributes
        batch_op.add_column(sa.Column("performance_requirements", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("scalability_requirements", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("security_requirements", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("compliance_requirements", sa.Text, nullable=True))

        # Integration Architecture
        batch_op.add_column(sa.Column("integration_patterns", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("api_architecture", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("data_integration", sa.Text, nullable=True))

        # Governance & Standards
        batch_op.add_column(sa.Column("governance_status", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("architectural_debt", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("compliance_status", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("last_architecture_review", sa.DateTime, nullable=True))
        batch_op.add_column(sa.Column("next_review_date", sa.DateTime, nullable=True))

    # Extend archimate_elements table
    with op.batch_alter_table("archimate_elements", schema=None) as batch_op:
        # Strategic Architecture Fields
        batch_op.add_column(sa.Column("strategic_alignment_score", sa.Float, nullable=True))
        batch_op.add_column(sa.Column("business_value_score", sa.Float, nullable=True))
        batch_op.add_column(sa.Column("technical_risk_score", sa.Float, nullable=True))
        batch_op.add_column(sa.Column("architectural_debt_score", sa.Float, nullable=True))

        # Capability Interdependency Tracking
        batch_op.add_column(sa.Column("dependency_level", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("upstream_dependencies", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("downstream_dependents", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("critical_path_member", sa.Boolean, default=False))

        # Quality Attributes
        batch_op.add_column(sa.Column("performance_metrics", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("scalability_metrics", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("reliability_metrics", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("security_posture", sa.Text, nullable=True))

        # Reference Architecture & Patterns
        batch_op.add_column(sa.Column("architectural_pattern", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("design_pattern_tags", sa.Text, nullable=True))
        batch_op.add_column(
            sa.Column("reference_implementation_url", sa.String(500), nullable=True)
        )
        batch_op.add_column(sa.Column("architectural_decision_records", sa.Text, nullable=True))

        # Cost & Investment Modeling
        batch_op.add_column(sa.Column("estimated_cost", sa.Float, nullable=True))
        batch_op.add_column(sa.Column("roi_score", sa.Float, nullable=True))
        batch_op.add_column(sa.Column("tco_annual", sa.Float, nullable=True))
        batch_op.add_column(sa.Column("investment_category", sa.String(50), nullable=True))

        # Governance & Compliance
        batch_op.add_column(sa.Column("architecture_review_status", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("compliance_frameworks", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("governance_standards", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("last_reviewed_date", sa.DateTime, nullable=True))
        batch_op.add_column(sa.Column("reviewer_notes", sa.Text, nullable=True))


def downgrade():
    """Remove architectural enhancement fields"""

    # Remove from archimate_capabilities
    with op.batch_alter_table("archimate_capabilities", schema=None) as batch_op:
        batch_op.drop_column("next_review_date")
        batch_op.drop_column("last_architecture_review")
        batch_op.drop_column("compliance_status")
        batch_op.drop_column("architectural_debt")
        batch_op.drop_column("governance_status")
        batch_op.drop_column("data_integration")
        batch_op.drop_column("api_architecture")
        batch_op.drop_column("integration_patterns")
        batch_op.drop_column("compliance_requirements")
        batch_op.drop_column("security_requirements")
        batch_op.drop_column("scalability_requirements")
        batch_op.drop_column("performance_requirements")
        batch_op.drop_column("technology_constraints")
        batch_op.drop_column("architectural_principles")
        batch_op.drop_column("design_patterns")
        batch_op.drop_column("reference_architecture_id")
        batch_op.drop_column("estimated_remediation_cost")
        batch_op.drop_column("remediation_plan")
        batch_op.drop_column("gap_impact")
        batch_op.drop_column("gap_description")
        batch_op.drop_column("has_capability_gap")
        batch_op.drop_column("dependency_complexity")
        batch_op.drop_column("criticality_score")
        batch_op.drop_column("enables")
        batch_op.drop_column("depends_on")
        batch_op.drop_column("maturity_gap")
        batch_op.drop_column("current_maturity")
        batch_op.drop_column("target_maturity")
        batch_op.drop_column("strategic_objective")
        batch_op.drop_column("investment_priority")
        batch_op.drop_column("strategic_importance")

    # Remove from archimate_elements
    with op.batch_alter_table("archimate_elements", schema=None) as batch_op:
        batch_op.drop_column("reviewer_notes")
        batch_op.drop_column("last_reviewed_date")
        batch_op.drop_column("governance_standards")
        batch_op.drop_column("compliance_frameworks")
        batch_op.drop_column("architecture_review_status")
        batch_op.drop_column("investment_category")
        batch_op.drop_column("tco_annual")
        batch_op.drop_column("roi_score")
        batch_op.drop_column("estimated_cost")
        batch_op.drop_column("architectural_decision_records")
        batch_op.drop_column("reference_implementation_url")
        batch_op.drop_column("design_pattern_tags")
        batch_op.drop_column("architectural_pattern")
        batch_op.drop_column("security_posture")
        batch_op.drop_column("reliability_metrics")
        batch_op.drop_column("scalability_metrics")
        batch_op.drop_column("performance_metrics")
        batch_op.drop_column("critical_path_member")
        batch_op.drop_column("downstream_dependents")
        batch_op.drop_column("upstream_dependencies")
        batch_op.drop_column("dependency_level")
        batch_op.drop_column("architectural_debt_score")
        batch_op.drop_column("technical_risk_score")
        batch_op.drop_column("business_value_score")
        batch_op.drop_column("strategic_alignment_score")
