"""
ADM Audit Log Models and Service

Comprehensive audit trail for all ADM activities.
Tracks who moved cards, when, from which phase to which,
approval chains, compliance evidence, and Architecture Board decisions.
Supports regulatory audit requirements.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app import db


class ADMAuditAction(str, Enum):
    """Types of audit actions tracked in ADM."""

    # Card operations
    CARD_CREATED = "card_created"
    CARD_UPDATED = "card_updated"
    CARD_DELETED = "card_deleted"
    CARD_MOVED = "card_moved"

    # Phase operations
    PHASE_TRANSITION_REQUESTED = "phase_transition_requested"
    PHASE_TRANSITION_APPROVED = "phase_transition_approved"
    PHASE_TRANSITION_REJECTED = "phase_transition_rejected"
    PHASE_TRANSITION_EXECUTED = "phase_transition_executed"

    # Approval workflow
    APPROVAL_CREATED = "approval_created"
    APPROVAL_SUBMITTED = "approval_submitted"
    APPROVAL_ASSIGNED = "approval_assigned"
    APPROVAL_DECISION_RECORDED = "approval_decision_recorded"
    APPROVAL_CANCELLED = "approval_cancelled"

    # Compliance
    CHECKPOINT_COMPLETED = "checkpoint_completed"
    CHECKPOINT_VERIFIED = "checkpoint_verified"

    # Stakeholder
    STAKEHOLDER_CONCURRENCE_REQUESTED = "stakeholder_concurrence_requested"
    STAKEHOLDER_CONCURRENCE_RECORDED = "stakeholder_concurrence_recorded"

    # Board operations
    BOARD_CREATED = "board_created"
    BOARD_UPDATED = "board_updated"
    BOARD_DELETED = "board_deleted"

    # Comment operations
    COMMENT_ADDED = "comment_added"
    COMMENT_UPDATED = "comment_updated"
    COMMENT_DELETED = "comment_deleted"

    # Attachment operations
    ATTACHMENT_ADDED = "attachment_added"
    ATTACHMENT_REMOVED = "attachment_removed"

    # ArchiMate associations
    ARCHIMATE_ELEMENT_LINKED = "archimate_element_linked"
    ARCHIMATE_ELEMENT_UNLINKED = "archimate_element_unlinked"

    # Application/System associations
    APPLICATION_LINKED = "application_linked"
    APPLICATION_UNLINKED = "application_unlinked"
    SYSTEM_LINKED = "system_linked"
    SYSTEM_UNLINKED = "system_unlinked"

    # ARB integration
    ARB_REVIEW_CREATED = "arb_review_created"
    ARB_REVIEW_LINKED = "arb_review_linked"


class ADMAuditLog(db.Model):
    """
    Comprehensive audit log for all ADM Kanban activities.

    Supports regulatory audit requirements with full traceability
    of who did what, when, and why.
    """

    __tablename__ = "adm_audit_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    # Audit reference
    audit_id = Column(String(100), unique=True, nullable=False)  # ADM-AUDIT-2026-001

    # Entity being audited
    entity_type = Column(String(50), nullable=False)  # card, board, approval, checkpoint, etc.
    entity_id = Column(Integer, nullable=False)
    entity_reference = Column(String(255))  # Human-readable reference (e.g., card title)

    # Action details
    action = Column(String(50), nullable=False)  # From ADMAuditAction
    action_description = Column(Text)

    # Changed values (for updates)
    old_values = Column(JSON)
    new_values = Column(JSON)
    changed_fields = Column(JSON)  # List of field names that changed

    # Context
    board_id = Column(Integer, ForeignKey("kanban_boards.id"))
    card_id = Column(Integer, ForeignKey("kanban_cards.id"))
    approval_id = Column(Integer, ForeignKey("adm_phase_approvals.id"))
    phase_id = Column(Integer, ForeignKey("adm_phases.id"))

    # Phase transition context (if applicable)
    source_phase_id = Column(Integer, ForeignKey("adm_phases.id"))
    target_phase_id = Column(Integer, ForeignKey("adm_phases.id"))
    source_phase_code = Column(String(10))
    target_phase_code = Column(String(10))

    # Actor information
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor_email = Column(String(255))
    actor_role = Column(String(100))  # Role at time of action

    # Request context
    ip_address = Column(String(100))
    user_agent = Column(String(500))
    request_id = Column(String(100))  # For correlating with web requests
    session_id = Column(String(100))

    # Business context
    justification = Column(Text)  # Business justification provided
    approval_chain = Column(JSON)  # List of approvals in chain

    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    board = relationship("KanbanBoard", backref="audit_logs")
    card = relationship("KanbanCard", backref="audit_logs")
    approval = relationship("ADMPhaseApproval", backref="audit_logs")
    phase = relationship("ADMPhase", foreign_keys=[phase_id])
    source_phase = relationship("ADMPhase", foreign_keys=[source_phase_id])
    target_phase = relationship("ADMPhase", foreign_keys=[target_phase_id])
    actor = relationship("User", backref="adm_audit_actions")

    def __repr__(self):
        return f"<ADMAuditLog {self.audit_id}: {self.action} on {self.entity_type}>"

    @staticmethod
    def generate_audit_id():
        """Generate unique audit ID."""
        year = datetime.utcnow().year
        last_audit = (
            ADMAuditLog.query.filter(ADMAuditLog.audit_id.like(f"ADM-AUDIT-{year}-%"))
            .order_by(ADMAuditLog.id.desc())
            .first()
        )

        if last_audit:
            try:
                last_num = int(last_audit.audit_id.split("-")[-1])
                next_num = last_num + 1
            except ValueError:
                next_num = 1
        else:
            next_num = 1

        return f"ADM-AUDIT-{year}-{next_num:06d}"


class ADMAuditSummary(db.Model):
    """
    Aggregated audit summary for quick reporting.

    Pre-computed summaries for common audit queries.
    """

    __tablename__ = "adm_audit_summaries"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    # Summary scope
    summary_type = Column(String(50), nullable=False)  # board, card, user, phase
    scope_id = Column(Integer, nullable=False)  # ID of the entity being summarized
    scope_name = Column(String(255))

    # Time period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # Aggregated metrics
    total_actions = Column(Integer, default=0)
    cards_created = Column(Integer, default=0)
    cards_moved = Column(Integer, default=0)
    approvals_submitted = Column(Integer, default=0)
    approvals_approved = Column(Integer, default=0)
    approvals_rejected = Column(Integer, default=0)
    phase_transitions = Column(JSON)  # Count by phase

    # Actor summary
    unique_actors = Column(Integer, default=0)
    top_actors = Column(JSON)  # List of {user_id, action_count}

    # Compliance
    checkpoints_completed = Column(Integer, default=0)
    stakeholder_concurrences = Column(Integer, default=0)

    # Timestamps
    computed_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ADMAuditSummary {self.summary_type}: {self.period_start} to {self.period_end}>"


class ADMDataRetentionPolicy(db.Model):
    """
    Data retention policy configuration for ADM audit logs.

    Configurable retention periods for different audit event types.
    """

    __tablename__ = "adm_data_retention_policies"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    policy_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)

    # Retention rules (days)
    card_operations_retention_days = Column(Integer, default=2555)  # 7 years
    phase_transition_retention_days = Column(Integer, default=2555)
    approval_workflow_retention_days = Column(Integer, default=3650)  # 10 years
    compliance_audit_retention_days = Column(Integer, default=3650)
    system_generated_retention_days = Column(Integer, default=365)  # 1 year

    # Archival configuration
    auto_archive_enabled = Column(Boolean, default=False)
    archive_after_days = Column(Integer, default=1095)  # 3 years
    archive_location = Column(String(500))

    # Policy status
    is_active = Column(Boolean, default=True)
    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ADMDataRetentionPolicy {self.policy_name}>"
