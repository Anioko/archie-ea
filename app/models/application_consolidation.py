"""
Application Consolidation Intelligence Models

AI-powered models for identifying duplicate applications, consolidation opportunities,
and cost-saving recommendations through portfolio rationalization.
"""

from datetime import datetime
from decimal import Decimal

from .. import db
from .mixins import TenantMixin


class ApplicationSimilarityAnalysis(db.Model):
    """
    Tracks similarity between applications for consolidation opportunities.

    Uses AI to analyze multiple dimensions:
    - Capability overlap (do they serve same business functions?)
    - Technology similarity (similar tech stacks?)
    - Functional similarity (same features?)
    - Data similarity (same data models?)
    - User overlap (same user groups?)

    High similarity scores indicate consolidation opportunities.
    """

    __tablename__ = "application_similarity_analysis"

    id = db.Column(db.Integer, primary_key=True)

    # Applications being compared
    app_1_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=False, index=True
    )
    app_2_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=False, index=True
    )

    # Similarity scores (0 - 100 for each dimension)
    capability_overlap_score = db.Column(db.Integer, default=0)  # Same business capabilities
    technology_similarity_score = db.Column(db.Integer, default=0)  # Similar tech stack
    functional_similarity_score = db.Column(db.Integer, default=0)  # Similar functions
    data_similarity_score = db.Column(db.Integer, default=0)  # Similar data models
    user_overlap_score = db.Column(db.Integer, default=0)  # Same user groups
    business_domain_match = db.Column(db.Integer, default=0)  # Same business domain
    overall_similarity_score = db.Column(db.Integer, default=0)  # Weighted average

    # Detailed overlap analysis
    shared_capabilities = db.Column(db.Text)  # JSON array of capability IDs/names
    shared_technologies = db.Column(db.Text)  # JSON array of technologies
    shared_user_types = db.Column(db.Text)  # JSON array of user types
    shared_business_processes = db.Column(db.Text)  # JSON array of process names

    # Consolidation recommendation
    consolidation_opportunity = db.Column(db.String(20), default="none")  # high, medium, low, none
    recommended_action = db.Column(
        db.String(50)
    )  # merge, retire_app1, retire_app2, standardize, keep_both
    recommended_survivor = db.Column(
        db.Integer, db.ForeignKey("application_components.id")
    )  # Which app to keep
    estimated_cost_savings = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))
    consolidation_complexity = db.Column(db.String(20))  # simple, moderate, complex, critical

    # AI analysis metadata
    analysis_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    analyzed_by_ai_model = db.Column(db.String(100))  # e.g., "gpt - 4", "claude - 3 - sonnet"
    confidence_score = db.Column(db.Float)  # 0 - 1, how confident is the AI
    reasoning = db.Column(db.Text)  # AI explanation of why these apps are similar
    analysis_version = db.Column(db.String(20), default="1.0")

    # Dependencies & constraints identified
    blocking_dependencies = db.Column(db.Text)  # JSON: factors preventing easy consolidation
    data_migration_required = db.Column(db.Boolean, default=False)
    user_migration_required = db.Column(db.Boolean, default=False)
    integration_changes_required = db.Column(db.Boolean, default=False)

    # Review & approval
    reviewed = db.Column(db.Boolean, default=False)
    reviewed_by = db.Column(db.String(200))
    reviewed_at = db.Column(db.DateTime)
    review_notes = db.Column(db.Text)

    # Relationships
    app_1 = db.relationship(
        "ApplicationComponent", foreign_keys=[app_1_id], backref="similarity_as_app1"
    )
    app_2 = db.relationship(
        "ApplicationComponent", foreign_keys=[app_2_id], backref="similarity_as_app2"
    )
    survivor_app = db.relationship("ApplicationComponent", foreign_keys=[recommended_survivor])

    # Unique constraint: only one analysis per app pair
    __table_args__ = (
        db.UniqueConstraint("app_1_id", "app_2_id", name="unique_app_pair"),
        db.Index("idx_similarity_score", "overall_similarity_score"),
        db.Index("idx_opportunity", "consolidation_opportunity"),
    )

    def __repr__(self):
        return f"<ApplicationSimilarityAnalysis App{self.app_1_id}-App{self.app_2_id} Score:{self.overall_similarity_score}>"


