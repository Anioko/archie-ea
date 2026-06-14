"""
Capability Framework Models

Comprehensive capability modeling for capability-driven architecture.
Includes capability dependencies, maturity assessments, technology enablement,
and strategic alignment.

Key Models:
- CapabilityDependency: Capability relationships and dependencies
- CapabilityMaturityAssessment: Maturity level tracking and gap analysis
- TechnologyCapability: Technology enablement of capabilities
- CapabilityRoadmap: Strategic capability evolution planning
"""

from datetime import datetime  # dead-code-ok

from sqlalchemy import CheckConstraint, event  # dead-code-ok
from sqlalchemy.orm import validates

from app.datetime_helpers import utcnow

from .. import db
from .business_capabilities import BusinessCapability
from .mixins import TenantMixin


class CapabilityDependency(TenantMixin, db.Model):
    """
    Capability Dependency Model

    Tracks dependencies and relationships between business capabilities.
    Essential for sequencing implementation, understanding integration points,
    and performing impact analysis.
    """

    __tablename__ = "capability_dependency"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # Link entities
    source_capability_id = db.Column(
        db.Integer, db.ForeignKey("business_capability.id"), nullable=False, index=True
    )
    target_capability_id = db.Column(
        db.Integer, db.ForeignKey("business_capability.id"), nullable=False, index=True
    )

    # Dependency characteristics
    dependency_type = db.Column(
        db.String(50), nullable=False
    )  # requires, enables, supports, conflicts_with, composed_of, extends
    dependency_strength = db.Column(
        db.String(20), default="medium"
    )  # critical, strong, medium, weak
    is_bidirectional = db.Column(db.Boolean, default=False)

    # Dependency details
    description = db.Column(db.Text)
    rationale = db.Column(db.Text)  # Why this dependency exists
    impact_if_broken = db.Column(db.Text)  # Impact if dependency is broken

    # Sequencing & timing
    sequence_order = db.Column(db.Integer)  # For sequential dependencies
    lead_time_days = db.Column(db.Integer)  # Time buffer needed between capabilities
    is_parallel = db.Column(db.Boolean, default=True)  # Can be implemented in parallel?

    # Risk assessment
    risk_level = db.Column(db.String(20))  # low, medium, high, critical
    mitigation_strategy = db.Column(db.Text)
    contingency_plan = db.Column(db.Text)

    # Integration complexity
    integration_complexity = db.Column(db.String(20))  # low, medium, high, very_high
    integration_effort_days = db.Column(db.Integer)
    integration_cost_estimate = db.Column(db.Float)

    # Status & validation
    is_active = db.Column(db.Boolean, default=True)
    is_validated = db.Column(db.Boolean, default=False)
    validation_date = db.Column(db.DateTime)
    validated_by = db.Column(db.String(100))

    # Discovery metadata
    discovered_by_ai = db.Column(db.Boolean, default=False)
    discovery_confidence = db.Column(db.Float)  # 0 - 1 AI confidence score
    discovery_source = db.Column(db.String(100))  # manual, ai, analysis, imported

    # Timestamps
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    # Relationships with explicit primaryjoin to handle dual foreign keys to same table
    source_capability = db.relationship(
        "BusinessCapability",
        foreign_keys=[source_capability_id],
        primaryjoin="CapabilityDependency.source_capability_id == BusinessCapability.id",
        backref="capability_dependency_source",
    )
    target_capability = db.relationship(
        "BusinessCapability",
        foreign_keys=[target_capability_id],
        primaryjoin="CapabilityDependency.target_capability_id == BusinessCapability.id",
        backref="incoming_dependencies",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "source_capability_id": self.source_capability_id,
            "target_capability_id": self.target_capability_id,
            "dependency_type": self.dependency_type,
            "dependency_strength": self.dependency_strength,
            "is_bidirectional": self.is_bidirectional,
            "risk_level": self.risk_level,
            "integration_complexity": self.integration_complexity,
            "is_active": self.is_active,
            "discovered_by_ai": self.discovered_by_ai,
        }

    def __repr__(self):
        try:
            src = (
                self.source_capability.name
                if self.source_capability
                else f"Cap#{self.source_capability_id}"
            )
            tgt = (
                self.target_capability.name
                if self.target_capability
                else f"Cap#{self.target_capability_id}"
            )
            return f"<CapabilityDependency {src} --{self.dependency_type}--> {tgt}>"
        except Exception:
            return f"<CapabilityDependency Cap#{self.source_capability_id} --{self.dependency_type}--> Cap#{self.target_capability_id}>"


