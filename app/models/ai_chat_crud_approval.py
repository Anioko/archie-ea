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

    # ARCH-020: identifies the specific agent turn/run that raised this approval,
    # distinct from chat_session_id (which identifies the conversation). Nullable
    # per CLAUDE.md's schema rules (reconcile-schema is ADD-COLUMN-only and every
    # new column must tolerate NULL on a pre-existing production row).
    agent_turn_id = db.Column(db.String(64), nullable=True)

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
            "agent_turn_id": self.agent_turn_id,
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

    @classmethod
    def get_pending_for_session(cls, user_id, chat_session_id):
        """Pending approvals for one user scoped to one chat session (ARCH-020).

        Lets the agent answer "what's still pending in *this* conversation"
        instead of only "what's pending for this user anywhere" — the gap that
        let a second, identical approval get queued when the user said
        "I approve" and the agent had no way to see the first one was already
        sitting there for this session.
        """
        if not chat_session_id:
            return []
        return (
            cls.query.filter_by(
                user_id=user_id,
                chat_session_id=chat_session_id,
                status=ApprovalStatus.PENDING,
            )
            .filter(cls.expires_at > datetime.utcnow())
            .order_by(cls.created_at.desc())
            .all()
        )


class AIChatApprovalAuditLog(db.Model):
    """Immutable audit trail of every approval state transition (ARCH-022).

    A row is appended, never updated or deleted, for every transition a
    AIChatCRUDApproval record goes through: created, approved, rejected,
    expired, executed, execution_refused. This is the record that lets the
    platform answer "did a human approve this, or did a restart / expiry
    sweep push it through" — a question the approval row alone cannot answer,
    because it only carries the *current* state, not the history of how it
    got there.

    actor_user_id is nullable because a system-initiated transition (an
    expiry sweep) legitimately has no human actor -- but for the "approved"
    and "executed" events specifically, application code refuses to write a
    system-actor row (see AIChatApprovalService._audit): those transitions
    require a human, or they don't happen.
    """

    __tablename__ = "ai_chat_approval_audit_log"

    id = db.Column(db.Integer, primary_key=True)
    approval_id = db.Column(
        db.Integer, db.ForeignKey("ai_chat_crud_approvals.id"), nullable=False, index=True
    )
    from_status = db.Column(db.String(20), nullable=True)
    to_status = db.Column(db.String(20), nullable=False)
    event = db.Column(db.String(30), nullable=False)  # created|approved|rejected|expired|executed|execution_refused
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    actor_type = db.Column(db.String(20), nullable=False, default="user")  # user|system
    reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "approval_id": self.approval_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "event": self.event,
            "actor_user_id": self.actor_user_id,
            "actor_type": self.actor_type,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
