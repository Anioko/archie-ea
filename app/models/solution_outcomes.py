"""
Solution Outcomes Tracking Models

Enterprise-grade models for tracking solution benefits realization:
- Outcome tracking against predicted values
- Measurement history over time
- Aggregate benefits realization reporting

Integrates with:
- Solution model for solution linkage
- SolutionAnalysisSession for AI prediction tracking
- User model for audit trail
"""

import enum
from datetime import date, datetime  # dead-code-ok
from decimal import Decimal  # dead-code-ok

from sqlalchemy import (  # dead-code-ok
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app import db
from app.models.mixins import TenantMixin

# ============================================================================
# ENUMS
# ============================================================================


class OutcomeType(enum.Enum):
    """Types of outcomes that can be tracked"""

    COST = "cost"  # Cost savings or avoidance
    TIMELINE = "timeline"  # Time to market, delivery improvements
    QUALITY = "quality"  # Quality improvements, defect reduction
    CAPABILITY = "capability"  # New capabilities delivered
    RISK = "risk"  # Risk reduction, compliance
    BENEFIT = "benefit"  # General business benefits


class TrackingStatus(enum.Enum):
    """Status of outcome tracking"""

    NOT_STARTED = "not_started"  # Not yet measured
    IN_PROGRESS = "in_progress"  # Actively tracking
    ACHIEVED = "achieved"  # Target met
    MISSED = "missed"  # Target not met
    EXCEEDED = "exceeded"  # Target exceeded


class RealizationStatus(enum.Enum):
    """Overall benefits realization status"""

    ON_TRACK = "on_track"  # Benefits on track to be realized
    AT_RISK = "at_risk"  # Some benefits at risk
    OFF_TRACK = "off_track"  # Benefits not being realized
    EXCEEDED = "exceeded"  # Benefits exceeding expectations


# ============================================================================
# SOLUTION OUTCOME TRACKING
# ============================================================================


class SolutionOutcome(TenantMixin, db.Model):
    """
    Track actual outcomes vs predicted for solutions.

    Captures predicted values from AI recommendations and tracks
    actual realized values over time to measure benefits realization.
    """

    __tablename__ = "solution_outcomes"

    id = Column(Integer, primary_key=True)
    solution_id = Column(Integer, ForeignKey("solutions.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("solution_analysis_sessions.id"), nullable=True)

    # Outcome identification
    outcome_type = Column(Enum(OutcomeType), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Predicted values (from recommendation)
    predicted_value = Column(Numeric(15, 2))
    predicted_unit = Column(String(50))  # dollars, months, percentage, count
    predicted_date = Column(Date)
    prediction_confidence = Column(Float)  # 0 - 1

    # Actual values (tracked over time)
    actual_value = Column(Numeric(15, 2))
    actual_date = Column(Date)
    variance_percentage = Column(Float)  # Calculated: (actual - predicted) / predicted * 100
    variance_explanation = Column(Text)

    # Status tracking
    tracking_status = Column(
        Enum(TrackingStatus), default=TrackingStatus.NOT_STARTED, nullable=False
    )
    last_measured_at = Column(DateTime)
    next_measurement_date = Column(Date)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    solution = relationship(
        "Solution", backref=db.backref("outcomes", lazy="dynamic", cascade="all, delete-orphan")
    )
    session = relationship(
        "SolutionAnalysisSession", backref=db.backref("tracked_outcomes", lazy="dynamic")
    )
    created_by = relationship("User", foreign_keys=[created_by_id])
    measurements = relationship(
        "SolutionOutcomeMeasurement",
        back_populates="outcome",
        cascade="all, delete-orphan",
        order_by="SolutionOutcomeMeasurement.measured_at.desc()",
    )

    # Indexes
    __table_args__ = (
        Index("idx_outcome_solution", "solution_id"),
        Index("idx_outcome_session", "session_id"),
        Index("idx_outcome_type", "outcome_type"),
        Index("idx_outcome_status", "tracking_status"),
        Index("idx_outcome_next_measurement", "next_measurement_date"),
    )

    def calculate_variance(self):
        """Calculate variance percentage between predicted and actual values."""
        if self.predicted_value and self.actual_value and self.predicted_value != 0:
            self.variance_percentage = float(
                (self.actual_value - self.predicted_value) / self.predicted_value * 100
            )
        else:
            self.variance_percentage = None
        return self.variance_percentage

    def update_status_from_variance(self):
        """Update tracking status based on variance."""
        if self.variance_percentage is None:
            return

        # For cost/timeline outcomes, negative variance (less than predicted) is good
        # For quality/capability/benefit outcomes, positive variance is good
        is_lower_better = self.outcome_type in [
            OutcomeType.COST,
            OutcomeType.TIMELINE,
            OutcomeType.RISK,
        ]

        if is_lower_better:
            if self.variance_percentage < -10:
                self.tracking_status = TrackingStatus.EXCEEDED
            elif self.variance_percentage <= 0:
                self.tracking_status = TrackingStatus.ACHIEVED
            elif self.variance_percentage <= 10:
                self.tracking_status = TrackingStatus.IN_PROGRESS
            else:
                self.tracking_status = TrackingStatus.MISSED
        else:
            if self.variance_percentage > 10:
                self.tracking_status = TrackingStatus.EXCEEDED
            elif self.variance_percentage >= 0:
                self.tracking_status = TrackingStatus.ACHIEVED
            elif self.variance_percentage >= -10:
                self.tracking_status = TrackingStatus.IN_PROGRESS
            else:
                self.tracking_status = TrackingStatus.MISSED

    def to_dict(self, include_measurements: bool = False) -> dict:
        """Convert to dictionary representation."""
        result = {
            "id": self.id,
            "solution_id": self.solution_id,
            "session_id": self.session_id,
            "outcome_type": self.outcome_type.value if self.outcome_type else None,
            "name": self.name,
            "description": self.description,
            "predicted_value": float(self.predicted_value) if self.predicted_value else None,
            "predicted_unit": self.predicted_unit,
            "predicted_date": self.predicted_date.isoformat() if self.predicted_date else None,
            "prediction_confidence": self.prediction_confidence,
            "actual_value": float(self.actual_value) if self.actual_value else None,
            "actual_date": self.actual_date.isoformat() if self.actual_date else None,
            "variance_percentage": self.variance_percentage,
            "variance_explanation": self.variance_explanation,
            "tracking_status": self.tracking_status.value if self.tracking_status else None,
            "last_measured_at": self.last_measured_at.isoformat()
            if self.last_measured_at
            else None,
            "next_measurement_date": self.next_measurement_date.isoformat()
            if self.next_measurement_date
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by_id": self.created_by_id,
        }

        if include_measurements:
            result["measurements"] = [m.to_dict() for m in self.measurements]

        return result

    def __repr__(self):
        return f"<SolutionOutcome {self.id}: {self.name} ({self.tracking_status.value if self.tracking_status else 'unknown'})>"


# ============================================================================
# OUTCOME MEASUREMENTS
# ============================================================================


class SolutionOutcomeMeasurement(TenantMixin, db.Model):
    """
    Individual measurements over time for an outcome.

    Provides a time-series of measurements to track progress
    toward outcome targets.
    """

    __tablename__ = "solution_outcome_measurements"

    id = Column(Integer, primary_key=True)
    outcome_id = Column(Integer, ForeignKey("solution_outcomes.id"), nullable=False)

    # Measurement data
    measured_value = Column(Numeric(15, 2), nullable=False)
    measured_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    measured_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Context
    notes = Column(Text)
    evidence_links = Column(JSON)  # List of URLs/document references

    # Relationships
    outcome = relationship("SolutionOutcome", back_populates="measurements")
    measured_by = relationship("User", foreign_keys=[measured_by_id])

    # Indexes
    __table_args__ = (
        Index("idx_measurement_outcome", "outcome_id"),
        Index("idx_measurement_date", "measured_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "outcome_id": self.outcome_id,
            "measured_value": float(self.measured_value) if self.measured_value else None,
            "measured_at": self.measured_at.isoformat() if self.measured_at else None,
            "measured_by_id": self.measured_by_id,
            "notes": self.notes,
            "evidence_links": self.evidence_links,
        }

    def __repr__(self):
        return (
            f"<SolutionOutcomeMeasurement {self.id}: {self.measured_value} at {self.measured_at}>"
        )


# ============================================================================
# BENEFITS REALIZATION REPORTING
# ============================================================================
# The canonical SolutionBenefitRealization model lives in solution_sad_models
# to avoid duplicate mapper registration on the same table.
from app.models.solution_sad_models import SolutionBenefitRealization  # noqa: F401, E402