class CapabilityMaturityAssessment(TenantMixin, db.Model):
    """
    Capability Maturity Assessment Model

    Tracks capability maturity levels over time using various maturity models
    (CMMI, custom frameworks). Enables maturity gap analysis and improvement planning.
    """

    __tablename__ = "capability_maturity_assessment"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # Link to capability
    business_capability_id = db.Column(
        db.Integer, db.ForeignKey("business_capability.id"), nullable=False, index=True
    )

    # Assessment metadata
    assessment_date = db.Column(db.Date, nullable=False, index=True)
    assessment_period = db.Column(db.String(50))  # Q1 - 2024, Annual - 2024, etc.
    assessor_name = db.Column(db.String(100))
    assessor_role = db.Column(db.String(100))
    assessment_method = db.Column(db.String(50))  # survey, interview, data_analysis, observation

    # Maturity framework
    maturity_framework = db.Column(
        db.String(50), default="custom"
    )  # CMMI, custom, ISO, industry_specific
    maturity_level = db.Column(db.Integer, nullable=False)  # Current maturity level (1 - 5)
    maturity_level_name = db.Column(
        db.String(50)
    )  # Initial, Managed, Defined, Quantitatively Managed, Optimizing

    # Maturity dimensions (for comprehensive assessment)
    people_maturity = db.Column(db.Integer)  # 1 - 5
    process_maturity = db.Column(db.Integer)  # 1 - 5
    technology_maturity = db.Column(db.Integer)  # 1 - 5
    data_maturity = db.Column(db.Integer)  # 1 - 5
    governance_maturity = db.Column(db.Integer)  # 1 - 5

    # Target & gap
    target_maturity_level = db.Column(db.Integer)  # Target maturity level (1 - 5)
    target_achievement_date = db.Column(db.Date)
    maturity_gap = db.Column(db.Integer)  # Calculated: target - current
    gap_severity = db.Column(db.String(20))  # low, medium, high, critical

    # Assessment details
    strengths = db.Column(db.Text)  # JSON array of strengths
    weaknesses = db.Column(db.Text)  # JSON array of weaknesses
    improvement_opportunities = db.Column(db.Text)  # JSON array of opportunities
    key_findings = db.Column(db.Text)

    # Metrics & evidence
    evidence_collected = db.Column(db.Text)  # JSON array of evidence sources
    supporting_metrics = db.Column(db.Text)  # JSON object of metrics
    qualitative_data = db.Column(db.Text)
    quantitative_data = db.Column(db.Text)

    # Action planning
    improvement_actions = db.Column(db.Text)  # JSON array of improvement actions
    investment_required = db.Column(db.Float)  # Investment needed to close gap
    estimated_effort_days = db.Column(db.Integer)
    expected_benefits = db.Column(db.Text)

    # Status tracking
    status = db.Column(db.String(20), default="draft")  # draft, validated, approved, implemented
    confidence_score = db.Column(db.Integer)  # 0 - 100 confidence in assessment
    notes = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    business_capability = db.relationship("BusinessCapability", backref="maturity_assessments")

    @validates(
        "maturity_level",
        "target_maturity_level",
        "people_maturity",
        "process_maturity",
        "technology_maturity",
        "data_maturity",
        "governance_maturity",
    )
    def validate_maturity_scores(self, key, value):
        """Ensure maturity scores are between 1 and 5"""
        if value is not None:
            if value < 1 or value > 5:
                raise ValueError(f"{key} must be between 1 and 5")
        return value

    def calculate_maturity_gap(self):
        """Calculate maturity gap"""
        if self.target_maturity_level and self.maturity_level:
            self.maturity_gap = self.target_maturity_level - self.maturity_level
            return self.maturity_gap
        return None

    def calculate_gap_severity(self):
        """Calculate gap severity based on gap size and business criticality"""
        if not self.maturity_gap:
            return "none"

        if self.maturity_gap >= 3:
            return "critical"
        elif self.maturity_gap == 2:
            return "high"
        elif self.maturity_gap == 1:
            return "medium"
        else:
            return "low"

    def to_dict(self):
        return {
            "id": self.id,
            "business_capability_id": self.business_capability_id,
            "assessment_date": self.assessment_date.isoformat() if self.assessment_date else None,
            "maturity_level": self.maturity_level,
            "maturity_level_name": self.maturity_level_name,
            "target_maturity_level": self.target_maturity_level,
            "maturity_gap": self.maturity_gap,
            "gap_severity": self.gap_severity,
            "people_maturity": self.people_maturity,
            "process_maturity": self.process_maturity,
            "technology_maturity": self.technology_maturity,
            "status": self.status,
        }

    def __repr__(self):
        cap_name = (
            self.business_capability.name
            if self.business_capability
            else f"Cap#{self.business_capability_id}"
        )
        return f"<CapabilityMaturityAssessment {cap_name} Level {self.maturity_level}>"


