"""
Application Import History Model

Tracks application import operations for audit and history purposes.
"""

import json
from datetime import datetime

from .. import db
from .mixins.core import TenantMixin


class ApplicationImportHistory(TenantMixin, db.Model):
    """
    Tracks application import operations.

    Records:
    - Who imported what and when
    - Import source (Excel, Manual, CSV, JSON)
    - Success/failure statistics
    - Error details
    """

    __tablename__ = "application_import_history"

    id = db.Column(db.Integer, primary_key=True)

    # Import metadata
    imported_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    imported_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    imported_by_name = db.Column(db.String(256))  # Store name in case user is deleted

    # Import source
    import_source = db.Column(db.String(50), nullable=False)  # 'excel', 'manual', 'csv', 'json'
    file_name = db.Column(db.String(500))  # For file-based imports
    file_size = db.Column(db.Integer)  # File size in bytes

    # Import statistics
    total_records = db.Column(db.Integer, default=0)
    records_created = db.Column(db.Integer, default=0)
    records_updated = db.Column(db.Integer, default=0)
    records_skipped = db.Column(db.Integer, default=0)
    records_failed = db.Column(db.Integer, default=0)

    # Import settings
    duplicate_mode = db.Column(db.String(50))  # 'merge', 'skip', 'duplicate'
    import_settings = db.Column(db.Text)  # JSON: additional settings

    # Status
    status = db.Column(
        db.String(50), default="completed"
    )  # 'pending', 'completed', 'failed', 'partial'
    error_summary = db.Column(db.Text)  # Summary of errors
    error_details = db.Column(db.Text)  # JSON: detailed error list

    # Relationships
    imported_by = db.relationship("User", foreign_keys=[imported_by_id])

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "imported_at": self.imported_at.isoformat() if self.imported_at else None,
            "imported_by_id": self.imported_by_id,
            "imported_by_name": self.imported_by_name,
            "import_source": self.import_source,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "total_records": self.total_records,
            "records_created": self.records_created,
            "records_updated": self.records_updated,
            "records_skipped": self.records_skipped,
            "records_failed": self.records_failed,
            "duplicate_mode": self.duplicate_mode,
            "status": self.status,
            "error_summary": self.error_summary,
            "error_details": json.loads(self.error_details) if self.error_details else [],
        }

    def __repr__(self):
        return (
            f"<ApplicationImportHistory {self.id} by {self.imported_by_name} at {self.imported_at}>"
        )
