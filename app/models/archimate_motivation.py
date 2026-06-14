"""
ArchiMate 3.2 Motivation Layer Models

This module implements the missing ArchiMate 3.2 Motivation layer elements:
- Stakeholder: Individual, team, or organization with interests in the architecture
- Assessment: Result of analysis of the state of affairs (driver analysis)
- Outcome: End result achieved through the use of capabilities
- Constraint: Factor limiting the realization of goals
- Value: Worth, usefulness, or importance of a core element
- Meaning: Knowledge/meaning associated with a representation

All models follow the standard pattern:
- id (Integer, primary_key)
- name (String 256, required)
- description (Text)
- archimate_id (String 50) - External ArchiMate identifier
- model_id (Integer, FK to architecture_models.id)
- layer = 'motivation' (constant)
- element_type (String 50) - Specific element type
- created_at, updated_at timestamps

Reference: ArchiMate 3.2 Specification, Chapter 6 - Motivation Elements
"""

from datetime import datetime

from sqlalchemy import event

from .. import db

# ============================================================================
# ArchiMate 3.2 Motivation Layer Models
# ============================================================================


class MotivationStakeholder(db.Model):
    """
    ArchiMate 3.2 Stakeholder element (Motivation Layer).

    Represents the role of an individual, team, or organization (or classes thereof)
    that represents their interests in, or concerns relative to, the outcome of
    the architecture.

    Examples:
    - "CFO" (financial stakeholder)
    - "Customer" (external stakeholder)
    - "IT Operations Team" (internal stakeholder)
    - "Regulatory Body" (external stakeholder)

    ArchiMate Relationships:
    - Stakeholder --(has interest in)--> Driver
    - Stakeholder --(has interest in)--> Goal
    - Stakeholder --(has interest in)--> Assessment
    """

    __tablename__ = "motivation_stakeholders"

    # Core fields (required by specification)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False, index=True)
    description = db.Column(db.Text)
    archimate_id = db.Column(db.String(50), index=True)  # External ArchiMate identifier
    model_id = db.Column(db.Integer, db.ForeignKey("architecture_models.id"), index=True)
    layer = db.Column(db.String(20), default="motivation")  # Always 'motivation'
    element_type = db.Column(db.String(50), default="Stakeholder")

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Additional Stakeholder-specific fields
    stakeholder_type = db.Column(
        db.String(50)
    )  # internal, external, executive, operational, regulatory
    influence_level = db.Column(db.String(20))  # high, medium, low

    # Extended attributes
    role = db.Column(db.String(100))  # CFO, Customer, IT Operations, Compliance Officer
    department = db.Column(db.String(100))
    organization = db.Column(db.String(200))
    power_level = db.Column(db.String(20))  # high, medium, low (for Power/Interest matrix)
    interest_level = db.Column(db.String(20))  # high, medium, low (for Power/Interest matrix)
    engagement_strategy = db.Column(
        db.String(50)
    )  # manage_closely, keep_satisfied, keep_informed, monitor
    communication_frequency = db.Column(
        db.String(30)
    )  # daily, weekly, monthly, quarterly, as_needed
    contact_name = db.Column(db.String(200))
    contact_email = db.Column(db.String(255))

    # Relationships
    architecture_model = db.relationship("ArchitectureModel", backref="motivation_stakeholders")

    def __repr__(self):
        return f"<MotivationStakeholder {self.name} ({self.stakeholder_type})>"