class TechnologyCapabilityMapping(db.Model):
    """
    Technology Capability Mapping Model

    Maps technology components to business capabilities.
    Identifies which technologies enable which capabilities.
    NOTE: Renamed from TechnologyCapability to avoid conflict with unified_capability.TechnologyCapability
    """

    __tablename__ = "technology_capability"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # Link entities
    business_capability_id = db.Column(
        db.Integer, db.ForeignKey("business_capability.id"), nullable=False, index=True
    )
    technology_stack_id = db.Column(
        db.Integer, db.ForeignKey("technology_stacks.id"), nullable=True, index=True
    )

    # Technology details
    technology_name = db.Column(db.String(256), nullable=False, index=True)
    technology_type = db.Column(
        db.String(50)
    )  # platform, framework, tool, language, database, infrastructure
    technology_category = db.Column(db.String(100))  # cloud, on_premise, saas, hybrid

    # Enablement characteristics
    enablement_level = db.Column(
        db.String(20), default="partial"
    )  # full, substantial, partial, minimal
    is_critical_enabler = db.Column(db.Boolean, default=False)
    enablement_percentage = db.Column(db.Integer)  # 0 - 100% of capability enabled

    # Technology health
    technology_age_years = db.Column(db.Integer)
    technology_lifecycle_stage = db.Column(
        db.String(30)
    )  # emerging, growing, mature, declining, obsolete
    obsolescence_risk = db.Column(db.String(20))  # low, medium, high, critical
    vendor_support_status = db.Column(db.String(50))  # active, extended, deprecated, unsupported

    # Strategic alignment
    strategic_fit = db.Column(db.String(20))  # excellent, good, fair, poor
    future_proof_score = db.Column(db.Integer)  # 0 - 100
    innovation_potential = db.Column(db.String(20))  # high, medium, low

    # Technical metrics
    technical_debt_score = db.Column(db.Integer)  # 0 - 100
    integration_complexity = db.Column(db.String(20))  # low, medium, high
    scalability_score = db.Column(db.Integer)  # 1 - 10
    reliability_score = db.Column(db.Integer)  # 1 - 10
    performance_score = db.Column(db.Integer)  # 1 - 10

    # Financial metrics
    annual_license_cost = db.Column(db.Float)
    annual_maintenance_cost = db.Column(db.Float)
    infrastructure_cost = db.Column(db.Float)
    training_cost_per_user = db.Column(db.Float)
    total_cost_of_ownership = db.Column(db.Float)

    # Replacement planning
    replacement_consideration = db.Column(db.Boolean, default=False)
    replacement_priority = db.Column(db.String(20))  # immediate, high, medium, low, none
    replacement_options = db.Column(db.Text)  # JSON array of replacement options
    replacement_cost_estimate = db.Column(db.Float)
    replacement_timeline_months = db.Column(db.Integer)

    # Status & metadata
    is_active = db.Column(db.Boolean, default=True)
    deployment_status = db.Column(db.String(30))  # planned, pilot, production, deprecated, retired
    last_assessed = db.Column(db.DateTime)
    assessment_notes = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    business_capability = db.relationship("BusinessCapability", backref="technology_enablers")
    technology_stack = db.relationship("TechnologyStack", foreign_keys=[technology_stack_id])

    def to_dict(self):
        return {
            "id": self.id,
            "business_capability_id": self.business_capability_id,
            "technology_name": self.technology_name,
            "technology_type": self.technology_type,
            "enablement_level": self.enablement_level,
            "is_critical_enabler": self.is_critical_enabler,
            "obsolescence_risk": self.obsolescence_risk,
            "strategic_fit": self.strategic_fit,
            "replacement_consideration": self.replacement_consideration,
        }

    def __repr__(self):
        cap_name = (
            self.business_capability.name
            if self.business_capability
            else f"Cap#{self.business_capability_id}"
        )
        return f"<TechnologyCapability {self.technology_name} → {cap_name}>"


