"""
Import Session Models - Transactional Staging with Checkpointing

Provides robust import recovery by persisting intermediate results during
LLM-powered ArchiMate generation. Prevents data loss from API failures,
credit exhaustion, server restarts, or interruptions.

Architecture:
- ImportSession: Tracks overall import state and progress
- StagingElement: Stores generated elements before final commit
- Checkpoint markers for granular recovery
- Atomic transactions for data integrity
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Index, Text
from sqlalchemy.dialects.postgresql import JSONB

from app import db


class ImportStatus(str, Enum):
    """Import session status states."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECOVERING = "recovering"


class CheckpointType(str, Enum):
    """Checkpoint types for granular recovery."""

    FILE_UPLOADED = "file_uploaded"
    FILE_PARSED = "file_parsed"
    APPLICATIONS_CREATED = "applications_created"
    CAPABILITIES_MATCHED = "capabilities_matched"
    ARCHIMATE_GENERATED = "archimate_generated"
    RELATIONSHIPS_CREATED = "relationships_created"
    APQC_MAPPED = "apqc_mapped"
    VENDOR_MATCHED = "vendor_matched"
    FINAL_COMMIT = "final_commit"


class StagingElementType(str, Enum):
    """Types of elements stored in staging."""

    APPLICATION = "application"
    CAPABILITY = "capability"
    ARCHIMATE_ELEMENT = "archimate_element"
    ARCHIMATE_RELATIONSHIP = "archimate_relationship"
    APQC_MAPPING = "apqc_mapping"
    VENDOR_MAPPING = "vendor_mapping"


