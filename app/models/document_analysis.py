"""
Document Analysis Models

Stores analysis history and results for architecture document analysis.
"""

import json
from datetime import datetime  # dead-code-ok

from sqlalchemy import text

from .. import db


class DocumentAnalysis(db.Model):
    """
    Stores analysis results from document analysis operations.
    Enables history, replay, and comparison of analyses.
    """

    __tablename__ = "document_analyses"

    id = db.Column(db.Integer, primary_key=True)

    # Entity relationship (polymorphic)
    entity_type = db.Column(db.String(50), nullable=False, index=True)  # 'application' or 'vendor'
    entity_id = db.Column(db.Integer, nullable=False, index=True)

    # Document information
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500))
    file_size = db.Column(db.BigInteger)
    file_hash = db.Column(db.String(64), index=True)  # SHA - 256 hash for deduplication
    mime_type = db.Column(db.String(100))

    # Analysis configuration
    provider = db.Column(db.String(50))  # 'claude', 'openai', 'gemini'
    model_name = db.Column(db.String(100))

    # Analysis results (stored as JSON)
    analysis_results = db.Column(db.Text)  # Full analysis results JSON
    application_data = db.Column(
        db.Text
    )  # Extracted application data (if entity_type='application')
    vendor_data = db.Column(db.Text)  # Extracted vendor data (if entity_type='vendor')
    archimate_elements = db.Column(db.Text)  # Extracted ArchiMate elements JSON
    relationships = db.Column(db.Text)  # Extracted relationships JSON
    validation_results = db.Column(db.Text)  # Validation results JSON

    # Metadata
    confidence = db.Column(db.String(20))  # 'high', 'medium', 'low'
    elements_count = db.Column(db.Integer, default=0)
    relationships_count = db.Column(db.Integer, default=0)
    validation_errors_count = db.Column(db.Integer, default=0)

    # Status
    status = db.Column(db.String(30), default="completed")  # 'completed', 'failed', 'partial'
    applied = db.Column(db.Boolean, default=False, index=True)  # Whether analysis was applied
    applied_at = db.Column(db.DateTime)

    # User tracking
    analyzed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    analyzed_by = db.relationship("User", backref="document_analyses")

    # Timestamps  # tenant-exempt: model column defaults
    created_at = db.Column(
        db.DateTime,
        default=text("CURRENT_TIMESTAMP"),
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )
    updated_at = db.Column(
        db.DateTime,
        default=text("CURRENT_TIMESTAMP"),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )

    # LLM interaction tracking
    llm_interaction_id = db.Column(db.Integer, db.ForeignKey("llm_interactions.id"))
    llm_interaction = db.relationship("LLMInteraction", backref="document_analyses")

    def get_analysis_results(self):
        """Parse analysis results JSON."""
        if self.analysis_results:
            return json.loads(self.analysis_results)
        return {}

    def get_application_data(self):
        """Parse application data JSON."""
        if self.application_data:
            return json.loads(self.application_data)
        return {}

    def get_vendor_data(self):
        """Parse vendor data JSON."""
        if self.vendor_data:
            return json.loads(self.vendor_data)
        return {}

    def get_archimate_elements(self):
        """Parse ArchiMate elements JSON."""
        if self.archimate_elements:
            return json.loads(self.archimate_elements)
        return []

    def get_relationships(self):
        """Parse relationships JSON."""
        if self.relationships:
            return json.loads(self.relationships)
        return []

    def get_validation_results(self):
        """Parse validation results JSON."""
        if self.validation_results:
            return json.loads(self.validation_results)
        return {}

    def to_dict(self):
        """Serialize to dictionary for API responses."""
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "provider": self.provider,
            "model_name": self.model_name,
            "confidence": self.confidence,
            "elements_count": self.elements_count,
            "relationships_count": self.relationships_count,
            "validation_errors_count": self.validation_errors_count,
            "status": self.status,
            "applied": self.applied,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "analysis_results": self.get_analysis_results(),
        }

    def __repr__(self):
        return (
            f"<DocumentAnalysis {self.id}: {self.file_name} ({self.entity_type}:{self.entity_id})>"
        )


class DocumentAnalysisEdit(db.Model):
    """
    Tracks manual edits made to analysis results before applying.
    Enables audit trail and comparison.
    """

    __tablename__ = "document_analysis_edits"

    id = db.Column(db.Integer, primary_key=True)

    # Analysis relationship
    analysis_id = db.Column(
        db.Integer, db.ForeignKey("document_analyses.id"), nullable=False, index=True
    )
    analysis = db.relationship("DocumentAnalysis", backref="edits")

    # Edit details
    field_path = db.Column(
        db.String(255), nullable=False
    )  # e.g., 'application_data.name', 'archimate_elements[0].description'
    original_value = db.Column(db.Text)  # JSON
    edited_value = db.Column(db.Text)  # JSON
    edit_type = db.Column(db.String(50))  # 'modified', 'added', 'removed'

    # User tracking
    edited_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    edited_by = db.relationship("User", backref="document_analysis_edits")

    # Timestamp  # tenant-exempt: model column default
    created_at = db.Column(
        db.DateTime, default=text("CURRENT_TIMESTAMP"), server_default=text("CURRENT_TIMESTAMP")
    )

    def __repr__(self):
        return f"<DocumentAnalysisEdit {self.id}: {self.field_path}>"