class CapabilityRoadmap(TenantMixin, db.Model):
    """
    Capability Roadmap Model

    Strategic planning for capability evolution over time.
    Tracks planned capability improvements, transformations, and investments.
    """

    __tablename__ = "capability_roadmap"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # Link to capability
    business_capability_id = db.Column(
        db.Integer, db.ForeignKey("business_capability.id"), nullable=False, index=True
    )

    # Roadmap details
    roadmap_name = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)
    roadmap_type = db.Column(
        db.String(50)
    )  # transformation, enhancement, modernization, retirement

    # Timeline
    start_date = db.Column(db.Date, nullable=False)
    target_completion_date = db.Column(db.Date, nullable=False)
    current_phase = db.Column(
        db.String(50)
    )  # planning, design, implementation, validation, complete
    phase_completion_percentage = db.Column(db.Integer, default=0)  # 0 - 100%

    # Strategic alignment
    strategic_initiative_id = db.Column(db.Integer, db.ForeignKey("enterprise_initiatives.id"))
    business_driver = db.Column(db.String(100))  # cost_reduction, growth, compliance, innovation
    expected_business_value = db.Column(db.Text)

    # Capability targets
    current_maturity_level = db.Column(db.Integer)  # 1 - 5
    target_maturity_level = db.Column(db.Integer)  # 1 - 5
    maturity_improvement_path = db.Column(db.Text)  # JSON array of milestones

    # Investment & resources
    total_investment_required = db.Column(db.Float)
    investment_allocated = db.Column(db.Float)
    investment_spent_to_date = db.Column(db.Float)
    resource_requirements = db.Column(db.Text)  # JSON array of resource needs

    # Benefits & ROI
    expected_annual_benefits = db.Column(db.Float)
    expected_roi_percentage = db.Column(db.Float)
    payback_period_months = db.Column(db.Integer)
    qualitative_benefits = db.Column(db.Text)  # JSON array

    # Risk & dependencies
    risk_level = db.Column(db.String(20))  # low, medium, high, critical
    key_risks = db.Column(db.Text)  # JSON array
    mitigation_strategies = db.Column(db.Text)  # JSON array
    dependencies = db.Column(db.Text)  # JSON array of dependency descriptions

    # Governance
    sponsor = db.Column(db.String(100))
    program_manager = db.Column(db.String(100))
    approval_status = db.Column(
        db.String(20), default="draft"
    )  # draft, proposed, approved, active, on_hold, cancelled, complete
    approval_date = db.Column(db.Date)

    # Status tracking
    status = db.Column(
        db.String(30), default="planning"
    )  # planning, approved, in_progress, on_hold, completed, cancelled
    health_status = db.Column(db.String(20))  # green, yellow, red
    progress_notes = db.Column(db.Text)
    last_status_update = db.Column(db.DateTime)

    # Timestamps
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    business_capability = db.relationship("BusinessCapability", backref="roadmap_items")
    strategic_initiative = db.relationship(
        "EnterpriseInitiative", foreign_keys=[strategic_initiative_id]
    )

    def to_dict(self):
        return {
            "id": self.id,
            "business_capability_id": self.business_capability_id,
            "roadmap_name": self.roadmap_name,
            "roadmap_type": self.roadmap_type,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "target_completion_date": self.target_completion_date.isoformat()
            if self.target_completion_date
            else None,
            "current_phase": self.current_phase,
            "phase_completion_percentage": self.phase_completion_percentage,
            "status": self.status,
            "health_status": self.health_status,
            "approval_status": self.approval_status,
        }

    def __repr__(self):
        return f"<CapabilityRoadmap {self.roadmap_name}>"


# Event listeners for automatic calculations
@event.listens_for(CapabilityMaturityAssessment, "before_insert")
@event.listens_for(CapabilityMaturityAssessment, "before_update")
def calculate_maturity_fields(mapper, connection, target):
    """Automatically calculate maturity gap and severity"""
    if target.target_maturity_level and target.maturity_level:
        target.maturity_gap = target.calculate_maturity_gap()
        target.gap_severity = target.calculate_gap_severity()
