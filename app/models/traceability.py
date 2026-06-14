"""
Traceability Model - End-to-end architecture traceability

Supports Strategy -> Business -> Application -> Technology traceability.
Enables impact analysis and viewpoint generation.
"""

from datetime import datetime

from app import db


class TraceabilityLink(db.Model):
    """
    End-to-end traceability link between architecture elements.

    Supports Strategy -> Business -> Application -> Technology traceability.
    Enables impact analysis and viewpoint generation.
    """

    __tablename__ = "traceability_links"

    id = db.Column(db.Integer, primary_key=True)

    # Source element
    source_element_type = db.Column(db.String(100), nullable=False)
    source_element_id = db.Column(db.Integer, nullable=False)
    source_archimate_element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Target element
    target_element_type = db.Column(db.String(100), nullable=False)
    target_element_id = db.Column(db.Integer, nullable=False)
    target_archimate_element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Solution scoping (for journey-derived links)
    solution_id = db.Column(
        db.Integer,
        db.ForeignKey("solutions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Traceability classification
    traceability_type = db.Column(db.String(50))  # realization, dependency, derivation
    traceability_layer = db.Column(db.String(50))  # strategy_to_business, etc.

    # Confidence and validation
    confidence_score = db.Column(db.Float, default=1.0)
    validated = db.Column(db.Boolean, default=False)
    validation_method = db.Column(db.String(30))

    # Impact weight
    impact_weight = db.Column(db.Float, default=1.0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    def __repr__(self):
        return f"<TraceabilityLink {self.source_element_type}:{self.source_element_id} -> {self.target_element_type}:{self.target_element_id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "source_element_type": self.source_element_type,
            "source_element_id": self.source_element_id,
            "target_element_type": self.target_element_type,
            "target_element_id": self.target_element_id,
            "traceability_type": self.traceability_type,
            "traceability_layer": self.traceability_layer,
            "confidence_score": self.confidence_score,
            "validated": self.validated,
            "impact_weight": self.impact_weight,
        }


class ImpactAnalysisResult(db.Model):
    """
    Stores impact analysis results for auditing and reporting.
    """

    __tablename__ = "impact_analysis_results"

    id = db.Column(db.Integer, primary_key=True)

    # Analysis context
    analysis_type = db.Column(db.String(50))  # change_impact, retirement_impact
    trigger_element_type = db.Column(db.String(100))
    trigger_element_id = db.Column(db.Integer)
    scenario = db.Column(db.String(50), nullable=True)  # API scenario: modification, retirement, upgrade, etc.

    # Impact scope (JSON)
    impacted_elements = db.Column(db.Text)  # JSON array
    impact_summary = db.Column(db.Text)  # JSON summary

    # Severity
    overall_severity = db.Column(db.String(20))  # critical, high, medium, low
    affected_capabilities_count = db.Column(db.Integer, default=0)
    affected_applications_count = db.Column(db.Integer, default=0)
    affected_processes_count = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    def __repr__(self):
        return f"<ImpactAnalysisResult {self.analysis_type} - {self.overall_severity}>"

    def to_dict(self):
        return {
            "id": self.id,
            "analysis_type": self.analysis_type,
            "trigger_element_type": self.trigger_element_type,
            "trigger_element_id": self.trigger_element_id,
            "scenario": self.scenario,
            "overall_severity": self.overall_severity,
            "affected_capabilities_count": self.affected_capabilities_count,
            "affected_applications_count": self.affected_applications_count,
            "affected_processes_count": self.affected_processes_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