class ApplicationConsolidationRecommendation(TenantMixin, db.Model):
    """
    Consolidation opportunities identified by AI with business case.

    Groups multiple similar applications and recommends consolidation strategy.
    Includes financial analysis, risk assessment, and implementation roadmap.
    """

    __tablename__ = "application_consolidation_recommendations"

    id = db.Column(db.Integer, primary_key=True)

    # Recommendation identity
    recommendation_name = db.Column(db.String(255), nullable=False)
    recommendation_code = db.Column(
        db.String(50), unique=True, index=True
    )  # e.g., "CONS - 2024 - 001"
    description = db.Column(db.Text)
    consolidation_type = db.Column(db.String(50))  # merge, replace, retire, standardize, modernize

    # Applications involved
    primary_app_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=False, index=True
    )
    redundant_app_ids = db.Column(db.Text)  # JSON array of app IDs to consolidate/retire
    total_apps_in_group = db.Column(db.Integer, default=2)

    # Business case - Capabilities
    duplicate_capabilities = db.Column(db.Text)  # JSON array of capability IDs
    capability_coverage = db.Column(db.Integer)  # Percentage of overlap 0 - 100
    capability_gap_analysis = db.Column(db.Text)  # What's unique in each app

    # Business case - Financial (annual figures)
    current_total_cost = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))
    target_total_cost = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))
    estimated_annual_savings = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))

    # Cost breakdown
    license_cost_savings = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))
    infrastructure_cost_savings = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))
    maintenance_cost_savings = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))
    support_cost_savings = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))
    fte_reduction = db.Column(db.Float, default=0.0)
    personnel_cost_savings = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))

    # Implementation costs
    estimated_migration_cost = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))
    data_migration_cost = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))
    integration_update_cost = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))
    training_cost = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))
    decommission_cost = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))
    contingency_cost = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))

    # ROI metrics
    estimated_duration_months = db.Column(db.Integer)
    roi_months = db.Column(db.Integer)  # Payback period
    npv = db.Column(db.Numeric(15, 2))  # Net Present Value
    irr_percentage = db.Column(db.Float)  # Internal Rate of Return

    # Risk assessment
    migration_complexity = db.Column(db.String(20))  # simple, moderate, high, critical
    business_risk = db.Column(db.String(20))  # low, medium, high, critical
    technical_risk = db.Column(db.String(20))  # low, medium, high, critical
    data_risk = db.Column(db.String(20))  # low, medium, high, critical
    risk_mitigation_plan = db.Column(db.Text)

    # Impact assessment
    affected_users = db.Column(db.Integer, default=0)
    affected_departments = db.Column(db.Text)  # JSON array
    affected_business_processes = db.Column(db.Text)  # JSON array
    integration_dependencies = db.Column(db.Integer, default=0)  # Count of integrations to update
    integration_dependencies_detail = db.Column(db.Text)  # JSON array of integration details

    # Compliance & governance
    compliance_considerations = db.Column(db.Text)
    regulatory_approvals_required = db.Column(db.Boolean, default=False)
    data_privacy_considerations = db.Column(db.Text)
    security_review_required = db.Column(db.Boolean, default=False)

    # Implementation roadmap
    implementation_phases = db.Column(db.Text)  # JSON array of phases
    prerequisites = db.Column(db.Text)  # JSON array
    key_milestones = db.Column(db.Text)  # JSON array
    success_criteria = db.Column(db.Text)  # JSON array

    # Status & tracking
    status = db.Column(
        db.String(30), default="proposed", index=True
    )  # proposed, under_review, approved, in_progress, completed, rejected, on_hold
    priority = db.Column(db.String(20), index=True)  # critical, high, medium, low
    priority_score = db.Column(db.Integer)  # Calculated score for sorting (higher = more urgent)

    # Ownership & approval
    proposed_by = db.Column(db.String(200))
    business_sponsor = db.Column(db.String(200))
    technical_lead = db.Column(db.String(200))
    approved_by = db.Column(db.String(200))
    approval_date = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)

    # Timeline
    proposed_date = db.Column(db.DateTime, default=datetime.utcnow)
    target_start_date = db.Column(db.Date)
    target_completion_date = db.Column(db.Date)
    actual_start_date = db.Column(db.Date)
    actual_completion_date = db.Column(db.Date)

    # AI generation metadata
    generated_by_ai = db.Column(db.Boolean, default=True)
    ai_model_used = db.Column(db.String(100))
    ai_confidence_score = db.Column(db.Float)  # 0 - 1
    ai_reasoning = db.Column(db.Text)  # Why AI recommends this consolidation

    # Updates & versioning
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = db.Column(db.Integer, default=1)

    # Relationships
    primary_app = db.relationship(
        "ApplicationComponent",
        foreign_keys=[primary_app_id],
        backref="consolidation_recommendations_as_primary",
    )

    def __repr__(self):
        return f"<ApplicationConsolidationRecommendation {self.recommendation_code}: {self.recommendation_name}>"

    @property
    def total_savings_over_3_years(self):
        """Calculate 3 - year savings"""
        if self.estimated_annual_savings:
            return float(self.estimated_annual_savings) * 3
        return 0.0

    @property
    def net_benefit(self):
        """Net benefit = 3 - year savings - migration cost"""
        savings = self.total_savings_over_3_years
        cost = float(self.estimated_migration_cost) if self.estimated_migration_cost else 0.0
        return savings - cost