class ImportSession(db.Model):
    """
    Tracks import session state and progress for recovery.

    Stores metadata about the import process, including:
    - User and file information
    - Progress tracking with checkpoints
    - Error information for debugging
    - Cost tracking for LLM usage
    - Recovery state for resumption
    """

    __tablename__ = "import_sessions"

    id = db.Column(db.Integer, primary_key=True)

    # Session identification
    session_uuid = db.Column(db.String(36), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # File information
    filename = db.Column(db.String(255), nullable=False)
    file_size_bytes = db.Column(db.Integer)
    file_hash = db.Column(db.String(64))  # SHA256 for deduplication

    # Import configuration
    import_type = db.Column(
        db.String(50), default="application_import"
    )  # application_import, archimate_import, etc.
    enable_ai_import = db.Column(db.Boolean, default=True)
    confidence_threshold = db.Column(db.Float, default=0.7)
    archimate_mode = db.Column(db.String(20), default="standard")  # quick, standard, comprehensive
    custom_mappings = db.Column(JSON)  # Field mappings from user

    # Status tracking
    status = db.Column(db.String(20), default=ImportStatus.PENDING, nullable=False, index=True)
    current_checkpoint = db.Column(db.String(50))  # Last successful checkpoint
    checkpoint_data = db.Column(JSON)  # Checkpoint-specific metadata

    # Progress tracking
    total_rows = db.Column(db.Integer, default=0)
    processed_rows = db.Column(db.Integer, default=0)
    successful_rows = db.Column(db.Integer, default=0)
    failed_rows = db.Column(db.Integer, default=0)
    skipped_rows = db.Column(db.Integer, default=0)
    progress_percentage = db.Column(db.Float, default=0.0)

    # LLM usage tracking
    llm_calls_made = db.Column(db.Integer, default=0)
    llm_tokens_used = db.Column(db.Integer, default=0)
    estimated_cost_usd = db.Column(db.Float, default=0.0)
    llm_providers_used = db.Column(JSON)  # List of providers used

    # Error tracking
    error_message = db.Column(Text)
    error_details = db.Column(JSON)  # Detailed error information
    retry_count = db.Column(db.Integer, default=0)
    last_error_at = db.Column(db.DateTime)

    # Timing information
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    estimated_completion_at = db.Column(db.DateTime)
    processing_time_seconds = db.Column(db.Integer)

    # Recovery information
    can_resume = db.Column(db.Boolean, default=True)
    resume_from_checkpoint = db.Column(db.String(50))
    recovery_attempts = db.Column(db.Integer, default=0)

    # Results summary
    results_summary = db.Column(JSON)  # Summary of what was created

    # Relationships
    user = db.relationship("User", backref="import_sessions")
    staging_elements = db.relationship(
        "StagingElement",
        back_populates="import_session",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    checkpoints = db.relationship(
        "ImportCheckpoint",
        back_populates="import_session",
        cascade="all, delete-orphan",
        order_by="ImportCheckpoint.created_at",
        lazy="dynamic",
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_import_session_user_status", "user_id", "status"),
        Index("idx_import_session_created", "created_at"),
        Index("idx_import_session_status_activity", "status", "last_activity_at"),
    )

    def __repr__(self):
        return f"<ImportSession {self.session_uuid} - {self.status}>"

    def update_progress(
        self, processed: int = None, successful: int = None, failed: int = None, skipped: int = None
    ):
        """Update progress counters and calculate percentage."""
        if processed is not None:
            self.processed_rows = processed
        if successful is not None:
            self.successful_rows = successful
        if failed is not None:
            self.failed_rows = failed
        if skipped is not None:
            self.skipped_rows = skipped

        if self.total_rows > 0:
            self.progress_percentage = (self.processed_rows / self.total_rows) * 100

        self.last_activity_at = datetime.utcnow()

    def add_checkpoint(self, checkpoint_type: CheckpointType, data: dict = None):
        """Add a checkpoint marker for recovery."""
        self.current_checkpoint = checkpoint_type.value
        if data:
            self.checkpoint_data = data
        self.last_activity_at = datetime.utcnow()

    def record_error(self, error_message: str, error_details: dict = None):
        """Record error information for debugging."""
        self.error_message = error_message
        self.error_details = error_details
        self.last_error_at = datetime.utcnow()
        self.retry_count += 1

    @property
    def error_messages(self):
        """Get error messages as a list for compatibility."""
        if self.error_message:
            return [self.error_message]
        return []

    def track_llm_usage(self, provider: str, tokens: int, estimated_cost: float):
        """Track LLM API usage and costs."""
        self.llm_calls_made += 1
        self.llm_tokens_used += tokens
        self.estimated_cost_usd += estimated_cost

        if not self.llm_providers_used:
            self.llm_providers_used = []
        if provider not in self.llm_providers_used:
            self.llm_providers_used.append(provider)

    def to_dict(self):
        """Convert session to dictionary for API responses."""
        return {
            "id": self.id,
            "session_uuid": self.session_uuid,
            "user_id": self.user_id,
            "filename": self.filename,
            "status": self.status,
            "current_checkpoint": self.current_checkpoint,
            "progress": {
                "total_rows": self.total_rows,
                "processed_rows": self.processed_rows,
                "successful_rows": self.successful_rows,
                "failed_rows": self.failed_rows,
                "skipped_rows": self.skipped_rows,
                "percentage": self.progress_percentage,
            },
            "llm_usage": {
                "calls_made": self.llm_calls_made,
                "tokens_used": self.llm_tokens_used,
                "estimated_cost_usd": self.estimated_cost_usd,
                "providers_used": self.llm_providers_used,
            },
            "timing": {
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
                "last_activity_at": self.last_activity_at.isoformat()
                if self.last_activity_at
                else None,
                "processing_time_seconds": self.processing_time_seconds,
            },
            "recovery": {
                "can_resume": self.can_resume,
                "resume_from_checkpoint": self.resume_from_checkpoint,
                "recovery_attempts": self.recovery_attempts,
            },
            "error": {
                "message": self.error_message,
                "details": self.error_details,
                "retry_count": self.retry_count,
                "last_error_at": self.last_error_at.isoformat() if self.last_error_at else None,
            }
            if self.error_message
            else None,
            "results_summary": self.results_summary,
        }


class StagingElement(db.Model):
    """
    Stores generated elements before final commit.

    Acts as a staging area for all elements generated during import:
    - Applications
    - Capabilities
    - ArchiMate elements
    - Relationships
    - APQC mappings

    Elements remain in staging until the entire import succeeds,
    enabling atomic commits and recovery from failures.
    """

    __tablename__ = "staging_elements"

    id = db.Column(db.Integer, primary_key=True)

    # Session relationship
    import_session_id = db.Column(
        db.Integer,
        db.ForeignKey("import_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Element identification
    element_type = db.Column(db.String(50), nullable=False, index=True)
    element_uuid = db.Column(db.String(36), unique=True, nullable=False, index=True)

    # Element data
    element_data = db.Column(JSON, nullable=False)  # Full element data
    element_metadata = db.Column(JSON)  # Additional metadata

    # Source tracking
    source_row_number = db.Column(db.Integer)  # Row in original file
    source_data = db.Column(JSON)  # Original CSV/Excel row data

    # Processing information
    generated_by_llm = db.Column(db.Boolean, default=False)
    llm_provider = db.Column(db.String(50))
    llm_model = db.Column(db.String(100))
    confidence_score = db.Column(db.Float)
    requires_review = db.Column(db.Boolean, default=False)

    # Relationship tracking
    parent_element_uuid = db.Column(db.String(36), index=True)  # For hierarchical elements
    related_element_uuids = db.Column(JSON)  # List of related element UUIDs

    # Status
    is_committed = db.Column(db.Boolean, default=False, index=True)
    committed_at = db.Column(db.DateTime)
    committed_id = db.Column(db.Integer)  # ID in permanent table after commit

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    import_session = db.relationship("ImportSession", back_populates="staging_elements")

    # Indexes for performance
    __table_args__ = (
        Index("idx_staging_session_type", "import_session_id", "element_type"),
        Index("idx_staging_committed", "is_committed"),
        Index("idx_staging_parent", "parent_element_uuid"),
    )

    def __repr__(self):
        return f"<StagingElement {self.element_uuid} - {self.element_type}>"

    def to_dict(self):
        """Convert staging element to dictionary."""
        return {
            "id": self.id,
            "element_type": self.element_type,
            "element_uuid": self.element_uuid,
            "element_data": self.element_data,
            "element_metadata": self.element_metadata,
            "source_row_number": self.source_row_number,
            "generated_by_llm": self.generated_by_llm,
            "llm_provider": self.llm_provider,
            "confidence_score": self.confidence_score,
            "requires_review": self.requires_review,
            "is_committed": self.is_committed,
            "committed_id": self.committed_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ImportCheckpoint(db.Model):
    """
    Checkpoint markers for granular recovery.

    Records each successful step in the import process,
    enabling resume from the last successful checkpoint.
    """

    __tablename__ = "import_checkpoints"

    id = db.Column(db.Integer, primary_key=True)

    # Session relationship
    import_session_id = db.Column(
        db.Integer,
        db.ForeignKey("import_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Checkpoint information
    checkpoint_type = db.Column(db.String(50), nullable=False, index=True)
    checkpoint_name = db.Column(db.String(100), nullable=False)
    checkpoint_data = db.Column(JSON)  # Checkpoint-specific data

    # Progress at checkpoint
    rows_processed = db.Column(db.Integer, default=0)
    elements_staged = db.Column(db.Integer, default=0)

    # Timing
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    duration_seconds = db.Column(db.Integer)

    # Relationships
    import_session = db.relationship("ImportSession", back_populates="checkpoints")

    def __repr__(self):
        return f"<ImportCheckpoint {self.checkpoint_type} - {self.checkpoint_name}>"

    def to_dict(self):
        """Convert checkpoint to dictionary."""
        return {
            "id": self.id,
            "checkpoint_type": self.checkpoint_type,
            "checkpoint_name": self.checkpoint_name,
            "checkpoint_data": self.checkpoint_data,
            "rows_processed": self.rows_processed,
            "elements_staged": self.elements_staged,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "duration_seconds": self.duration_seconds,
        }
