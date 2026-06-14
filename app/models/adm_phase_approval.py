"""
ADM Phase Approval and Governance Models

Implements Architecture Board approval workflow for ADM phase transitions.
Replaces drag-and-drop with governed transitions requiring explicit approval.
"""

import logging
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, event
from sqlalchemy.orm import attributes, relationship

from app import db
from app.models.mixins.core import TenantMixin

_state_logger = logging.getLogger(__name__ + ".state_machine")

# Valid status transitions for ADMPhaseApproval
_APPROVAL_TRANSITIONS = {
    "draft": {"submitted", "cancelled"},
    "submitted": {"under_review", "cancelled"},
    "under_review": {"pending_information", "approved", "approved_with_conditions", "rejected", "deferred"},
    "pending_information": {"under_review", "cancelled"},
    "approved": set(),  # terminal
    "approved_with_conditions": set(),  # terminal
    "rejected": {"draft"},  # can be reworked
    "deferred": {"submitted"},  # can be re-submitted
    "cancelled": set(),  # terminal
}


class ApprovalStatus(str, Enum):
    """Status of phase transition approval request."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    PENDING_INFO = "pending_information"
    APPROVED = "approved"
    APPROVED_WITH_CONDITIONS = "approved_with_conditions"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


class ADMPhaseApproval(TenantMixin, db.Model):
    """
    Architecture Board approval request for ADM phase transitions.

    Tracks formal approval workflow for moving cards between ADM phases,
    ensuring TOGAF governance is followed.
    """

    __tablename__ = "adm_phase_approvals"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    approval_number = Column(String(50), unique=True, nullable=False)  # ADM-2026-001

    # Card being moved
    card_id = Column(Integer, ForeignKey("kanban_cards.id"), nullable=False)
    board_id = Column(Integer, ForeignKey("kanban_boards.id"), nullable=False)

    # Phase transition details
    source_phase_id = Column(Integer, ForeignKey("adm_phases.id"), nullable=False)
    target_phase_id = Column(Integer, ForeignKey("adm_phases.id"), nullable=False)

    # Approval workflow
    status = Column(String(50), default="draft")

    # Requester
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    requested_at = Column(DateTime)

    # Business justification
    business_justification = Column(Text)
    technical_justification = Column(Text)
    risk_assessment = Column(Text)

    # Compliance evidence
    deliverables_completed = Column(JSON)  # List of completed deliverable IDs
    compliance_checklist_status = Column(JSON)  # Checklist item completion
    stakeholder_concurrence = Column(JSON)  # Stakeholder approvals

    # Architecture Board review
    reviewer_id = Column(Integer, ForeignKey("users.id"))
    review_started_at = Column(DateTime)
    review_completed_at = Column(DateTime)

    # Decision
    decision = Column(String(50))  # approved, approved_with_conditions, rejected, deferred
    decision_rationale = Column(Text)
    conditions = Column(JSON)  # Conditions for conditional approval
    decided_by_id = Column(Integer, ForeignKey("users.id"))
    decision_date = Column(DateTime)

    # ARB session link (if reviewed in formal session)
    arb_session_id = Column(Integer, ForeignKey("architecture_review_boards.id"))
    arb_review_item_id = Column(Integer, ForeignKey("arb_review_items.id"))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    card = relationship("KanbanCard", backref="phase_approvals")
    board = relationship("KanbanBoard", backref="phase_approvals")
    source_phase = relationship("ADMPhase", foreign_keys=[source_phase_id], backref="outgoing_approvals")
    target_phase = relationship("ADMPhase", foreign_keys=[target_phase_id], backref="incoming_approvals")
    requested_by = relationship("User", foreign_keys=[requested_by_id], backref="requested_phase_approvals")
    reviewer = relationship("User", foreign_keys=[reviewer_id], backref="reviewed_phase_approvals")
    decided_by = relationship("User", foreign_keys=[decided_by_id], backref="phase_approval_decisions")
    arb_session = relationship("ArchitectureReviewBoard", backref="adm_approvals")
    arb_review_item = relationship("ARBReviewItem", backref="adm_phase_approval")

    def __repr__(self):
        return f"<ADMPhaseApproval {self.approval_number}: {self.source_phase.code} -> {self.target_phase.code}>"

    @staticmethod
    def generate_approval_number():
        """Generate next approval request number."""
        year = datetime.utcnow().year
        last_approval = (
            ADMPhaseApproval.query.filter(ADMPhaseApproval.approval_number.like(f"ADM-{year}-%"))
            .order_by(ADMPhaseApproval.id.desc())
            .first()
        )

        if last_approval:
            try:
                last_num = int(last_approval.approval_number.split("-")[-1])
                next_num = last_num + 1
            except ValueError:
                next_num = 1
        else:
            next_num = 1

        return f"ADM-{year}-{next_num:03d}"

    def is_approved(self):
        """Check if approval is in an approved state."""
        return self.status in ["approved", "approved_with_conditions"]


class ADMComplianceCheckpoint(db.Model):
    """
    Individual compliance checkpoint items for phase gate validation.

    Tracks completion of specific gate criteria required for phase transitions.
    """

    __tablename__ = "adm_compliance_checkpoints"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    # Link to approval request
    approval_id = Column(Integer, ForeignKey("adm_phase_approvals.id"), nullable=False)

    # Checkpoint details
    checkpoint_name = Column(String(200), nullable=False)
    checkpoint_category = Column(String(50))  # deliverable, stakeholder, governance, technical
    description = Column(Text)

    # Completion status
    is_required = Column(Boolean, default=True)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime)
    completed_by_id = Column(Integer, ForeignKey("users.id"))

    # Evidence
    evidence_required = Column(Boolean, default=False)
    evidence_description = Column(Text)
    evidence_url = Column(String(500))
    evidence_notes = Column(Text)

    # Verification
    verified = Column(Boolean, default=False)
    verified_by_id = Column(Integer, ForeignKey("users.id"))
    verified_at = Column(DateTime)
    verification_notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    approval = relationship("ADMPhaseApproval", backref="checkpoints")
    completed_by = relationship("User", foreign_keys=[completed_by_id], backref="completed_checkpoints")
    verified_by = relationship("User", foreign_keys=[verified_by_id], backref="verified_checkpoints")

    def __repr__(self):
        return f"<ADMComplianceCheckpoint {self.checkpoint_name}: {self.is_completed}>"


class ADMStakeholderConcurrence(db.Model):
    """
    Stakeholder concurrence tracking for phase transitions.

    Records stakeholder approvals required before Architecture Board review.
    """

    __tablename__ = "adm_stakeholder_concurrences"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    # Link to approval request
    approval_id = Column(Integer, ForeignKey("adm_phase_approvals.id"), nullable=False)

    # Stakeholder details
    stakeholder_role = Column(String(100), nullable=False)  # business_owner, tech_lead, etc.
    stakeholder_user_id = Column(Integer, ForeignKey("users.id"))
    stakeholder_name = Column(String(200))  # If external stakeholder
    stakeholder_email = Column(String(255))

    # Concurrence status
    status = Column(String(50), default="pending")  # pending, approved, rejected, abstained
    concurrence_date = Column(DateTime)

    # Comments
    comments = Column(Text)
    concerns = Column(Text)

    # Timestamps
    requested_at = Column(DateTime, default=datetime.utcnow)
    responded_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    approval = relationship("ADMPhaseApproval", backref="stakeholder_concurrences")
    stakeholder_user = relationship("User", foreign_keys=[stakeholder_user_id], backref="stakeholder_concurrences")

    def __repr__(self):
        return f"<ADMStakeholderConcurrence {self.stakeholder_role}: {self.status}>"


class ADMTransitionHistory(TenantMixin, db.Model):
    """
    History of phase transitions (approved moves).

    Audit trail of all successfully completed phase transitions.
    """

    __tablename__ = "adm_transition_history"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    # Card details
    card_id = Column(Integer, ForeignKey("kanban_cards.id"), nullable=False)
    board_id = Column(Integer, ForeignKey("kanban_boards.id"), nullable=False)

    # Transition details
    source_phase_id = Column(Integer, ForeignKey("adm_phases.id"), nullable=False)
    target_phase_id = Column(Integer, ForeignKey("adm_phases.id"), nullable=False)

    # Approval link
    approval_id = Column(Integer, ForeignKey("adm_phase_approvals.id"), nullable=False)

    # Transition execution
    transitioned_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    transitioned_at = Column(DateTime, default=datetime.utcnow)

    # Notes
    notes = Column(Text)

    # Relationships
    card = relationship("KanbanCard", backref="transition_history")
    board = relationship("KanbanBoard", backref="transition_history")
    source_phase = relationship("ADMPhase", foreign_keys=[source_phase_id])
    target_phase = relationship("ADMPhase", foreign_keys=[target_phase_id])
    approval = relationship("ADMPhaseApproval", backref="transition_record")
    transitioned_by = relationship("User", backref="executed_transitions")

    def __repr__(self):
        return f"<ADMTransitionHistory {self.source_phase.code} -> {self.target_phase.code}>"


# ============================================================================
# State Machine Enforcement via SQLAlchemy Events
# ============================================================================


def _validate_approval_status(target, value, oldvalue, initiator):
    """SQLAlchemy event listener that validates ADMPhaseApproval status transitions."""
    if oldvalue is value or oldvalue is None:
        return value
    if oldvalue is attributes.NO_VALUE or oldvalue is attributes.NEVER_SET:
        return value
    if oldvalue == value:
        return value
    allowed = _APPROVAL_TRANSITIONS.get(oldvalue, set())
    if value not in allowed:
        _state_logger.warning(
            "Invalid ADMPhaseApproval transition blocked: %s -> %s (allowed: %s)",
            oldvalue, value, allowed or "none (terminal)",
        )
        raise ValueError(
            f"Invalid ADMPhaseApproval status transition: {oldvalue} -> {value}. "
            f"Allowed: {allowed or 'none (terminal state)'}"
        )
    _state_logger.debug("ADMPhaseApproval status: %s -> %s", oldvalue, value)
    return value


event.listen(ADMPhaseApproval.status, "set", _validate_approval_status, retval=True)