class ApplicationDuplicationReport(db.Model):
    """
    Portfolio-wide duplication analysis report.

    Aggregates similarity analyses into portfolio-level insights.
    Generated periodically to track consolidation progress.
    """

    __tablename__ = "application_duplication_reports"

    id = db.Column(db.Integer, primary_key=True)

    # Report identity
    report_name = db.Column(db.String(255), nullable=False)
    report_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    reporting_period_start = db.Column(db.Date)
    reporting_period_end = db.Column(db.Date)

    # Portfolio metrics
    total_applications_analyzed = db.Column(db.Integer, default=0)
    total_duplicate_pairs_found = db.Column(db.Integer, default=0)
    high_similarity_pairs = db.Column(db.Integer, default=0)  # similarity > 70
    medium_similarity_pairs = db.Column(db.Integer, default=0)  # 40 - 70
    low_similarity_pairs = db.Column(db.Integer, default=0)  # 20 - 40

    # Financial impact
    total_duplication_cost = db.Column(
        db.Numeric(15, 2), default=Decimal("0.00")
    )  # Annual cost of redundancy
    potential_annual_savings = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))
    estimated_implementation_cost = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))
    net_3year_benefit = db.Column(db.Numeric(15, 2), default=Decimal("0.00"))

    # Consolidation opportunities
    consolidation_recommendations_count = db.Column(db.Integer, default=0)
    quick_wins_count = db.Column(db.Integer, default=0)  # ROI < 12 months
    medium_term_opportunities = db.Column(db.Integer, default=0)  # ROI 12 - 24 months
    long_term_opportunities = db.Column(db.Integer, default=0)  # ROI > 24 months

    # Duplication by dimension
    capability_duplication_score = db.Column(db.Integer)  # Average capability overlap
    technology_duplication_score = db.Column(db.Integer)  # Average tech similarity
    most_duplicated_capability = db.Column(db.String(255))
    most_duplicated_technology = db.Column(db.String(255))
    most_duplicated_domain = db.Column(db.String(100))

    # Top opportunities (stored as JSON)
    top_10_opportunities = db.Column(db.Text)  # JSON array of recommendation IDs with summaries

    # Analysis coverage
    analysis_completeness = db.Column(db.Integer)  # Percentage of app pairs analyzed 0 - 100
    apps_not_analyzed = db.Column(db.Text)  # JSON array of app IDs missing data

    # Trends (vs previous report)
    duplication_trend = db.Column(db.String(20))  # increasing, decreasing, stable
    previous_report_id = db.Column(db.Integer, db.ForeignKey("application_duplication_reports.id"))
    savings_realized_since_last = db.Column(db.Numeric(15, 2))
    apps_consolidated_since_last = db.Column(db.Integer)

    # Report metadata
    generated_by = db.Column(db.String(200))
    ai_model_used = db.Column(db.String(100))
    report_status = db.Column(db.String(30), default="draft")  # draft, published, archived

    # Relationships
    previous_report = db.relationship(
        "ApplicationDuplicationReport",
        remote_side="ApplicationDuplicationReport.id",
        backref="next_reports",
    )

    def __repr__(self):
        return f"<ApplicationDuplicationReport {self.report_name} {self.report_date}>"
