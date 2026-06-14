"""
Capability Gap Analysis Framework

Comprehensive gap analysis system for capability-application mapping.
Provides systematic identification of capability gaps and optimization opportunities.
Supports strategic decision-making and investment prioritization.

Features:
- Systematic gap analysis methodology
- Coverage assessment and scoring
- Gap prioritization and impact analysis
- Investment recommendations
- Roadmap planning
- Performance tracking
"""

from datetime import datetime
from typing import Any, Dict, List, Optional  # dead-code-ok

from sqlalchemy import (  # dead-code-ok
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .. import db
from .mixins import TenantMixin


class CapabilityGapAnalysis(TenantMixin, db.Model):
    """
    Capability Gap Analysis Model

    Core gap analysis framework for capability-application mapping.
    Identifies gaps between required capabilities and current application support.
    """

    __tablename__ = "capability_gap_analysis"

    id = Column(db.Integer, primary_key=True)

    # Analysis identity
    analysis_name = Column(db.String(256), nullable=False, index=True)
    analysis_description = Column(db.Text)
    analysis_code = Column(db.String(50), unique=True, index=True)  # e.g., GA - 2024 - Q1

    # Analysis scope
    scope_type = Column(db.String(30))  # enterprise, domain, capability, value_stream
    scope_description = Column(db.Text)
    business_domains = Column(db.Text)  # JSON array of domain codes
    capability_levels = Column(db.Text)  # JSON array of capability levels (L1, L2, L3)

    # Analysis methodology
    methodology = Column(db.String(50))  # quantitative, qualitative, hybrid
    data_sources = Column(db.Text)  # JSON array of data sources
    assessment_framework = Column(db.String(50))  # custom, industry_standard, best_practice

    # Analysis metadata
    analyst = Column(db.String(100))
    reviewer = Column(db.String(100))
    approver = Column(db.String(100))

    # Timeline
    start_date = Column(db.Date)
    completion_date = Column(db.Date)
    next_review_date = Column(db.Date)

    # Status
    status = Column(
        db.String(20), default="planned"
    )  # planned, in_progress, completed, approved, archived

    # Summary metrics
    total_capabilities_assessed = Column(db.Integer, default=0)
    capabilities_fully_covered = Column(db.Integer, default=0)
    capabilities_partially_covered = Column(db.Integer, default=0)
    capabilities_with_gaps = Column(db.Integer, default=0)
    overall_coverage_percentage = Column(db.Float, default=0)

    # Gap metrics
    critical_gaps = Column(db.Integer, default=0)
    high_priority_gaps = Column(db.Integer, default=0)
    medium_priority_gaps = Column(db.Integer, default=0)
    low_priority_gaps = Column(db.Integer, default=0)

    # Financial impact
    total_investment_required = Column(db.Float, default=0)
    estimated_annual_value = Column(db.Float, default=0)
    average_payback_period_months = Column(db.Integer, default=0)
    roi_percentage = Column(db.Float, default=0)

    # Manufacturing specific
    manufacturing_gaps = Column(db.Integer, default=0)
    manufacturing_critical_gaps = Column(db.Integer, default=0)
    production_impact_gaps = Column(db.Integer, default=0)

    # Timestamps
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    gap_details = relationship("CapabilityGapDetail", back_populates="analysis")
    recommendations = relationship("GapAnalysisRecommendation", back_populates="analysis")

    def __repr__(self):
        return f"<CapabilityGapAnalysis {self.analysis_name}>"

    def calculate_coverage_metrics(self):
        """Calculate coverage metrics based on gap details"""
        total = len(self.gap_details)
        if total == 0:
            return

        fully_covered = len([g for g in self.gap_details if g.coverage_status == "fully_covered"])
        partially_covered = len(
            [g for g in self.gap_details if g.coverage_status == "partially_covered"]
        )
        with_gaps = len([g for g in self.gap_details if g.coverage_status == "gap"])

        self.total_capabilities_assessed = total
        self.capabilities_fully_covered = fully_covered
        self.capabilities_partially_covered = partially_covered
        self.capabilities_with_gaps = with_gaps
        self.overall_coverage_percentage = (fully_covered / total) * 100 if total > 0 else 0

        db.session.commit()

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "analysis_name": self.analysis_name,
            "analysis_description": self.analysis_description,
            "analysis_code": self.analysis_code,
            "scope_type": self.scope_type,
            "scope_description": self.scope_description,
            "methodology": self.methodology,
            "analyst": self.analyst,
            "reviewer": self.reviewer,
            "approver": self.approver,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "completion_date": self.completion_date.isoformat() if self.completion_date else None,
            "next_review_date": self.next_review_date.isoformat()
            if self.next_review_date
            else None,
            "status": self.status,
            "total_capabilities_assessed": self.total_capabilities_assessed,
            "capabilities_fully_covered": self.capabilities_fully_covered,
            "capabilities_partially_covered": self.capabilities_partially_covered,
            "capabilities_with_gaps": self.capabilities_with_gaps,
            "overall_coverage_percentage": self.overall_coverage_percentage,
            "critical_gaps": self.critical_gaps,
            "high_priority_gaps": self.high_priority_gaps,
            "medium_priority_gaps": self.medium_priority_gaps,
            "low_priority_gaps": self.low_priority_gaps,
            "total_investment_required": self.total_investment_required,
            "estimated_annual_value": self.estimated_annual_value,
            "average_payback_period_months": self.average_payback_period_months,
            "roi_percentage": self.roi_percentage,
            "manufacturing_gaps": self.manufacturing_gaps,
            "manufacturing_critical_gaps": self.manufacturing_critical_gaps,
            "production_impact_gaps": self.production_impact_gaps,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CapabilityGapDetail(db.Model):
    """
    Capability Gap Detail Model

    Detailed gap analysis for individual capabilities.
    Provides comprehensive assessment of capability coverage and gaps.
    """

    __tablename__ = "capability_gap_details"

    id = Column(db.Integer, primary_key=True)

    # Link entities
    analysis_id = Column(db.Integer, db.ForeignKey("capability_gap_analysis.id"), nullable=False)
    capability_id = Column(db.Integer, db.ForeignKey("unified_capabilities.id"), nullable=False)

    # Gap assessment
    coverage_status = Column(
        db.String(20), default="unknown"
    )  # fully_covered, partially_covered, gap, excess
    coverage_percentage = Column(db.Integer, default=0)  # 0 - 100% coverage
    gap_severity = Column(db.String(20), default="medium", index=True)  # critical, high, medium, low

    # Gap description
    gap_description = Column(db.Text)
    gap_root_cause = Column(db.Text)
    business_impact = Column(db.Text)

    # Current state assessment
    current_applications = Column(db.Text)  # JSON array of supporting applications
    current_coverage_quality = Column(db.Integer, default=1)  # 1 - 5 quality scale
    current_integration_level = Column(db.String(20))  # low, medium, high
    current_maturity = Column(db.Integer, default=1)  # 1 - 5 maturity scale

    # Target state requirements
    required_coverage_percentage = Column(db.Integer, default=100)  # Required coverage
    required_quality_level = Column(db.Integer, default=4)  # Required quality level
    required_maturity_level = Column(db.Integer, default=3)  # Required maturity level
    target_integration_level = Column(db.String(20), default="high")

    # Gap impact analysis
    business_impact_score = Column(db.Integer, default=3)  # 1 - 10 impact score
    operational_impact_score = Column(db.Integer, default=3)  # 1 - 10 operational impact
    financial_impact_score = Column(db.Integer, default=3)  # 1 - 10 financial impact
    risk_impact_score = Column(db.Integer, default=3)  # 1 - 10 risk impact

    # Priority assessment
    priority_score = Column(db.Integer, default=3)  # 1 - 10 priority score
    urgency_level = Column(db.String(20), default="medium")  # immediate, high, medium, low
    strategic_alignment = Column(db.String(20), default="medium")  # high, medium, low

    # Solution requirements
    solution_type = Column(
        db.String(50)
    )  # new_application, enhance_existing, process_change, organizational_change
    solution_complexity = Column(db.String(20), default="medium")  # low, medium, high
    estimated_effort_person_days = Column(db.Integer)
    estimated_cost = Column(db.Float)

    # Value proposition
    expected_benefits = Column(db.Text)  # JSON array of expected benefits
    quantified_value = Column(db.Float)  # Annual quantified value
    value_realization_timeline = Column(db.Integer)  # Months to realize value

    # Manufacturing specific
    manufacturing_impact = Column(db.String(20), default="medium")  # critical, high, medium, low
    production_impact = Column(db.String(20), default="medium")  # critical, high, medium, low
    quality_impact = Column(db.String(20), default="medium")  # critical, high, medium, low
    safety_impact = Column(db.String(20), default="low")  # critical, high, medium, low

    # Dependencies
    prerequisite_capabilities = Column(db.Text)  # JSON array of prerequisite capabilities
    dependent_capabilities = Column(db.Text)  # JSON array of dependent capabilities
    required_technologies = Column(db.Text)  # JSON array of required technologies

    # Assessment metadata
    assessor = Column(db.String(100))
    assessment_date = Column(db.DateTime, default=datetime.utcnow)
    confidence_level = Column(db.Integer, default=3)  # 1 - 5 confidence in assessment
    assessment_notes = Column(db.Text)

    # Timestamps
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    analysis = relationship("CapabilityGapAnalysis", back_populates="gap_details")
    capability = relationship("UnifiedCapability")
    solution_options = relationship("GapSolutionOption", back_populates="gap_detail")

    def __repr__(self):
        return f"<CapabilityGapDetail {self.capability.name} - {self.coverage_status}>"

    def calculate_priority_score(self):
        """Calculate priority score based on impact factors"""
        weights = {
            "business_impact": 0.3,
            "operational_impact": 0.25,
            "financial_impact": 0.25,
            "risk_impact": 0.2,
        }

        score = (
            self.business_impact_score * weights["business_impact"]
            + self.operational_impact_score * weights["operational_impact"]
            + self.financial_impact_score * weights["financial_impact"]
            + self.risk_impact_score * weights["risk_impact"]
        )

        self.priority_score = round(score, 1)
        db.session.commit()
        return self.priority_score

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "capability_id": self.capability_id,
            "capability_name": self.capability.name if self.capability else None,
            "capability_code": self.capability.code if self.capability else None,
            "coverage_status": self.coverage_status,
            "coverage_percentage": self.coverage_percentage,
            "gap_severity": self.gap_severity,
            "gap_description": self.gap_description,
            "gap_root_cause": self.gap_root_cause,
            "business_impact": self.business_impact,
            "current_coverage_quality": self.current_coverage_quality,
            "current_integration_level": self.current_integration_level,
            "current_maturity": self.current_maturity,
            "required_coverage_percentage": self.required_coverage_percentage,
            "required_quality_level": self.required_quality_level,
            "required_maturity_level": self.required_maturity_level,
            "target_integration_level": self.target_integration_level,
            "business_impact_score": self.business_impact_score,
            "operational_impact_score": self.operational_impact_score,
            "financial_impact_score": self.financial_impact_score,
            "risk_impact_score": self.risk_impact_score,
            "priority_score": self.priority_score,
            "urgency_level": self.urgency_level,
            "strategic_alignment": self.strategic_alignment,
            "solution_type": self.solution_type,
            "solution_complexity": self.solution_complexity,
            "estimated_effort_person_days": self.estimated_effort_person_days,
            "estimated_cost": self.estimated_cost,
            "quantified_value": self.quantified_value,
            "value_realization_timeline": self.value_realization_timeline,
            "manufacturing_impact": self.manufacturing_impact,
            "production_impact": self.production_impact,
            "quality_impact": self.quality_impact,
            "safety_impact": self.safety_impact,
            "assessor": self.assessor,
            "assessment_date": self.assessment_date.isoformat() if self.assessment_date else None,
            "confidence_level": self.confidence_level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class GapSolutionOption(db.Model):
    """
    Gap Solution Option Model

    Solution options for addressing capability gaps.
    Provides alternative approaches with cost-benefit analysis.
    """

    __tablename__ = "gap_solution_options"

    id = Column(db.Integer, primary_key=True)

    # Link entities
    gap_detail_id = Column(db.Integer, db.ForeignKey("capability_gap_details.id"), nullable=False)

    # Solution identity
    solution_name = Column(db.String(256), nullable=False)
    solution_description = Column(db.Text)
    solution_type = Column(
        db.String(50)
    )  # new_application, enhance_existing, process_change, organizational_change, outsourcing

    # Solution characteristics
    solution_approach = Column(db.String(50))  # build, buy, configure, integrate, automate
    technology_approach = Column(db.String(50))  # custom, packaged, saas, open_source
    implementation_approach = Column(db.String(50))  # big_bang, phased, pilot, parallel

    # Cost analysis
    implementation_cost = Column(db.Float)  # One-time implementation cost
    annual_operating_cost = Column(db.Float)  # Annual operating cost
    licensing_cost = Column(db.Float)  # Annual licensing cost
    training_cost = Column(db.Float)  # One-time training cost
    change_management_cost = Column(db.Float)  # Change management cost
    total_cost_of_ownership = Column(db.Float)  # 3 - year TCO

    # Benefits analysis
    annual_value_realization = Column(db.Float)  # Annual value from solution
    productivity_improvement = Column(db.Integer)  # Percentage productivity improvement
    quality_improvement = Column(db.Integer)  # Percentage quality improvement
    cost_reduction = Column(db.Integer)  # Percentage cost reduction
    risk_reduction = Column(db.Integer)  # Percentage risk reduction

    # Financial metrics
    payback_period_months = Column(db.Integer)  # Payback period in months
    roi_percentage = Column(db.Float)  # ROI percentage
    npv = Column(db.Float)  # Net present value
    irr = Column(db.Float)  # Internal rate of return

    # Implementation details
    implementation_duration_months = Column(db.Integer)  # Implementation timeline
    resource_requirements = Column(db.Text)  # JSON array of resource requirements
    skill_requirements = Column(db.Text)  # JSON array of skill requirements
    vendor_requirements = Column(db.Text)  # JSON array of vendor requirements

    # Risk assessment
    implementation_risk = Column(db.String(20))  # low, medium, high, critical
    technology_risk = Column(db.String(20))  # low, medium, high, critical
    business_risk = Column(db.String(20))  # low, medium, high, critical
    adoption_risk = Column(db.String(20))  # low, medium, high, critical

    # Manufacturing specific
    production_disruption_risk = Column(db.String(20))  # low, medium, high, critical
    quality_assurance_requirements = Column(db.Text)  # JSON array of QA requirements
    regulatory_compliance_impact = Column(db.String(20))  # low, medium, high, critical

    # Solution assessment
    feasibility_score = Column(db.Integer, default=3)  # 1 - 5 feasibility score
    alignment_score = Column(db.Integer, default=3)  # 1 - 5 strategic alignment score
    sustainability_score = Column(db.Integer, default=3)  # 1 - 5 sustainability score
    overall_score = Column(db.Integer, default=3)  # 1 - 5 overall score

    # OA-002: scoring columns
    prioritisation_score = Column(db.Float, nullable=True)
    implementation_cost_estimate = Column(db.String(50), nullable=True)
    time_to_implement_weeks = Column(db.Integer, nullable=True)
    strategic_alignment_score = Column(db.Float, nullable=True)

    # Recommendation
    recommended = Column(db.Boolean, default=False)
    recommendation_rank = Column(db.Integer)  # Rank among options
    recommendation_rationale = Column(db.Text)

    # Metadata
    solution_provider = Column(db.String(100))  # Vendor or internal team
    reference_accounts = Column(db.Text)  # JSON array of reference accounts
    case_studies = Column(db.Text)  # JSON array of relevant case studies

    # Timestamps
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    gap_detail = relationship("CapabilityGapDetail", back_populates="solution_options")

    def __repr__(self):
        return f"<GapSolutionOption {self.solution_name}>"

    def calculate_financial_metrics(self):
        """Calculate financial metrics"""
        if self.annual_value_realization and self.total_cost_of_ownership:
            # Simple ROI calculation
            self.roi_percentage = (
                self.annual_value_realization / self.total_cost_of_ownership
            ) * 100

        if self.total_cost_of_ownership and self.annual_value_realization:
            # Simple payback calculation
            self.payback_period_months = (
                self.total_cost_of_ownership / self.annual_value_realization
            ) * 12

        db.session.commit()

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "gap_detail_id": self.gap_detail_id,
            "solution_name": self.solution_name,
            "solution_description": self.solution_description,
            "solution_type": self.solution_type,
            "solution_approach": self.solution_approach,
            "technology_approach": self.technology_approach,
            "implementation_approach": self.implementation_approach,
            "implementation_cost": self.implementation_cost,
            "annual_operating_cost": self.annual_operating_cost,
            "licensing_cost": self.licensing_cost,
            "training_cost": self.training_cost,
            "change_management_cost": self.change_management_cost,
            "total_cost_of_ownership": self.total_cost_of_ownership,
            "annual_value_realization": self.annual_value_realization,
            "productivity_improvement": self.productivity_improvement,
            "quality_improvement": self.quality_improvement,
            "cost_reduction": self.cost_reduction,
            "risk_reduction": self.risk_reduction,
            "payback_period_months": self.payback_period_months,
            "roi_percentage": self.roi_percentage,
            "npv": self.npv,
            "irr": self.irr,
            "implementation_duration_months": self.implementation_duration_months,
            "implementation_risk": self.implementation_risk,
            "technology_risk": self.technology_risk,
            "business_risk": self.business_risk,
            "adoption_risk": self.adoption_risk,
            "production_disruption_risk": self.production_disruption_risk,
            "feasibility_score": self.feasibility_score,
            "alignment_score": self.alignment_score,
            "sustainability_score": self.sustainability_score,
            "overall_score": self.overall_score,
            "recommended": self.recommended,
            "recommendation_rank": self.recommendation_rank,
            "recommendation_rationale": self.recommendation_rationale,
            "solution_provider": self.solution_provider,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class GapAnalysisRecommendation(db.Model):
    """
    Gap Analysis Recommendation Model

    Strategic recommendations based on gap analysis.
    Provides actionable insights for capability improvement.
    """

    __tablename__ = "gap_analysis_recommendations"

    id = Column(db.Integer, primary_key=True)

    # Link entities
    analysis_id = Column(db.Integer, db.ForeignKey("capability_gap_analysis.id"), nullable=False)

    # Recommendation identity
    recommendation_title = Column(db.String(256), nullable=False)
    recommendation_description = Column(db.Text)
    recommendation_type = Column(db.String(50))  # strategic, tactical, operational, financial

    # Recommendation classification
    category = Column(
        db.String(50)
    )  # investment, consolidation, modernization, optimization, retirement
    priority = Column(db.String(20))  # critical, high, medium, low
    urgency = Column(db.String(20))  # immediate, short_term, medium_term, long_term

    # Business case
    business_problem = Column(db.Text)
    proposed_solution = Column(db.Text)
    expected_outcomes = Column(db.Text)  # JSON array of expected outcomes
    success_metrics = Column(db.Text)  # JSON array of success metrics

    # Financial impact
    investment_required = Column(db.Float)
    annual_benefits = Column(db.Float)
    payback_period_months = Column(db.Integer)
    roi_percentage = Column(db.Float)
    risk_adjusted_roi = Column(db.Float)

    # Implementation requirements
    implementation_timeline_months = Column(db.Integer)
    resource_requirements = Column(db.Text)  # JSON array of resource requirements
    skill_requirements = Column(db.Text)  # JSON array of skill requirements
    dependencies = Column(db.Text)  # JSON array of dependencies

    # Risk assessment
    implementation_risk = Column(db.String(20))  # low, medium, high, critical
    business_risk = Column(db.String(20))  # low, medium, high, critical
    financial_risk = Column(db.String(20))  # low, medium, high, critical
    mitigation_strategies = Column(db.Text)  # JSON array of mitigation strategies

    # Stakeholder impact
    affected_departments = Column(db.Text)  # JSON array of affected departments
    stakeholder_analysis = Column(db.Text)  # JSON array of stakeholder impacts
    change_management_requirements = Column(db.Text)  # JSON array of change management requirements

    # Manufacturing specific
    production_impact = Column(db.String(20))  # low, medium, high, critical
    quality_impact = Column(db.String(20))  # low, medium, high, critical
    safety_impact = Column(db.String(20))  # low, medium, high, critical
    regulatory_impact = Column(db.String(20))  # low, medium, high, critical

    # Governance
    recommendation_owner = Column(db.String(100))
    approval_required = Column(db.String(100))  # JSON array of approval authorities
    governance_requirements = Column(db.Text)  # JSON array of governance requirements

    # Tracking
    status = Column(
        db.String(20), default="recommended"
    )  # recommended, approved, in_progress, completed, rejected
    approval_date = Column(db.Date)
    implementation_start_date = Column(db.Date)
    expected_completion_date = Column(db.Date)
    actual_completion_date = Column(db.Date)

    # Results
    actual_investment = Column(db.Float)
    actual_benefits = Column(db.Float)
    actual_payback_period_months = Column(db.Integer)
    actual_roi_percentage = Column(db.Float)
    lessons_learned = Column(db.Text)

    # Metadata
    confidence_level = Column(db.Integer, default=3)  # 1 - 5 confidence in recommendation
    data_sources = Column(db.Text)  # JSON array of data sources
    assumptions = Column(db.Text)  # JSON array of assumptions

    # Timestamps
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    analysis = relationship("CapabilityGapAnalysis", back_populates="recommendations")

    def __repr__(self):
        return f"<GapAnalysisRecommendation {self.recommendation_title}>"

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "recommendation_title": self.recommendation_title,
            "recommendation_description": self.recommendation_description,
            "recommendation_type": self.recommendation_type,
            "category": self.category,
            "priority": self.priority,
            "urgency": self.urgency,
            "business_problem": self.business_problem,
            "proposed_solution": self.proposed_solution,
            "investment_required": self.investment_required,
            "annual_benefits": self.annual_benefits,
            "payback_period_months": self.payback_period_months,
            "roi_percentage": self.roi_percentage,
            "risk_adjusted_roi": self.risk_adjusted_roi,
            "implementation_timeline_months": self.implementation_timeline_months,
            "implementation_risk": self.implementation_risk,
            "business_risk": self.business_risk,
            "financial_risk": self.financial_risk,
            "production_impact": self.production_impact,
            "quality_impact": self.quality_impact,
            "safety_impact": self.safety_impact,
            "regulatory_impact": self.regulatory_impact,
            "recommendation_owner": self.recommendation_owner,
            "status": self.status,
            "approval_date": self.approval_date.isoformat() if self.approval_date else None,
            "implementation_start_date": self.implementation_start_date.isoformat()
            if self.implementation_start_date
            else None,
            "expected_completion_date": self.expected_completion_date.isoformat()
            if self.expected_completion_date
            else None,
            "actual_completion_date": self.actual_completion_date.isoformat()
            if self.actual_completion_date
            else None,
            "actual_investment": self.actual_investment,
            "actual_benefits": self.actual_benefits,
            "actual_payback_period_months": self.actual_payback_period_months,
            "actual_roi_percentage": self.actual_roi_percentage,
            "confidence_level": self.confidence_level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CapabilityGapDashboard(db.Model):
    """
    Capability Gap Dashboard Model

    Dashboard configuration and metrics for gap analysis visualization.
    Supports executive reporting and performance tracking.
    """

    __tablename__ = "capability_gap_dashboard"

    id = Column(db.Integer, primary_key=True)

    # Dashboard identity
    dashboard_name = Column(db.String(256), nullable=False, index=True)
    dashboard_description = Column(db.Text)
    dashboard_type = Column(db.String(30))  # executive, operational, detailed, trend

    # Dashboard configuration
    scope_filter = Column(db.Text)  # JSON filter for scope
    time_period = Column(db.String(30))  # current, quarterly, annual, custom
    comparison_period = Column(db.String(30))  # previous_period, same_period_last_year

    # Metrics configuration
    primary_metrics = Column(db.Text)  # JSON array of primary metrics
    secondary_metrics = Column(db.Text)  # JSON array of secondary metrics
    trend_metrics = Column(db.Text)  # JSON array of trend metrics

    # Visualization settings
    chart_types = Column(db.Text)  # JSON array of chart types
    color_scheme = Column(db.String(50))  # default, corporate, accessibility
    layout_configuration = Column(db.Text)  # JSON layout configuration

    # Data refresh
    auto_refresh_enabled = Column(db.Boolean, default=True)
    refresh_frequency_minutes = Column(db.Integer, default=60)
    last_refreshed = Column(db.DateTime, default=datetime.utcnow)

    # Access control
    view_permissions = Column(db.Text)  # JSON array of user roles with view permission
    edit_permissions = Column(db.Text)  # JSON array of user roles with edit permission

    # Timestamps
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CapabilityGapDashboard {self.dashboard_name}>"