class MotivationAssessment(db.Model):
    """
    ArchiMate 3.2 Assessment element (Motivation Layer).

    Represents the result of an analysis of the state of affairs of the enterprise
    with respect to some driver.

    Examples:
    - "Customer Satisfaction Survey 2023" - assessment of customer sentiment
    - "Architecture Maturity Assessment" - assessment of architecture capabilities
    - "Security Risk Assessment" - assessment of security posture
    - "Gap Analysis Report" - assessment of current vs. target state

    ArchiMate Relationships:
    - Assessment --(associated with)--> Driver
    - Assessment --(associated with)--> Goal
    - Stakeholder --(has interest in)--> Assessment
    """

    __tablename__ = "motivation_assessments"

    # Core fields (required by specification)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False, index=True)
    description = db.Column(db.Text)
    archimate_id = db.Column(db.String(50), index=True)  # External ArchiMate identifier
    model_id = db.Column(db.Integer, db.ForeignKey("architecture_models.id"), index=True)
    layer = db.Column(db.String(20), default="motivation")  # Always 'motivation'
    element_type = db.Column(db.String(50), default="Assessment")

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Additional Assessment-specific fields
    assessment_date = db.Column(db.Date)
    impact_level = db.Column(db.String(20))  # high, medium, low, critical

    # Extended attributes
    assessment_type = db.Column(db.String(50))  # SWOT, Maturity, Risk, Performance, Gap
    result_score = db.Column(db.String(50))  # Numeric or categorical result
    assessor = db.Column(db.String(100))  # Who performed the assessment
    methodology = db.Column(db.String(100))  # Assessment methodology used
    findings = db.Column(db.Text)  # Key findings from the assessment
    recommendations = db.Column(db.Text)  # Recommendations based on findings
    next_assessment_date = db.Column(db.Date)

    # Relationships
    architecture_model = db.relationship("ArchitectureModel", backref="motivation_assessments")

    def __repr__(self):
        return f"<MotivationAssessment {self.name} ({self.assessment_type})>"


class MotivationOutcome(db.Model):
    """
    ArchiMate 3.2 Outcome element (Motivation Layer).

    Represents an end result that has been achieved. An outcome is the end result,
    the desired state or situation that the enterprise and its stakeholders want
    to achieve.

    Examples:
    - "Reduced Time-to-Market" - outcome of process improvement
    - "Improved Customer Satisfaction" - outcome of service enhancement
    - "20% Cost Reduction" - outcome of rationalization initiative
    - "Regulatory Compliance Achieved" - outcome of compliance program

    ArchiMate Relationships:
    - Outcome --(realizes)--> Goal
    - Value --(associated with)--> Outcome
    - Capability --(realizes)--> Outcome
    """

    __tablename__ = "motivation_outcomes"

    # Core fields (required by specification)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False, index=True)
    description = db.Column(db.Text)
    archimate_id = db.Column(db.String(50), index=True)  # External ArchiMate identifier
    model_id = db.Column(db.Integer, db.ForeignKey("architecture_models.id"), index=True)
    layer = db.Column(db.String(20), default="motivation")  # Always 'motivation'
    element_type = db.Column(db.String(50), default="Outcome")

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Additional Outcome-specific fields
    achievement_level = db.Column(db.String(20))  # not_started, partial, achieved, exceeded
    measurement_criteria = db.Column(db.Text)  # How achievement is measured

    # Extended attributes
    target_value = db.Column(db.String(100))  # "20% reduction", "NPS > 50"
    current_value = db.Column(db.String(100))  # Current measured value
    baseline_value = db.Column(db.String(100))  # Starting point
    measurement_unit = db.Column(db.String(50))  # percentage, EUR, count
    measurement_frequency = db.Column(db.String(30))  # daily, weekly, monthly, quarterly
    target_date = db.Column(db.Date)  # When should outcome be achieved
    achieved_date = db.Column(db.Date)  # When was outcome actually achieved
    realization_status = db.Column(
        db.String(30), default="not_started"
    )  # not_started, in_progress, at_risk, achieved, failed

    # Goal linkage
    goal_id = db.Column(db.Integer, db.ForeignKey("goals.id"), nullable=True, index=True)

    # Relationships
    architecture_model = db.relationship("ArchitectureModel", backref="motivation_outcomes")
    goal = db.relationship("Goal", backref="motivation_outcomes", foreign_keys=[goal_id])

    @property
    def achievement_percentage(self):
        """Calculate achievement percentage if values are numeric."""
        try:
            if self.current_value and self.target_value and self.baseline_value:
                current = float(self.current_value.replace("%", "").replace(",", ""))
                target = float(self.target_value.replace("%", "").replace(",", ""))
                baseline = float(self.baseline_value.replace("%", "").replace(",", ""))
                if target != baseline:
                    return min(100, max(0, ((current - baseline) / (target - baseline)) * 100))
        except (ValueError, ZeroDivisionError):
            pass
        return None

    def __repr__(self):
        return f"<MotivationOutcome {self.name} ({self.achievement_level})>"


