"""
Batch Processing with Progress & Recovery Models

Provides comprehensive batch processing capabilities with progress tracking,
error recovery, checkpoint management, and transaction rollback for enterprise-scale operations.
"""

import json
from datetime import datetime
from enum import Enum

from .. import db


class BatchJobStatus(Enum):
    """Batch job status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECOVERING = "recovering"


class BatchJobType(Enum):
    """Batch job type enumeration."""

    AI_IMPORT = "ai_import"
    CAPABILITY_MAPPING = "capability_mapping"
    APQC_CLASSIFICATION = "apqc_classification"
    ARCHIMATE_GENERATION = "archimate_generation"
    VENDOR_ANALYSIS = "vendor_analysis"
    TAXONOMY_VALIDATION = "taxonomy_validation"
    BULK_UPDATE = "bulk_update"


class BatchJob(db.Model):
    """Master batch job record for tracking and management."""

    __tablename__ = "batch_jobs"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.BigInteger, primary_key=True)
    job_name = db.Column(db.String(200), nullable=False, index=True)
    job_type = db.Column(db.Enum(BatchJobType), nullable=False, index=True)
    status = db.Column(db.Enum(BatchJobStatus), default=BatchJobStatus.PENDING, index=True)

    # Job configuration
    total_items = db.Column(db.Integer, nullable=False, default=0)
    processed_items = db.Column(db.Integer, default=0)
    successful_items = db.Column(db.Integer, default=0)
    failed_items = db.Column(db.Integer, default=0)
    skipped_items = db.Column(db.Integer, default=0)

    # Progress tracking
    progress_percentage = db.Column(db.Numeric(5, 2), default=0.0)
    estimated_completion_time = db.Column(db.DateTime)
    actual_completion_time = db.Column(db.DateTime)

    # Performance metrics
    items_per_second = db.Column(db.Numeric(10, 2))
    average_processing_time = db.Column(db.Numeric(10, 3))  # seconds per item
    total_processing_time = db.Column(db.Numeric(10, 3))  # seconds

    # Error handling
    error_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    retry_count = db.Column(db.Integer, default=0)
    last_error_message = db.Column(db.Text)
    last_error_time = db.Column(db.DateTime)

    # Recovery and checkpoint
    checkpoint_data = db.Column(db.Text)  # JSON with recovery state
    last_checkpoint_time = db.Column(db.DateTime)
    recovery_attempts = db.Column(db.Integer, default=0)

    # Job parameters
    job_parameters = db.Column(db.Text)  # JSON with job-specific parameters
    confidence_threshold = db.Column(db.Numeric(3, 2), default=0.6)
    auto_retry = db.Column(db.Boolean, default=True)
    parallel_processing = db.Column(db.Boolean, default=False)
    batch_size = db.Column(db.Integer, default=100)

    # Status and metadata
    priority = db.Column(db.Integer, default=5)  # 1 - 10, lower is higher priority
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    created_by = db.relationship("User", backref="created_batch_jobs")
    items = db.relationship(
        "BatchJobItem", back_populates="batch_job", cascade="all, delete-orphan", lazy="select"
    )
    checkpoints = db.relationship(
        "BatchJobCheckpoint",
        back_populates="batch_job",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self):
        return f"<BatchJob {self.job_name} ({self.job_type.value}) - {self.status.value}>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "job_name": self.job_name,
            "job_type": self.job_type.value,
            "status": self.status.value,
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "successful_items": self.successful_items,
            "failed_items": self.failed_items,
            "skipped_items": self.skipped_items,
            "progress_percentage": float(self.progress_percentage),
            "estimated_completion_time": self.estimated_completion_time.isoformat()
            if self.estimated_completion_time
            else None,
            "actual_completion_time": self.actual_completion_time.isoformat()
            if self.actual_completion_time
            else None,
            "items_per_second": float(self.items_per_second) if self.items_per_second else None,
            "average_processing_time": float(self.average_processing_time)
            if self.average_processing_time
            else None,
            "total_processing_time": float(self.total_processing_time)
            if self.total_processing_time
            else None,
            "error_count": self.error_count,
            "retry_count": self.retry_count,
            "last_error_message": self.last_error_message,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "recovery_attempts": self.recovery_attempts,
            "job_parameters": json.loads(self.job_parameters) if self.job_parameters else {},
            "confidence_threshold": float(self.confidence_threshold),
            "auto_retry": self.auto_retry,
            "parallel_processing": self.parallel_processing,
            "batch_size": self.batch_size,
            "priority": self.priority,
            "created_by_id": self.created_by_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class BatchJobItem(db.Model):
    """Individual item within a batch job with detailed status tracking."""

    __tablename__ = "batch_job_items"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.BigInteger, primary_key=True)
    batch_job_id = db.Column(
        db.BigInteger, db.ForeignKey("batch_jobs.id"), nullable=False, index=True
    )
    item_sequence = db.Column(db.Integer, nullable=False)  # Order within batch
    item_type = db.Column(db.String(50))  # "application", "capability", "process", etc.
    item_id = db.Column(db.BigInteger)  # Foreign key to the actual item
    item_name = db.Column(db.String(500))  # Human-readable name
    item_data = db.Column(db.Text)  # JSON with item-specific data

    # Processing status
    status = db.Column(
        db.String(30), default="pending"
    )  # pending, processing, completed, failed, skipped, retrying
    processing_attempts = db.Column(db.Integer, default=0)
    max_attempts = db.Column(db.Integer, default=3)

    # Processing metrics
    processing_start_time = db.Column(db.DateTime)
    processing_end_time = db.Column(db.DateTime)
    processing_duration = db.Column(db.Numeric(10, 3))  # seconds

    # Results and output
    result_data = db.Column(db.Text)  # JSON with processing results
    confidence_score = db.Column(db.Numeric(3, 2))  # 0.0 - 1.0
    warnings = db.Column(db.Text)  # JSON array of warnings
    recommendations = db.Column(db.Text)  # JSON array of recommendations

    # Error handling
    error_message = db.Column(db.Text)
    error_type = db.Column(db.String(100))  # "validation_error", "processing_error", "system_error"
    error_data = db.Column(db.Text)  # JSON with error details
    retry_after = db.Column(db.DateTime)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    batch_job = db.relationship("BatchJob", back_populates="items")

    def __repr__(self):
        return f"<BatchJobItem {self.item_name} ({self.status})>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "batch_job_id": self.batch_job_id,
            "item_sequence": self.item_sequence,
            "item_type": self.item_type,
            "item_id": self.item_id,
            "item_name": self.item_name,
            "item_data": json.loads(self.item_data) if self.item_data else {},
            "status": self.status,
            "processing_attempts": self.processing_attempts,
            "max_attempts": self.max_attempts,
            "processing_start_time": self.processing_start_time.isoformat()
            if self.processing_start_time
            else None,
            "processing_end_time": self.processing_end_time.isoformat()
            if self.processing_end_time
            else None,
            "processing_duration": float(self.processing_duration)
            if self.processing_duration
            else None,
            "result_data": json.loads(self.result_data) if self.result_data else {},
            "confidence_score": float(self.confidence_score) if self.confidence_score else None,
            "warnings": json.loads(self.warnings) if self.warnings else [],
            "recommendations": json.loads(self.recommendations) if self.recommendations else [],
            "error_message": self.error_message,
            "error_type": self.error_type,
            "error_data": json.loads(self.error_data) if self.error_data else {},
            "retry_after": self.retry_after.isoformat() if self.retry_after else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class BatchJobCheckpoint(db.Model):
    """Checkpoint data for batch job recovery and resume."""

    __tablename__ = "batch_job_checkpoints"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.BigInteger, primary_key=True)
    batch_job_id = db.Column(
        db.BigInteger, db.ForeignKey("batch_jobs.id"), nullable=False, index=True
    )
    checkpoint_name = db.Column(db.String(200), nullable=False)
    checkpoint_type = db.Column(db.String(50))  # "progress", "error", "milestone", "manual"

    # Checkpoint state
    processed_items_count = db.Column(db.Integer, default=0)
    successful_items_count = db.Column(db.Integer, default=0)
    failed_items_count = db.Column(db.Integer, default=0)

    # Recovery data
    checkpoint_data = db.Column(db.Text)  # JSON with recovery state
    last_processed_item_id = db.Column(db.BigInteger)
    last_successful_item_sequence = db.Column(db.Integer)

    # Performance snapshot
    items_per_second_at_checkpoint = db.Column(db.Numeric(10, 2))
    memory_usage_at_checkpoint = db.Column(db.Numeric(10, 2))  # MB
    cpu_usage_at_checkpoint = db.Column(db.Numeric(5, 2))  # percentage

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    created_by = db.Column(db.String(100))  # "system", "user", "recovery"

    # Relationships
    batch_job = db.relationship("BatchJob", back_populates="checkpoints")

    def __repr__(self):
        return f"<BatchJobCheckpoint {self.checkpoint_name} ({self.checkpoint_type})>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "batch_job_id": self.batch_job_id,
            "checkpoint_name": self.checkpoint_name,
            "checkpoint_type": self.checkpoint_type,
            "processed_items_count": self.processed_items_count,
            "successful_items_count": self.successful_items_count,
            "failed_items_count": self.failed_items_count,
            "checkpoint_data": json.loads(self.checkpoint_data) if self.checkpoint_data else {},
            "last_processed_item_id": self.last_processed_item_id,
            "last_successful_item_sequence": self.last_successful_item_sequence,
            "items_per_second_at_checkpoint": float(self.items_per_second_at_checkpoint)
            if self.items_per_second_at_checkpoint
            else None,
            "memory_usage_at_checkpoint": float(self.memory_usage_at_checkpoint)
            if self.memory_usage_at_checkpoint
            else None,
            "cpu_usage_at_checkpoint": float(self.cpu_usage_at_checkpoint)
            if self.cpu_usage_at_checkpoint
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }


class BatchJobError(db.Model):
    """Detailed error tracking for batch jobs with recovery suggestions."""

    __tablename__ = "batch_job_errors"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.BigInteger, primary_key=True)
    batch_job_id = db.Column(
        db.BigInteger, db.ForeignKey("batch_jobs.id"), nullable=False, index=True
    )
    batch_job_item_id = db.Column(db.BigInteger, db.ForeignKey("batch_job_items.id"))

    # Error details
    error_type = db.Column(
        db.String(100), nullable=False
    )  # "validation", "processing", "system", "timeout"
    error_code = db.Column(db.String(50))  # Specific error code
    error_message = db.Column(db.Text, nullable=False)
    error_stack_trace = db.Column(db.Text)  # Full stack trace if available

    # Context information
    item_type = db.Column(db.String(50))
    item_name = db.Column(db.String(500))
    processing_step = db.Column(db.String(100))  # "validation", "mapping", "generation", etc.

    # Recovery information
    can_retry = db.Column(db.Boolean, default=True)
    retry_delay_seconds = db.Column(db.Integer, default=60)
    max_retries = db.Column(db.Integer, default=3)
    retry_count = db.Column(db.Integer, default=0)

    # Recovery suggestions
    recovery_action = db.Column(db.String(200))  # "retry", "skip", "manual_intervention", "abort"
    recovery_suggestion = db.Column(db.Text)  # Human-readable recovery suggestion
    auto_recovery_possible = db.Column(db.Boolean, default=False)

    # Error classification
    severity = db.Column(db.String(20), default="medium")  # "low", "medium", "high", "critical"
    category = db.Column(db.String(50))  # "user_error", "system_error", "data_error", "timeout"

    # Metadata
    occurred_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    resolved_at = db.Column(db.DateTime)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    batch_job = db.relationship("BatchJob")
    batch_job_item = db.relationship("BatchJobItem")
    resolved_by = db.relationship("User", backref="resolved_batch_errors")

    def __repr__(self):
        return f"<BatchJobError {self.error_type}: {self.error_message[:50]}...>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "batch_job_id": self.batch_job_id,
            "batch_job_item_id": self.batch_job_item_id,
            "error_type": self.error_type,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "error_stack_trace": self.error_stack_trace,
            "item_type": self.item_type,
            "item_name": self.item_name,
            "processing_step": self.processing_step,
            "can_retry": self.can_retry,
            "retry_delay_seconds": self.retry_delay_seconds,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "recovery_action": self.recovery_action,
            "recovery_suggestion": self.recovery_suggestion,
            "auto_recovery_possible": self.auto_recovery_possible,
            "severity": self.severity,
            "category": self.category,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by_id": self.resolved_by_id,
        }


class BatchJobStatistics(db.Model):
    """Aggregated statistics for batch job performance monitoring."""

    __tablename__ = "batch_job_statistics"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.BigInteger, primary_key=True)
    job_type = db.Column(db.Enum(BatchJobType), nullable=False, index=True)
    date_bucket = db.Column(db.Date, nullable=False, index=True)  # Daily aggregation
    time_bucket = db.Column(db.String(20), index=True)  # "hourly", "daily", "weekly", "monthly"

    # Job counts
    total_jobs = db.Column(db.Integer, default=0)
    completed_jobs = db.Column(db.Integer, default=0)
    failed_jobs = db.Column(db.Integer, default=0)
    cancelled_jobs = db.Column(db.Integer, default=0)

    # Item counts
    total_items = db.Column(db.BigInteger, default=0)
    processed_items = db.Column(db.BigInteger, default=0)
    successful_items = db.Column(db.BigInteger, default=0)
    failed_items = db.Column(db.BigInteger, default=0)
    skipped_items = db.Column(db.BigInteger, default=0)

    # Performance metrics
    average_items_per_second = db.Column(db.Numeric(10, 2))
    average_processing_time = db.Column(db.Numeric(10, 3))  # seconds per item
    total_processing_time = db.Column(db.Numeric(15, 3))  # seconds

    # Error metrics
    total_errors = db.Column(db.Integer, default=0)
    average_errors_per_job = db.Column(db.Numeric(10, 2))
    error_rate_percentage = db.Column(db.Numeric(5, 2))  # percentage

    # Resource metrics
    average_memory_usage = db.Column(db.Numeric(10, 2))  # MB
    peak_memory_usage = db.Column(db.Numeric(10, 2))  # MB
    average_cpu_usage = db.Column(db.Numeric(5, 2))  # percentage
    peak_cpu_usage = db.Column(db.Numeric(5, 2))  # percentage

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<BatchJobStatistics {self.job_type.value} - {self.date_bucket}>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "job_type": self.job_type.value,
            "date_bucket": self.date_bucket.isoformat() if self.date_bucket else None,
            "time_bucket": self.time_bucket,
            "total_jobs": self.total_jobs,
            "completed_jobs": self.completed_jobs,
            "failed_jobs": self.failed_jobs,
            "cancelled_jobs": self.cancelled_jobs,
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "successful_items": self.successful_items,
            "failed_items": self.failed_items,
            "skipped_items": self.skipped_items,
            "average_items_per_second": float(self.average_items_per_second)
            if self.average_items_per_second
            else None,
            "average_processing_time": float(self.average_processing_time)
            if self.average_processing_time
            else None,
            "total_processing_time": float(self.total_processing_time)
            if self.total_processing_time
            else None,
            "total_errors": self.total_errors,
            "average_errors_per_job": float(self.average_errors_per_job)
            if self.average_errors_per_job
            else None,
            "error_rate_percentage": float(self.error_rate_percentage)
            if self.error_rate_percentage
            else None,
            "average_memory_usage": float(self.average_memory_usage)
            if self.average_memory_usage
            else None,
            "peak_memory_usage": float(self.peak_memory_usage) if self.peak_memory_usage else None,
            "average_cpu_usage": float(self.average_cpu_usage) if self.average_cpu_usage else None,
            "peak_cpu_usage": float(self.peak_cpu_usage) if self.peak_cpu_usage else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
