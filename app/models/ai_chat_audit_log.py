"""
AI Chat Audit Log Model

Comprehensive audit trail for all AI Chat operations.
Tracks user actions, AI decisions, data modifications, and system events.
"""

import json
from datetime import datetime
from enum import Enum

from app import db


class AuditEventType(Enum):
    """Types of audit events."""
    CHAT_MESSAGE = "chat_message"
    CRUD_OPERATION = "crud_operation"
    APPROVAL_CREATED = "approval_created"
    APPROVAL_APPROVED = "approval_approved"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_EXECUTED = "approval_executed"
    APPROVAL_EXPIRED = "approval_expired"
    ENTITY_MATCHED = "entity_matched"
    ARCHIMATE_GENERATED = "archimate_generated"
    MODEL_SWITCHED = "model_switched"
    ERROR_OCCURRED = "error_occurred"
    SECURITY_EVENT = "security_event"


class AIChatAuditLog(db.Model):
    """
    Comprehensive audit log for AI Chat operations.
    
    Tracks:
    - All chat messages and their context
    - CRUD operations with before/after state
    - Approval workflow events
    - Entity matching decisions
    - ArchiMate generation events
    - Model usage and switches
    - Errors and security events
    """

    __tablename__ = "ai_chat_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    
    # Event classification
    event_type = db.Column(db.Enum(AuditEventType), nullable=False)
    severity = db.Column(db.String(20), default="info")  # info, warning, error, critical
    
    # User context
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user_name = db.Column(db.String(100), nullable=True)  # Denormalized for audit trail
    
    # Chat context
    chat_session_id = db.Column(db.String(100), nullable=True)
    domain = db.Column(db.String(50), nullable=True)
    persona = db.Column(db.String(50), nullable=True)
    
    # Event details
    message = db.Column(db.Text, nullable=True)  # Original user message
    ai_response = db.Column(db.Text, nullable=True)  # AI response text
    
    # Operation details (for CRUD)
    operation_type = db.Column(db.String(50), nullable=True)  # create, update, delete
    entity_type = db.Column(db.String(50), nullable=True)  # capability, application, vendor
    entity_id = db.Column(db.Integer, nullable=True)
    
    # Before/after state (JSON)
    before_state = db.Column(db.Text, nullable=True)  # JSON
    after_state = db.Column(db.Text, nullable=True)  # JSON
    
    # Approval workflow tracking
    approval_id = db.Column(db.Integer, db.ForeignKey("ai_chat_crud_approvals.id"), nullable=True)
    
    # AI model information
    model_used = db.Column(db.String(100), nullable=True)
    provider_used = db.Column(db.String(50), nullable=True)
    
    # Confidence and validation
    confidence_score = db.Column(db.Float, nullable=True)
    validation_status = db.Column(db.String(50), nullable=True)  # passed, failed, warning
    validation_details = db.Column(db.Text, nullable=True)  # JSON
    
    # Error tracking
    error_message = db.Column(db.Text, nullable=True)
    error_stack_trace = db.Column(db.Text, nullable=True)
    
    # IP and session for security
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 compatible
    session_token_hash = db.Column(db.String(64), nullable=True)  # SHA-256 hash
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    processing_time_ms = db.Column(db.Integer, nullable=True)
    
    # Metadata
    extra_metadata = db.Column(db.Text, nullable=True)  # Additional JSON data
    
    def to_dict(self):
        """Convert audit log to dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type.value if self.event_type else None,
            "severity": self.severity,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "chat_session_id": self.chat_session_id,
            "domain": self.domain,
            "persona": self.persona,
            "message": self.message,
            "ai_response": self.ai_response,
            "operation_type": self.operation_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "before_state": json.loads(self.before_state) if self.before_state else None,
            "after_state": json.loads(self.after_state) if self.after_state else None,
            "approval_id": self.approval_id,
            "model_used": self.model_used,
            "provider_used": self.provider_used,
            "confidence_score": self.confidence_score,
            "validation_status": self.validation_status,
            "validation_details": json.loads(self.validation_details) if self.validation_details else None,
            "error_message": self.error_message,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processing_time_ms": self.processing_time_ms,
            "extra_metadata": json.loads(self.extra_metadata) if self.extra_metadata else None,
        }

    @classmethod
    def get_recent_for_user(cls, user_id: int, limit: int = 50):
        """Get recent audit logs for a user."""
        return cls.query.filter_by(user_id=user_id).order_by(cls.created_at.desc()).limit(limit).all()

    @classmethod
    def get_by_event_type(cls, event_type: AuditEventType, limit: int = 100):
        """Get audit logs by event type."""
        return cls.query.filter_by(event_type=event_type).order_by(cls.created_at.desc()).limit(limit).all()

    @classmethod
    def get_by_approval_id(cls, approval_id: int):
        """Get all audit logs related to a specific approval."""
        return cls.query.filter_by(approval_id=approval_id).order_by(cls.created_at).all()

    @classmethod
    def get_security_events(cls, severity: str = "critical", hours: int = 24):
        """Get security events by severity within time window."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return cls.query.filter(
            cls.event_type == AuditEventType.SECURITY_EVENT,
            cls.severity == severity,
            cls.created_at >= cutoff
        ).order_by(cls.created_at.desc()).all()
