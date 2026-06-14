"""
AI Chat CRUD Approval Model

Tracks pending CRUD operations from AI chat for user approval.
Prevents immediate execution of data modifications via natural language.
"""

import json
from datetime import datetime
from enum import Enum

from app import db


class ApprovalStatus(Enum):
    """Status of CRUD approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AIChatCRUDApproval(db.Model):
    """
    Tracks pending CRUD operations from AI chat interactions.

    When a user issues a CRUD command via chat (e.g., "Create a Customer
    Management capability"), the system creates a pending approval record
    instead of executing immediately. The user must review and confirm
    before the operation is executed.
    """

    __tablename__ = "ai_chat_crud_approvals"

    id = db.Column(db.Integer, primary_key=True)

    # User who initiated the request
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Operation details
    operation_type = db.Column(db.String(50), nullable=False)  # create, update, delete
    entity_type = db.Column(db.String(50), nullable=False)  # capability, application, vendor, etc.
    entity_id = db.Column(db.Integer, nullable=True)  # For update/delete operations

    # The natural language command that triggered this
    original_command = db.Column(db.Text, nullable=False)

    # JSON payload for the operation
    operation_payload = db.Column(db.Text, nullable=False)

    # Human-readable summary of what will happen
    summary = db.Column(db.Text, nullable=False)

    # Approval status
    status = db.Column(db.Enum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)  # Auto-expire pending approvals
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Rejection reason
    rejected_reason = db.Column(db.Text, nullable=True)

    # Execution result (if approved and executed)
    execution_result = db.Column(db.Text, nullable=True)  # JSON
    executed_at = db.Column(db.DateTime, nullable=True)

    # Session/chat context
    chat_session_id = db.Column(db.String(100), nullable=True)

    def to_dict(self):
        """Convert approval record to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "operation_type": self.operation_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "original_command": self.original_command,
            "operation_payload": json.loads(self.operation_payload) if self.operation_payload else None,
            "summary": self.summary,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approved_by_id": self.approved_by_id,
            "rejected_reason": self.rejected_reason,
            "execution_result": json.loads(self.execution_result) if self.execution_result else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "chat_session_id": self.chat_session_id,
        }

    def approve(self, user_id):
        """Mark approval as approved by a user."""
        self.status = ApprovalStatus.APPROVED
        self.approved_at = datetime.utcnow()
        self.approved_by_id = user_id

    def reject(self, reason=None):
        """Mark approval as rejected."""
        self.status = ApprovalStatus.REJECTED
        self.rejected_reason = reason

    def execute(self, result):
        """Mark as executed with result."""
        self.execution_result = json.dumps(result)
        self.executed_at = datetime.utcnow()

    def is_expired(self):
        """Check if approval has expired."""
        return datetime.utcnow() > self.expires_at

    @classmethod
    def get_pending_for_user(cls, user_id):
        """Get all pending approvals for a user."""
        return cls.query.filter_by(
            user_id=user_id,
            status=ApprovalStatus.PENDING
        ).filter(
            cls.expires_at > datetime.utcnow()
        ).all()

    @classmethod
    def get_by_id_and_user(cls, approval_id, user_id):
        """Get approval by ID ensuring it belongs to the user."""
        return cls.query.filter_by(
            id=approval_id,
            user_id=user_id
        ).first()
