"""
AI Chat Document Upload Models

Tracks document uploads and analysis history for the AI chat interface.
"""

import json
import logging
from datetime import datetime  # dead-code-ok

from sqlalchemy import text

from .. import db
from .mixins.core import TenantMixin

logger = logging.getLogger(__name__)


class AIChatDocumentUpload(TenantMixin, db.Model):
    """
    Tracks document uploads in the AI chat interface.
    Stores metadata, analysis results, and status for each upload.
    """

    __tablename__ = "ai_chat_document_uploads"

    id = db.Column(db.Integer, primary_key=True)

    # Document information
    file_name = db.Column(db.String(255), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500))
    file_size = db.Column(db.BigInteger)  # Size in bytes
    file_type = db.Column(db.String(50))  # 'document', 'image', 'spreadsheet'
    mime_type = db.Column(db.String(100))

    # Upload status
    status = db.Column(
        db.String(30), default="uploading", index=True
    )  # 'uploading', 'analyzing', 'completed', 'failed'
    upload_progress = db.Column(db.Integer, default=0)  # 0 - 100

    # Analysis configuration
    provider = db.Column(db.String(50), default="claude")  # 'claude', 'openai', 'gemini'
    model_name = db.Column(db.String(100))

    # Analysis results (stored as JSON)
    analysis_results = db.Column(db.Text)  # Full analysis results JSON
    created_elements_count = db.Column(db.Integer, default=0)
    created_elements_details = db.Column(db.Text)  # JSON array of created elements
    errors = db.Column(db.Text)  # JSON array of errors

    # Metadata
    confidence = db.Column(db.String(20))  # 'high', 'medium', 'low'
    chat_context_summary = db.Column(db.Text)  # Summary for chat context

    # User tracking
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    uploaded_by = db.relationship("User", backref="ai_chat_document_uploads")

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
    analyzed_at = db.Column(db.DateTime)  # When analysis completed

    def get_analysis_results(self):
        """Parse analysis results JSON."""
        if self.analysis_results:
            try:
                return json.loads(self.analysis_results)
            except (ValueError, KeyError, TypeError):
                return {}
        return {}

    def get_created_elements_details(self):
        """Parse created elements details JSON."""
        if self.created_elements_details:
            try:
                return json.loads(self.created_elements_details)
            except (ValueError, KeyError, TypeError):
                return []
        return []

    def get_errors(self):
        """Parse errors JSON."""
        if self.errors:
            try:
                return json.loads(self.errors)
            except (ValueError, KeyError, TypeError):
                return []
        return []

    def format_file_size(self):
        """Format file size in human-readable format."""
        if not self.file_size:
            return "Unknown"
        for unit in ["B", "KB", "MB", "GB"]:
            if self.file_size < 1024.0:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024.0
        return f"{self.file_size:.1f} TB"

    def to_dict(self):
        """Serialize to dictionary for API responses."""
        return {
            "id": self.id,
            "file_name": self.file_name,
            "original_filename": self.original_filename,
            "file_size": self.file_size,
            "file_size_formatted": self.format_file_size(),
            "file_type": self.file_type,
            "status": self.status,
            "upload_progress": self.upload_progress,
            "provider": self.provider,
            "confidence": self.confidence,
            "created_elements_count": self.created_elements_count,
            "created_elements_details": self.get_created_elements_details(),
            "errors": self.get_errors(),
            "chat_context_summary": self.chat_context_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "uploaded_by": self.uploaded_by.full_name() if self.uploaded_by else None,
            "uploaded_by_email": self.uploaded_by.email if self.uploaded_by else None,
        }

    def __repr__(self):
        return f"<AIChatDocumentUpload {self.id}: {self.file_name} ({self.status})>"