class MotivationConstraint(db.Model):
    """
    ArchiMate 3.2 Constraint element (Motivation Layer).

    Represents a factor that prevents or obstructs the realization of goals.
    A constraint is a limitation on the design and implementation of an
    architecture, its realization, or a goal.

    Examples:
    - "Budget Limit: EUR 5M" - financial constraint
    - "Go-Live by Q2 2026" - timeline constraint
    - "Must use OpenShift" - technical constraint
    - "GDPR Compliance Required" - regulatory constraint
    - "Max 10 FTEs Available" - resource constraint

    ArchiMate Relationships:
    - Constraint --(influences)--> Goal
    - Principle --(realizes)--> Constraint
    - Requirement --(realizes)--> Constraint
    """

    __tablename__ = "motivation_constraints"

    # Core fields (required by specification)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False, index=True)
    description = db.Column(db.Text)
    archimate_id = db.Column(db.String(50), index=True)  # External ArchiMate identifier
    model_id = db.Column(db.Integer, db.ForeignKey("architecture_models.id"), index=True)
    layer = db.Column(db.String(20), default="motivation")  # Always 'motivation'
    element_type = db.Column(db.String(50), default="Constraint")

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Additional Constraint-specific fields
    constraint_type = db.Column(
        db.String(50)
    )  # budget, timeline, regulatory, technical, resource, platform, vendor, organizational
    severity = db.Column(db.String(20))  # critical, high, medium, low

    # Extended attributes
    is_hard_constraint = db.Column(
        db.Boolean, default=True
    )  # True = cannot violate, False = negotiable
    constraint_value = db.Column(db.String(200))  # "EUR 5M max", "12 months", "EU only"
    constraint_unit = db.Column(db.String(50))  # EUR, months, region, FTEs
    violation_consequence = db.Column(db.Text)  # What happens if violated
    effective_from = db.Column(db.Date)  # When constraint starts
    effective_until = db.Column(db.Date)  # When constraint expires (if applicable)
    status = db.Column(db.String(30), default="active")  # active, expired, waived, superseded
    waiver_reason = db.Column(db.Text)  # If status=waived, why was it waived
    waived_by = db.Column(db.String(100))  # Who approved the waiver

    # Goal linkage
    goal_id = db.Column(db.Integer, db.ForeignKey("goals.id"), nullable=True, index=True)

    # Relationships
    architecture_model = db.relationship("ArchitectureModel", backref="motivation_constraints")
    goal = db.relationship("Goal", backref="motivation_constraints", foreign_keys=[goal_id])

    def __repr__(self):
        return f"<MotivationConstraint {self.name} [{self.constraint_type}]>"


class MotivationValue(db.Model):
    """
    ArchiMate 3.2 Value element (Motivation Layer).

    Represents the relative worth, utility, or importance of a core element
    or an outcome. Value may apply to what a party gets in return for money
    paid or the relative worth of something exchanged.

    Examples:
    - "Cost Reduction" - financial value
    - "Improved Customer Experience" - customer value
    - "Risk Mitigation" - operational value
    - "Market Leadership" - strategic value
    - "Regulatory Compliance" - compliance value

    ArchiMate Relationships:
    - Value --(associated with)--> Outcome
    - Value --(associated with)--> Business Service
    - Stakeholder --(has interest in)--> Value
    """

    __tablename__ = "motivation_values"

    # Core fields (required by specification)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False, index=True)
    description = db.Column(db.Text)
    archimate_id = db.Column(db.String(50), index=True)  # External ArchiMate identifier
    model_id = db.Column(db.Integer, db.ForeignKey("architecture_models.id"), index=True)
    layer = db.Column(db.String(20), default="motivation")  # Always 'motivation'
    element_type = db.Column(db.String(50), default="Value")

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Additional Value-specific fields
    value_type = db.Column(
        db.String(50)
    )  # financial, operational, strategic, social, customer, compliance
    priority = db.Column(db.Integer)  # 1 - 10 priority ranking

    # Extended attributes
    amount = db.Column(db.Numeric(15, 2))  # Optional quantified value
    currency = db.Column(db.String(10))  # EUR, USD, GBP
    quantification_method = db.Column(db.String(100))  # How value was quantified
    realization_timeframe = db.Column(
        db.String(50)
    )  # immediate, short_term, medium_term, long_term
    confidence_level = db.Column(db.String(20))  # high, medium, low

    # Relationships
    architecture_model = db.relationship("ArchitectureModel", backref="motivation_values")

    def __repr__(self):
        return f"<MotivationValue {self.name} ({self.value_type})>"


