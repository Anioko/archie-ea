"""Configurable scoring engine model.

Generic scoring configuration that replaces hardcoded values across the platform:
- ArchiMate pattern confidence (hardcoded 0.7-0.75)
- Vendor pricing tiers (hardcoded brackets)
- Vendor quality scores (returns 0 always)
- Risk templates (hardcoded by domain)

Each row represents a (category, metric) pair with weight, threshold, and bounds.
"""

from datetime import datetime

from app import db


class ScoringConfig(db.Model):
    """Platform-wide configurable scoring parameters.

    Categories group related metrics (e.g. 'archimate_confidence',
    'vendor_pricing', 'risk_scoring').  Each metric within a category
    has a weight, optional threshold, and optional min/max bounds.
    """

    __tablename__ = "scoring_configs"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)
    metric = db.Column(db.String(100), nullable=False)
    weight = db.Column(db.Float, default=1.0)
    threshold = db.Column(db.Float, nullable=True)
    min_value = db.Column(db.Float, nullable=True)
    max_value = db.Column(db.Float, nullable=True)
    formula = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint(
            "category", "metric", name="uq_scoring_config_category_metric"
        ),
        {"extend_existing": True},
    )

    def __repr__(self):
        return f"<ScoringConfig {self.category}/{self.metric} w={self.weight}>"

    def to_dict(self):
        """Serialize to dictionary for API responses."""
        return {
            "id": self.id,
            "category": self.category,
            "metric": self.metric,
            "weight": self.weight,
            "threshold": self.threshold,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "formula": self.formula,
            "is_active": self.is_active,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
