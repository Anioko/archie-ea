"""
Capability-ArchiMate Classification Model

Links capabilities to ArchiMate element classifications for proper layer/type assignment.
Supports viewpoint generation and compliance validation.
"""

from datetime import datetime

from app import db

__all__ = ["CapabilityArchiMateClassification"]


class CapabilityArchiMateClassification(db.Model):
    """
    Maps capabilities to ArchiMate element classifications.

    Enables proper ArchiMate layer/type assignment per capability,
    supporting viewpoint generation and compliance validation.
    """

    __tablename__ = "capability_archimate_classifications"

    id = db.Column(db.Integer, primary_key=True)
    capability_id = db.Column(db.Integer, db.ForeignKey("business_capability.id"), nullable=False)

    # ArchiMate classification
    archimate_layer = db.Column(db.String(30), nullable=False)
    archimate_element_type = db.Column(db.String(100), nullable=False)
    archimate_element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Classification metadata
    classification_method = db.Column(db.String(30), default="manual")
    confidence_score = db.Column(db.Float, default=1.0)

    # Validation
    validated = db.Column(db.Boolean, default=False)
    validated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    validated_at = db.Column(db.DateTime)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    capability = db.relationship("BusinessCapability", backref="archimate_classifications")

    def __repr__(self):
        return f"<CapabilityArchiMateClassification {self.capability_id} -> {self.archimate_element_type}>"

    def to_dict(self):
        return {
            "id": self.id,
            "capability_id": self.capability_id,
            "archimate_layer": self.archimate_layer,
            "archimate_element_type": self.archimate_element_type,
            "archimate_element_id": self.archimate_element_id,
            "classification_method": self.classification_method,
            "confidence_score": self.confidence_score,
            "validated": self.validated,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