class MotivationMeaning(db.Model):
    """
    ArchiMate 3.2 Meaning element (Motivation Layer).

    Represents the knowledge or expertise present in, or the interpretation
    given to, a core element in a particular context.

    Examples:
    - "Legal Interpretation of GDPR" - legal meaning
    - "Customer Satisfaction" - business meaning
    - "Technical Debt" - technical meaning
    - "Risk Appetite" - governance meaning

    ArchiMate Relationships:
    - Meaning --(associated with)--> Representation
    - Meaning --(associated with)--> Business Object
    - Stakeholder --(has interest in)--> Meaning
    """

    __tablename__ = "motivation_meanings"

    # Core fields (required by specification)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False, index=True)
    description = db.Column(db.Text)
    archimate_id = db.Column(db.String(50), index=True)  # External ArchiMate identifier
    model_id = db.Column(db.Integer, db.ForeignKey("architecture_models.id"), index=True)
    layer = db.Column(db.String(20), default="motivation")  # Always 'motivation'
    element_type = db.Column(db.String(50), default="Meaning")

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Additional Meaning-specific fields
    semantic_type = db.Column(db.String(50))  # legal, business, technical, governance, operational

    # Extended attributes
    context = db.Column(db.Text)  # Context in which this meaning applies
    source_reference = db.Column(
        db.String(500)
    )  # Reference to source of meaning (standard, regulation, etc.)
    interpretation_date = db.Column(db.Date)  # When was this interpretation established
    interpreted_by = db.Column(db.String(100))  # Who provided the interpretation
    validity_scope = db.Column(db.String(100))  # enterprise, business_unit, department, project

    # Relationships
    architecture_model = db.relationship("ArchitectureModel", backref="motivation_meanings")

    def __repr__(self):
        return f"<MotivationMeaning {self.name} ({self.semantic_type})>"


# ============================================================================
# Event Listeners - Auto-create ArchiMateElement entries
# ============================================================================


@event.listens_for(MotivationStakeholder, "before_insert")
def create_stakeholder_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement for MotivationStakeholder"""
    if not target.archimate_id:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="Stakeholder",
                layer="Motivation",
                description=target.description or f"Stakeholder: {target.name}",
                architecture_id=target.model_id,
            )
        )
        target.archimate_id = f"archimate-{result.inserted_primary_key[0]}"


@event.listens_for(MotivationAssessment, "before_insert")
def create_assessment_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement for MotivationAssessment"""
    if not target.archimate_id:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="Assessment",
                layer="Motivation",
                description=target.description or f"Assessment: {target.name}",
                architecture_id=target.model_id,
            )
        )
        target.archimate_id = f"archimate-{result.inserted_primary_key[0]}"


@event.listens_for(MotivationOutcome, "before_insert")
def create_outcome_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement for MotivationOutcome"""
    if not target.archimate_id:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="Outcome",
                layer="Motivation",
                description=target.description or f"Outcome: {target.name}",
                architecture_id=target.model_id,
            )
        )
        target.archimate_id = f"archimate-{result.inserted_primary_key[0]}"


@event.listens_for(MotivationConstraint, "before_insert")
def create_constraint_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement for MotivationConstraint"""
    if not target.archimate_id:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="Constraint",
                layer="Motivation",
                description=target.description or f"Constraint: {target.name}",
                architecture_id=target.model_id,
            )
        )
        target.archimate_id = f"archimate-{result.inserted_primary_key[0]}"


@event.listens_for(MotivationValue, "before_insert")
def create_value_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement for MotivationValue"""
    if not target.archimate_id:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="Value",
                layer="Motivation",
                description=target.description or f"Value: {target.name}",
                architecture_id=target.model_id,
            )
        )
        target.archimate_id = f"archimate-{result.inserted_primary_key[0]}"


@event.listens_for(MotivationMeaning, "before_insert")
def create_meaning_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement for MotivationMeaning"""
    if not target.archimate_id:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="Meaning",
                layer="Motivation",
                description=target.description or f"Meaning: {target.name}",
                architecture_id=target.model_id,
            )
        )
        target.archimate_id = f"archimate-{result.inserted_primary_key[0]}"
