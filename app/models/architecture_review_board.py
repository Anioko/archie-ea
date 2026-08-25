"""
Architecture Review Board (ARB) Models

Implements TOGAF-aligned Architecture Review Board process for enterprise governance.
Integrates with ArchiMate 3.2 viewpoints and capability-based planning.

TOGAF ADM Phases Supported:
- Phase A: Architecture Vision
- Phase B: Business Architecture
- Phase C: Information Systems Architecture
- Phase D: Technology Architecture
- Phase E: Opportunities and Solutions
- Phase F: Migration Planning
- Phase G: Implementation Governance
- Phase H: Architecture Change Management

ArchiMate 3.2 Viewpoints for Review:
- Motivation Viewpoint
- Strategy Viewpoint
- Business Layer Viewpoints
- Application Layer Viewpoints
- Technology Layer Viewpoints
- Implementation & Migration Viewpoints
"""

import os
import uuid
from datetime import datetime, timedelta  # dead-code-ok
from enum import Enum
from typing import Any, Dict, List, Optional  # dead-code-ok

from sqlalchemy import event  # dead-code-ok
from sqlalchemy.ext.hybrid import hybrid_property  # dead-code-ok

from .. import db
from .mixins import OptimisticLockMixin, TenantMixin

_FAST_INIT = os.getenv("APP_FAST_INIT", "0") == "1"


class ARBReviewStatus(str, Enum):
    """Status of an ARB review."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    PENDING_INFO = "pending_information"
    APPROVED = "approved"
    APPROVED_WITH_CONDITIONS = "approved_with_conditions"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    WITHDRAWN = "withdrawn"


# These are the state groups used by operational ARB reporting.  Keeping them
# next to the canonical status vocabulary prevents each dashboard from quietly
# choosing a different meaning for "open".
ARB_OPEN_STATUSES = frozenset(
    {
        ARBReviewStatus.SUBMITTED.value,
        ARBReviewStatus.UNDER_REVIEW.value,
        ARBReviewStatus.PENDING_INFO.value,
        "pending_info",  # legacy spelling present in existing ARB records
        "pending",       # legacy queue spelling present in existing ARB records
    }
)
ARB_BLOCKED_OR_NOT_READY_STATUSES = frozenset(
    {
        ARBReviewStatus.PENDING_INFO.value,
        "pending_info",
        ARBReviewStatus.DEFERRED.value,
    }
)
ARB_DECIDED_STATUSES = frozenset(
    {
        ARBReviewStatus.APPROVED.value,
        ARBReviewStatus.APPROVED_WITH_CONDITIONS.value,
        ARBReviewStatus.REJECTED.value,
        ARBReviewStatus.DEFERRED.value,
    }
)
ARB_REVIEW_SLA_DAYS = 21


class TOGAFPhase(str, Enum):
    """TOGAF ADM Phases."""

    PRELIMINARY = "preliminary"
    PHASE_A = "phase_a_vision"
    PHASE_B = "phase_b_business"
    PHASE_C = "phase_c_information_systems"
    PHASE_D = "phase_d_technology"
    PHASE_E = "phase_e_opportunities"
    PHASE_F = "phase_f_migration"
    PHASE_G = "phase_g_implementation"
    PHASE_H = "phase_h_change_management"
    REQUIREMENTS_MANAGEMENT = "requirements_management"


class ARBExceptionStatus(str, Enum):
    """Status values for ARB exception requests."""

    REQUESTED = "requested"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    DENIED = "denied"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ReviewType(str, Enum):
    """Types of architecture reviews."""

    SOLUTION_DESIGN = "solution_design"
    ARCHITECTURE_CHANGE = "architecture_change"
    TECHNOLOGY_SELECTION = "technology_selection"
    CAPABILITY_IMPLEMENTATION = "capability_implementation"
    INTEGRATION_PATTERN = "integration_pattern"
    SECURITY_REVIEW = "security_review"
    COMPLIANCE_REVIEW = "compliance_review"
    EXCEPTION_REQUEST = "exception_request"
    STANDARD_DEVIATION = "standard_deviation"
    RETIREMENT_REVIEW = "retirement_review"


class ARBAuditAction(str, Enum):
    """Audit actions for ARB entities."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    STATUS_CHANGE = "status_change"
    DECISION = "decision"
    ASSIGNMENT = "assignment"
    SCORE_UPDATE = "score_update"
    COMMENT_ADD = "comment_add"
    EXCEPTION_REQUEST = "exception_request"
    EXCEPTION_DECISION = "exception_decision"
    READINESS_CHECK = "readiness_check"
    DECISION_REOPEN = "decision_reopen"


class ARBAuditLog(TenantMixin, db.Model):
    """Lightweight audit log model for ARB actions.

    This is a compact compatibility shim used by services that expect
    an ARBAuditLog model to exist. It intentionally contains only the
    fields required by the audit service.
    """

    __tablename__ = "arb_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    # Phase B (Wave 4): TenantMixin enabled — backfill completed in Phase A.
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    entity_reference = db.Column(db.String(255))
    action = db.Column(db.String(50), nullable=False)
    action_description = db.Column(db.Text)
    old_value = db.Column(db.JSON)
    new_value = db.Column(db.JSON)
    changed_fields = db.Column(db.JSON)
    user_id = db.Column(db.Integer)
    user_email = db.Column(db.String(255))
    ip_address = db.Column(db.String(100))
    user_agent = db.Column(db.String(500))
    request_id = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class ARBException(TenantMixin, db.Model):
    """Exception request model for architecture governance standards."""

    __tablename__ = "arb_exceptions"

    id = db.Column(db.Integer, primary_key=True)
    # Phase B (Wave 4): TenantMixin enabled — backfill completed in Phase A.
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)
    exception_number = db.Column(db.String(50), unique=True)
    standard_id = db.Column(db.Integer)
    exception_type = db.Column(db.String(100))
    status = db.Column(db.String(50))

    # Request tracking
    business_justification = db.Column(db.Text)
    risk_mitigation = db.Column(db.Text)
    scope = db.Column(db.Text)
    exception_reason = db.Column(db.Text)
    review_item_id = db.Column(db.Integer)

    # Requester
    requested_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    requested_at = db.Column(db.DateTime)

    # Review
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime)
    review_notes = db.Column(db.Text)

    # Approval
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_at = db.Column(db.DateTime)
    approval_notes = db.Column(db.Text)

    # Denial
    denied_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    denied_at = db.Column(db.DateTime)
    denial_reason = db.Column(db.Text)

    # Revocation
    revoked_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    revoked_at = db.Column(db.DateTime)
    revocation_reason = db.Column(db.Text)

    # Expiration and renewal
    expires_at = db.Column(db.DateTime)
    parent_exception_id = db.Column(db.Integer, db.ForeignKey("arb_exceptions.id"))
    renewal_count = db.Column(db.Integer, default=0)
    reminder_sent_at = db.Column(db.DateTime)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    requester = db.relationship(
        "User", foreign_keys=[requested_by_id], backref="requested_exceptions"
    )
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id], backref="reviewed_exceptions")
    approver = db.relationship("User", foreign_keys=[approved_by_id], backref="approved_exceptions")
    denier = db.relationship("User", foreign_keys=[denied_by_id], backref="denied_exceptions")
    parent = db.relationship("ARBException", remote_side=[id], backref="renewals")


# Default workflow stages and lightweight ARBWorkflowStage model
DEFAULT_WORKFLOW_STAGES = [
    {"code": "draft", "name": "Draft", "order": 1},
    {"code": "submitted", "name": "Submitted", "order": 2},
    {"code": "under_review", "name": "Under Review", "order": 3},
    {"code": "approved", "name": "Approved", "order": 4},
    {"code": "rejected", "name": "Rejected", "order": 5},
]


# Global reference data (shared across tenants) — intentionally NOT TenantMixin; org column unused. See wave-4 Task-2 review.
class ARBWorkflowStage(db.Model):
    """Lightweight workflow stage model for ARB processes."""

    __tablename__ = "arb_workflow_stages"

    id = db.Column(db.Integer, primary_key=True)
    # Global reference data (shared across tenants) — intentionally NOT TenantMixin; org column unused. See wave-4 Task-2 review.
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {"id": self.id, "code": self.code, "name": self.name, "order": self.order}

    def can_transition_to(self, target_stage: "ARBWorkflowStage") -> bool:
        """Return whether this stage can transition to the target stage."""
        if not target_stage:
            return False
        if not self.is_active or not target_stage.is_active:
            return False
        if self.code == target_stage.code:
            return True
        # Default fallback for legacy rows: forward-only transitions by order.
        return (target_stage.order or 0) > (self.order or 0)

    def evaluate_gate_conditions(self, review_item: Any) -> Dict[str, Any]:
        """
        Evaluate gate conditions for a transition into this stage.

        This model currently does not persist explicit gate rules, so we return
        a permissive, structured result to keep the workflow engine stable.
        """
        return {"passed": True, "checks": [], "blocking_issues": []}


def create_default_workflow_stages():
    """Return default workflow stage definitions (non-DB representations)."""
    return [dict(s) for s in DEFAULT_WORKFLOW_STAGES]


class ArchitectureReviewBoard(TenantMixin, db.Model, OptimisticLockMixin):
    """
    Architecture Review Board session model.

    Represents an ARB meeting/session where multiple review items are discussed.
    """

    __tablename__ = "architecture_review_boards"

    id = db.Column(db.Integer, primary_key=True)
    board_number = db.Column(db.String(50), unique=True, nullable=False)  # ARB - 2026 - 001
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)

    # Scheduling
    scheduled_date = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=120)
    location = db.Column(db.String(255))  # Physical location or meeting link
    meeting_link = db.Column(db.String(500))  # Video conference URL

    # Board composition
    chair_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    secretary_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Status
    status = db.Column(
        db.String(30), default="scheduled"
    )  # scheduled, in_progress, completed, cancelled

    # Agenda and minutes
    agenda = db.Column(db.JSON)  # Structured agenda with items
    minutes = db.Column(db.Text)
    decisions_summary = db.Column(db.JSON)  # Summary of all decisions made

    # ArchiMate element linkage
    impacted_element_ids = db.Column(db.JSON, default=list)

    # Governance metrics
    items_reviewed = db.Column(db.Integer, default=0)
    items_approved = db.Column(db.Integer, default=0)
    items_rejected = db.Column(db.Integer, default=0)
    items_deferred = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    # Relationships
    chair = db.relationship("User", foreign_keys=[chair_id], backref="chaired_arb_sessions")
    secretary = db.relationship(
        "User", foreign_keys=[secretary_id], backref="arb_secretary_sessions"
    )
    review_items = db.relationship(
        "ARBReviewItem", back_populates="arb_session", cascade="all, delete-orphan"
    )
    board_members = db.relationship(
        "ARBBoardMember", back_populates="arb_session", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ARB {self.board_number}: {self.name}>"

    @staticmethod
    def generate_board_number():
        """Generate next ARB session number."""
        year = datetime.utcnow().year
        last_arb = (
            ArchitectureReviewBoard.query.filter(
                ArchitectureReviewBoard.board_number.like(f"ARB-{year}-%")
            )
            .order_by(ArchitectureReviewBoard.id.desc())
            .first()
        )

        if last_arb:
            try:
                last_num = int(last_arb.board_number.split("-")[-1])
                next_num = last_num + 1
            except ValueError:
                next_num = 1
        else:
            next_num = 1

        return f"ARB-{year}-{next_num:03d}"

    def to_dict(self):
        return {
            "id": self.id,
            "board_number": self.board_number,
            "name": self.name,
            "description": self.description,
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
            "duration_minutes": self.duration_minutes,
            "location": self.location,
            "meeting_link": self.meeting_link,
            "status": self.status,
            "items_reviewed": self.items_reviewed,
            "items_approved": self.items_approved,
            "items_rejected": self.items_rejected,
            "items_deferred": self.items_deferred,
            "chair": {
                "id": self.chair.id,
                "name": f"{self.chair.first_name} {self.chair.last_name}",
            }
            if self.chair
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ARBBoardMember(TenantMixin, db.Model):
    """Board members for an ARB session."""

    __tablename__ = "arb_board_members"

    id = db.Column(db.Integer, primary_key=True)
    # Phase B (Wave 4): TenantMixin enabled — backfill completed in Phase A.
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)
    arb_session_id = db.Column(
        db.Integer, db.ForeignKey("architecture_review_boards.id"), nullable=False
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Role on the board
    role = db.Column(
        db.String(50), nullable=False
    )  # enterprise_architect, solution_architect, business_architect, data_architect, security_architect, integration_architect
    voting_member = db.Column(db.Boolean, default=True)

    # Attendance
    attendance_status = db.Column(
        db.String(30), default="pending"
    )  # pending, confirmed, declined, attended, absent
    attendance_notes = db.Column(db.Text)

    # Relationships
    arb_session = db.relationship("ArchitectureReviewBoard", back_populates="board_members")
    user = db.relationship("User", backref="arb_memberships")

    __table_args__ = (db.UniqueConstraint("arb_session_id", "user_id", name="uix_arb_member"),)


_ARB_REVIEW_CYCLE_SHAPE = (
    "subject_type IS NOT NULL AND subject_id IS NOT NULL "
    "AND review_number IS NOT NULL AND cycle_number IS NOT NULL "
    "AND cycle_number > 0 AND status IS NOT NULL AND opened_at IS NOT NULL "
    "AND ((cycle_number = 1 AND predecessor_cycle_id IS NULL) "
    "OR (cycle_number > 1 AND predecessor_cycle_id IS NOT NULL)) "
    "AND ((status = 'historical_unverified' "
    "AND migration_gap_reason IS NOT NULL AND legacy_source_type IS NOT NULL "
    "AND legacy_source_id IS NOT NULL AND closed_at IS NOT NULL "
    "AND terminal_outcome IS NOT NULL "
    "AND decision_brief_version_id IS NULL "
    "AND solution_evidence_snapshot_id IS NULL "
    "AND subject_evidence_snapshot_id IS NULL "
    "AND ((subject_type = 'solution' AND subject_id = solution_id "
    "AND solution_id IS NOT NULL AND decision_brief_id IS NULL "
    "AND architecture_model_id IS NULL AND adr_id IS NULL) "
    "OR (subject_type = 'architecture_model' "
    "AND subject_id = architecture_model_id "
    "AND architecture_model_id IS NOT NULL AND decision_brief_id IS NULL "
    "AND solution_id IS NULL AND adr_id IS NULL) "
    "OR (subject_type = 'adr' AND subject_id = adr_id AND adr_id IS NOT NULL "
    "AND decision_brief_id IS NULL AND solution_id IS NULL "
    "AND architecture_model_id IS NULL))) "
    "OR (status <> 'historical_unverified' "
    "AND migration_gap_reason IS NULL AND legacy_source_type IS NULL "
    "AND legacy_source_id IS NULL "
    "AND ((subject_type = 'decision_brief' "
    "AND subject_id = decision_brief_id AND decision_brief_id IS NOT NULL "
    "AND solution_id IS NULL AND architecture_model_id IS NULL AND adr_id IS NULL "
    "AND decision_brief_version_id IS NOT NULL "
    "AND solution_evidence_snapshot_id IS NULL "
    "AND subject_evidence_snapshot_id IS NULL) "
    "OR (subject_type = 'solution' AND subject_id = solution_id "
    "AND solution_id IS NOT NULL AND decision_brief_id IS NULL "
    "AND architecture_model_id IS NULL AND adr_id IS NULL "
    "AND decision_brief_version_id IS NULL "
    "AND solution_evidence_snapshot_id IS NOT NULL "
    "AND subject_evidence_snapshot_id IS NULL) "
    "OR (subject_type = 'architecture_model' "
    "AND subject_id = architecture_model_id "
    "AND architecture_model_id IS NOT NULL AND decision_brief_id IS NULL "
    "AND solution_id IS NULL AND adr_id IS NULL "
    "AND decision_brief_version_id IS NULL "
    "AND solution_evidence_snapshot_id IS NULL "
    "AND subject_evidence_snapshot_id IS NOT NULL) "
    "OR (subject_type = 'adr' AND subject_id = adr_id AND adr_id IS NOT NULL "
    "AND decision_brief_id IS NULL AND solution_id IS NULL "
    "AND architecture_model_id IS NULL AND decision_brief_version_id IS NULL "
    "AND solution_evidence_snapshot_id IS NULL "
    "AND subject_evidence_snapshot_id IS NOT NULL)))) "
    "AND ((closed_at IS NULL AND terminal_outcome IS NULL) "
    "OR (closed_at IS NOT NULL AND terminal_outcome IS NOT NULL))"
)


class ARBReviewCycle(TenantMixin, db.Model):
    """Immutable subject/evidence identity around the sole ARB review item."""

    __tablename__ = "arb_review_cycles"

    id = db.Column(db.Integer, primary_key=True)
    subject_type = db.Column(db.String(40), nullable=True, index=True)
    subject_id = db.Column(db.Integer, nullable=True, index=True)
    decision_brief_id = db.Column(
        db.Integer,
        db.ForeignKey("decision_briefs.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    solution_id = db.Column(
        db.Integer,
        db.ForeignKey("solutions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    architecture_model_id = db.Column(
        db.Integer,
        db.ForeignKey("architecture_models.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    adr_id = db.Column(
        db.Integer,
        db.ForeignKey("architecture_decision_records.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    decision_brief_version_id = db.Column(
        db.Integer,
        db.ForeignKey("decision_brief_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    solution_evidence_snapshot_id = db.Column(
        db.Integer,
        db.ForeignKey("arb_submission_evidence_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
    )
    subject_evidence_snapshot_id = db.Column(
        db.Integer,
        db.ForeignKey("arb_subject_evidence_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
    )
    review_number = db.Column(db.String(50), nullable=True)
    cycle_number = db.Column(db.Integer, nullable=True)
    predecessor_cycle_id = db.Column(
        db.Integer,
        db.ForeignKey("arb_review_cycles.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status = db.Column(db.String(40), nullable=True)
    migration_gap_reason = db.Column(db.Text, nullable=True)
    legacy_source_type = db.Column(db.String(80), nullable=True)
    legacy_source_id = db.Column(db.Integer, nullable=True)
    opened_at = db.Column(
        db.DateTime(timezone=True), nullable=True, server_default=db.func.now()
    )
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    terminal_outcome = db.Column(db.String(80), nullable=True)

    __table_args__ = (
        db.CheckConstraint(_ARB_REVIEW_CYCLE_SHAPE, name="ck_arb_review_cycle_shape"),
        db.UniqueConstraint(
            "organization_id",
            "subject_type",
            "subject_id",
            "cycle_number",
            name="uq_arb_review_cycle_number",
        ),
        db.UniqueConstraint(
            "organization_id",
            "review_number",
            name="uq_arb_review_cycle_review_number",
        ),
        db.UniqueConstraint(
            "predecessor_cycle_id",
            name="uq_arb_review_cycle_predecessor",
        ),
        db.Index(
            "uq_arb_review_cycle_open_subject",
            "organization_id",
            "subject_type",
            "subject_id",
            unique=True,
            postgresql_where=db.text("closed_at IS NULL"),
        ),
    )


_ARB_TYPED_REVIEW_SHAPE = (
    "(review_cycle_id IS NULL AND subject_type IS NULL AND subject_id IS NULL "
    "AND decision_brief_id IS NULL AND decision_brief_version_id IS NULL "
    "AND solution_evidence_snapshot_id IS NULL "
    "AND subject_evidence_snapshot_id IS NULL) "
    "OR (review_cycle_id IS NOT NULL AND status = 'historical_unverified' "
    "AND subject_type IS NOT NULL AND subject_id IS NOT NULL "
    "AND decision_brief_id IS NULL AND decision_brief_version_id IS NULL "
    "AND solution_evidence_snapshot_id IS NULL "
    "AND subject_evidence_snapshot_id IS NULL "
    "AND ((subject_type = 'solution' AND subject_id = solution_id "
    "AND solution_id IS NOT NULL AND architecture_model_id IS NULL "
    "AND adr_id IS NULL) "
    "OR (subject_type = 'architecture_model' "
    "AND subject_id = architecture_model_id AND solution_id IS NULL "
    "AND architecture_model_id IS NOT NULL AND adr_id IS NULL) "
    "OR (subject_type = 'adr' AND subject_id = adr_id AND solution_id IS NULL "
    "AND architecture_model_id IS NULL AND adr_id IS NOT NULL))) "
    "OR (review_cycle_id IS NOT NULL AND status <> 'historical_unverified' "
    "AND subject_type IS NOT NULL "
    "AND subject_id IS NOT NULL AND ((subject_type = 'decision_brief' "
    "AND subject_id = decision_brief_id AND decision_brief_id IS NOT NULL "
    "AND solution_id IS NULL AND architecture_model_id IS NULL AND adr_id IS NULL "
    "AND decision_brief_version_id IS NOT NULL "
    "AND solution_evidence_snapshot_id IS NULL "
    "AND subject_evidence_snapshot_id IS NULL) "
    "OR (subject_type = 'solution' AND subject_id = solution_id "
    "AND solution_id IS NOT NULL AND decision_brief_id IS NULL "
    "AND architecture_model_id IS NULL AND adr_id IS NULL "
    "AND decision_brief_version_id IS NULL "
    "AND solution_evidence_snapshot_id IS NOT NULL "
    "AND subject_evidence_snapshot_id IS NULL) "
    "OR (subject_type = 'architecture_model' "
    "AND subject_id = architecture_model_id "
    "AND architecture_model_id IS NOT NULL AND decision_brief_id IS NULL "
    "AND solution_id IS NULL AND adr_id IS NULL "
    "AND decision_brief_version_id IS NULL "
    "AND solution_evidence_snapshot_id IS NULL "
    "AND subject_evidence_snapshot_id IS NOT NULL) "
    "OR (subject_type = 'adr' AND subject_id = adr_id AND adr_id IS NOT NULL "
    "AND decision_brief_id IS NULL AND solution_id IS NULL "
    "AND architecture_model_id IS NULL AND decision_brief_version_id IS NULL "
    "AND solution_evidence_snapshot_id IS NULL "
    "AND subject_evidence_snapshot_id IS NOT NULL)))"
)


class ARBReviewItem(TenantMixin, db.Model, OptimisticLockMixin):
    """
    Individual item submitted for ARB review.

    Links solutions, capabilities, and ADRs to the review process.
    """

    __tablename__ = "arb_review_items"

    id = db.Column(db.Integer, primary_key=True)
    # Phase B (Wave 4): TenantMixin enabled — backfill completed in Phase A.
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)
    review_number = db.Column(db.String(50), unique=True, nullable=False)  # REV - 2026 - 001
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)

    # Review classification
    review_type = db.Column(db.String(50), nullable=False)  # From ReviewType enum
    togaf_phase = db.Column(db.String(50))  # From TOGAFPhase enum
    archimate_layer = db.Column(
        db.String(30)
    )  # motivation, strategy, business, application, technology, implementation

    # Priority and urgency
    priority = db.Column(db.String(20), default="medium")  # critical, high, medium, low
    business_impact = db.Column(db.String(20))  # critical, high, medium, low
    estimated_effort = db.Column(db.String(20))  # small, medium, large, xl

    # Linkages to existing entities
    solution_id = db.Column(db.Integer, db.ForeignKey("solutions.id"))
    architecture_model_id = db.Column(db.Integer, db.ForeignKey("architecture_models.id"))
    adr_id = db.Column(db.Integer, db.ForeignKey("architecture_decision_records.id"))
    subject_type = db.Column(db.String(40), nullable=True, index=True)
    subject_id = db.Column(db.Integer, nullable=True, index=True)
    decision_brief_id = db.Column(
        db.Integer,
        db.ForeignKey("decision_briefs.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    decision_brief_version_id = db.Column(
        db.Integer,
        db.ForeignKey("decision_brief_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    solution_evidence_snapshot_id = db.Column(
        db.Integer,
        db.ForeignKey("arb_submission_evidence_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
    )
    subject_evidence_snapshot_id = db.Column(
        db.Integer,
        db.ForeignKey("arb_subject_evidence_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
    )
    review_cycle_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "arb_review_cycles.id",
            ondelete="RESTRICT",
            use_alter=True,
            name="fk_arb_review_item_cycle",
        ),
        nullable=True,
        unique=True,
    )

    # Status and workflow
    status = db.Column(db.String(30), default="draft")  # From ARBReviewStatus enum
    arb_session_id = db.Column(db.Integer, db.ForeignKey("architecture_review_boards.id", ondelete="CASCADE"))

    # Submission details
    submitter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    submitted_at = db.Column(db.DateTime)

    # Review details
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    review_started_at = db.Column(db.DateTime)
    review_completed_at = db.Column(db.DateTime)

    # Decision
    decision = db.Column(db.String(50))  # approved, approved_with_conditions, rejected, deferred
    decision_rationale = db.Column(db.Text)
    conditions = db.Column(db.JSON)  # Conditions for approval
    decision_date = db.Column(db.DateTime)
    decided_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Review checklist and scoring
    governance_checklist = db.Column(db.JSON)  # Checklist items and completion status
    compliance_score = db.Column(db.Float)  # 0 - 100
    risk_score = db.Column(db.Float)  # 0 - 100
    quality_score = db.Column(db.Float)  # 0 - 100
    overall_score = db.Column(db.Float)  # Weighted average

    # Capability impact analysis
    capability_impacts = db.Column(db.JSON)  # List of impacted capabilities with analysis

    # ArchiMate viewpoint analysis
    archimate_viewpoints = db.Column(db.JSON)  # Relevant viewpoints and assessments

    # Supporting documents
    attachments = db.Column(db.JSON)  # List of attached documents

    # ENH-020: Implementation status tracking
    implementation_status = db.Column(
        db.String(30), default="not_started"
    )  # not_started, in_progress, completed, blocked, deferred
    implementation_notes = db.Column(db.Text)
    implementation_started_at = db.Column(db.DateTime)
    implementation_completed_at = db.Column(db.DateTime)
    conditions_response = db.Column(db.JSON)  # Response to conditions_required

    # COM-009: Jira integration
    jira_issue_key = db.Column(db.String(50), nullable=True)  # e.g. ARCH-42

    # Follow-up tracking
    follow_up_required = db.Column(db.Boolean, default=False)
    follow_up_date = db.Column(db.Date)
    follow_up_notes = db.Column(db.Text)

    # External integrations
    servicenow_change_id = db.Column(db.String(100), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    arb_session = db.relationship("ArchitectureReviewBoard", back_populates="review_items")
    solution = db.relationship("Solution", foreign_keys=[solution_id], backref="arb_reviews")
    architecture_model = db.relationship("ArchitectureModel", backref="arb_reviews")
    adr = db.relationship("ArchitectureDecisionRecord", backref="arb_reviews")
    submitter = db.relationship("User", foreign_keys=[submitter_id], backref="submitted_arb_items")
    reviewer = db.relationship("User", foreign_keys=[reviewer_id], backref="reviewed_arb_items")
    decided_by = db.relationship("User", foreign_keys=[decided_by_id], backref="arb_decisions")
    review_cycle = db.relationship(
        "ARBReviewCycle",
        foreign_keys=[review_cycle_id],
        backref=db.backref("review_item", uselist=False),
    )
    comments = db.relationship(
        "ARBReviewComment", back_populates="review_item", cascade="all, delete-orphan"
    )
    capability_links = db.relationship(
        "ARBCapabilityImpact", back_populates="review_item", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.CheckConstraint(_ARB_TYPED_REVIEW_SHAPE, name="ck_arb_review_item_typed_shape"),
    )

    def __repr__(self):
        return f"<ARBReviewItem {self.review_number}: {self.title}>"

    @staticmethod
    def generate_review_number():
        """Generate a globally unique, non-enumerable review number.

        ``ARBReviewItem`` is tenant-scoped but ``review_number`` has a global
        unique constraint. A sequential "last row + 1" query is filtered to
        the current tenant and is also race-prone, so two organizations (or
        concurrent submissions) can select the same number. Match the
        canonical evidence-gated submission format instead.
        """
        return f"REV-{datetime.utcnow():%Y}-{uuid.uuid4().hex[:12].upper()}"

    def calculate_overall_score(self):
        """Calculate weighted overall score."""
        weights = {"compliance": 0.35, "risk": 0.30, "quality": 0.35}

        scores = []
        if self.compliance_score is not None:
            scores.append(self.compliance_score * weights["compliance"])
        if self.risk_score is not None:
            # Risk is inverted - lower risk = higher score
            scores.append((100 - self.risk_score) * weights["risk"])
        if self.quality_score is not None:
            scores.append(self.quality_score * weights["quality"])

        if scores:
            total_weight = sum(
                weights[k]
                for k in ["compliance", "risk", "quality"]
                if getattr(self, f"{k}_score") is not None
            )
            self.overall_score = sum(scores) / total_weight if total_weight > 0 else 0

        return self.overall_score

    def to_dict(self, include_details=True):
        base_dict = {
            "id": self.id,
            "review_number": self.review_number,
            "title": self.title,
            "review_type": self.review_type,
            "togaf_phase": self.togaf_phase,
            "archimate_layer": self.archimate_layer,
            "priority": self.priority,
            "status": self.status,
            "decision": self.decision,
            "overall_score": self.overall_score,
            "submitter": {
                "id": self.submitter.id,
                "name": f"{self.submitter.first_name} {self.submitter.last_name}",
            }
            if self.submitter
            else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

        if include_details:
            base_dict.update(
                {
                    "description": self.description,
                    "business_impact": self.business_impact,
                    "estimated_effort": self.estimated_effort,
                    "solution_id": self.solution_id,
                    "adr_id": self.adr_id,
                    "decision_rationale": self.decision_rationale,
                    "conditions": self.conditions,
                    "governance_checklist": self.governance_checklist,
                    "compliance_score": self.compliance_score,
                    "risk_score": self.risk_score,
                    "quality_score": self.quality_score,
                    "capability_impacts": self.capability_impacts,
                    "archimate_viewpoints": self.archimate_viewpoints,
                    "follow_up_required": self.follow_up_required,
                    "follow_up_date": self.follow_up_date.isoformat()
                    if self.follow_up_date
                    else None,
                    "implementation_status": self.implementation_status,
                    "implementation_notes": self.implementation_notes,
                    "implementation_started_at": self.implementation_started_at.isoformat()
                    if self.implementation_started_at
                    else None,
                    "implementation_completed_at": self.implementation_completed_at.isoformat()
                    if self.implementation_completed_at
                    else None,
                    "conditions_response": self.conditions_response,
                }
            )

        return base_dict


def _arb_membership_function_sql(quoted_schema):
    return f"""
    CREATE OR REPLACE FUNCTION {quoted_schema}.archie_validate_arb_cycle_membership()
    RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, {quoted_schema}
    AS $$
    DECLARE
        matching_review_id integer;
    BEGIN
        IF TG_TABLE_NAME = 'arb_subject_evidence_snapshots' THEN
            IF NEW.subject_type = 'architecture_model' AND NOT EXISTS (
                SELECT 1 FROM architecture_models model
                WHERE model.id = NEW.architecture_model_id
                  AND model.organization_id = NEW.organization_id
            ) THEN
                RAISE EXCEPTION 'ARB snapshot subject is outside its tenant'
                    USING ERRCODE = '23514';
            ELSIF NEW.subject_type = 'adr' AND NOT EXISTS (
                SELECT 1 FROM architecture_decision_records adr
                WHERE adr.id = NEW.adr_id
                  AND adr.organization_id = NEW.organization_id
            ) THEN
                RAISE EXCEPTION 'ARB snapshot subject is outside its tenant'
                    USING ERRCODE = '23514';
            END IF;

        ELSIF TG_TABLE_NAME = 'arb_review_cycles' THEN
            IF NEW.subject_type = 'decision_brief' THEN
                IF NOT EXISTS (
                    SELECT 1 FROM decision_briefs brief
                    WHERE brief.id = NEW.decision_brief_id
                      AND brief.organization_id = NEW.organization_id
                ) THEN
                    RAISE EXCEPTION 'ARB cycle subject is outside its tenant'
                        USING ERRCODE = '23514';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM decision_brief_versions version
                    WHERE version.id = NEW.decision_brief_version_id
                      AND version.brief_id = NEW.decision_brief_id
                      AND version.organization_id = NEW.organization_id
                ) THEN
                    RAISE EXCEPTION 'ARB cycle version does not belong to its brief and tenant'
                        USING ERRCODE = '23514';
                END IF;
            ELSIF NEW.subject_type = 'solution' THEN
                IF NOT EXISTS (
                    SELECT 1 FROM solutions solution
                    WHERE solution.id = NEW.solution_id
                      AND solution.organization_id = NEW.organization_id
                ) THEN
                    RAISE EXCEPTION 'ARB cycle subject is outside its tenant'
                        USING ERRCODE = '23514';
                END IF;
                IF NEW.status <> 'historical_unverified' AND NOT EXISTS (
                    SELECT 1 FROM arb_submission_evidence_snapshots snapshot
                    WHERE snapshot.id = NEW.solution_evidence_snapshot_id
                      AND snapshot.solution_id = NEW.solution_id
                      AND snapshot.organization_id = NEW.organization_id
                ) THEN
                    RAISE EXCEPTION 'ARB cycle snapshot does not belong to its subject and tenant'
                        USING ERRCODE = '23514';
                END IF;
            ELSIF NEW.subject_type = 'architecture_model' THEN
                IF NOT EXISTS (
                    SELECT 1 FROM architecture_models model
                    WHERE model.id = NEW.architecture_model_id
                      AND model.organization_id = NEW.organization_id
                ) THEN
                    RAISE EXCEPTION 'ARB cycle subject is outside its tenant'
                        USING ERRCODE = '23514';
                END IF;
                IF NEW.status <> 'historical_unverified' AND NOT EXISTS (
                    SELECT 1 FROM arb_subject_evidence_snapshots snapshot
                    WHERE snapshot.id = NEW.subject_evidence_snapshot_id
                      AND snapshot.subject_type = NEW.subject_type
                      AND snapshot.subject_id = NEW.subject_id
                      AND snapshot.architecture_model_id = NEW.architecture_model_id
                      AND snapshot.organization_id = NEW.organization_id
                ) THEN
                    RAISE EXCEPTION 'ARB cycle snapshot does not belong to its subject and tenant'
                        USING ERRCODE = '23514';
                END IF;
            ELSIF NEW.subject_type = 'adr' THEN
                IF NOT EXISTS (
                    SELECT 1 FROM architecture_decision_records adr
                    WHERE adr.id = NEW.adr_id
                      AND adr.organization_id = NEW.organization_id
                ) THEN
                    RAISE EXCEPTION 'ARB cycle subject is outside its tenant'
                        USING ERRCODE = '23514';
                END IF;
                IF NEW.status <> 'historical_unverified' AND NOT EXISTS (
                    SELECT 1 FROM arb_subject_evidence_snapshots snapshot
                    WHERE snapshot.id = NEW.subject_evidence_snapshot_id
                      AND snapshot.subject_type = NEW.subject_type
                      AND snapshot.subject_id = NEW.subject_id
                      AND snapshot.adr_id = NEW.adr_id
                      AND snapshot.organization_id = NEW.organization_id
                ) THEN
                    RAISE EXCEPTION 'ARB cycle snapshot does not belong to its subject and tenant'
                        USING ERRCODE = '23514';
                END IF;
            END IF;

            IF NEW.predecessor_cycle_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM arb_review_cycles predecessor
                WHERE predecessor.id = NEW.predecessor_cycle_id
                  AND predecessor.organization_id = NEW.organization_id
                  AND predecessor.subject_type = NEW.subject_type
                  AND predecessor.subject_id = NEW.subject_id
                  AND predecessor.cycle_number = NEW.cycle_number - 1
                  AND predecessor.closed_at IS NOT NULL
                  AND predecessor.closed_at <= NEW.opened_at
            ) THEN
                RAISE EXCEPTION 'ARB cycle predecessor is not monotonic for its typed subject'
                    USING ERRCODE = '23514';
            END IF;

            SELECT review.id INTO matching_review_id
            FROM arb_review_items review
            WHERE review.review_cycle_id = NEW.id
              AND review.organization_id = NEW.organization_id
              AND review.status = NEW.status
              AND review.subject_type = NEW.subject_type
              AND review.subject_id = NEW.subject_id
              AND review.decision_brief_id IS NOT DISTINCT FROM NEW.decision_brief_id
              AND review.solution_id IS NOT DISTINCT FROM NEW.solution_id
              AND review.architecture_model_id IS NOT DISTINCT FROM NEW.architecture_model_id
              AND review.adr_id IS NOT DISTINCT FROM NEW.adr_id
              AND review.decision_brief_version_id IS NOT DISTINCT FROM NEW.decision_brief_version_id
              AND review.solution_evidence_snapshot_id IS NOT DISTINCT FROM NEW.solution_evidence_snapshot_id
              AND review.subject_evidence_snapshot_id IS NOT DISTINCT FROM NEW.subject_evidence_snapshot_id;
            IF matching_review_id IS NULL THEN
                RAISE EXCEPTION 'ARB cycle review projection is missing or disagrees'
                    USING ERRCODE = '23514';
            END IF;
            IF NEW.subject_type = 'solution'
               AND NEW.status <> 'historical_unverified'
               AND NOT EXISTS (
                   SELECT 1 FROM arb_submission_evidence_snapshots snapshot
                   WHERE snapshot.id = NEW.solution_evidence_snapshot_id
                     AND snapshot.review_item_id = matching_review_id
               ) THEN
                RAISE EXCEPTION 'ARB Solution snapshot does not belong to its review'
                    USING ERRCODE = '23514';
            END IF;

        ELSIF TG_TABLE_NAME = 'arb_review_items' AND NEW.review_cycle_id IS NOT NULL THEN
            IF NOT EXISTS (
                SELECT 1 FROM arb_review_cycles cycle
                WHERE cycle.id = NEW.review_cycle_id
                  AND cycle.organization_id = NEW.organization_id
                  AND cycle.status = NEW.status
                  AND cycle.subject_type = NEW.subject_type
                  AND cycle.subject_id = NEW.subject_id
                  AND cycle.decision_brief_id IS NOT DISTINCT FROM NEW.decision_brief_id
                  AND cycle.solution_id IS NOT DISTINCT FROM NEW.solution_id
                  AND cycle.architecture_model_id IS NOT DISTINCT FROM NEW.architecture_model_id
                  AND cycle.adr_id IS NOT DISTINCT FROM NEW.adr_id
                  AND cycle.decision_brief_version_id IS NOT DISTINCT FROM NEW.decision_brief_version_id
                  AND cycle.solution_evidence_snapshot_id IS NOT DISTINCT FROM NEW.solution_evidence_snapshot_id
                  AND cycle.subject_evidence_snapshot_id IS NOT DISTINCT FROM NEW.subject_evidence_snapshot_id
            ) THEN
                RAISE EXCEPTION 'ARB review projection disagrees with its cycle'
                    USING ERRCODE = '23514';
            END IF;
            IF NEW.subject_type = 'solution'
               AND NEW.solution_evidence_snapshot_id IS NOT NULL
               AND NOT EXISTS (
                SELECT 1 FROM arb_submission_evidence_snapshots snapshot
                WHERE snapshot.id = NEW.solution_evidence_snapshot_id
                  AND snapshot.review_item_id = NEW.id
                  AND snapshot.organization_id = NEW.organization_id
                  AND snapshot.solution_id = NEW.solution_id
            ) THEN
                RAISE EXCEPTION 'ARB Solution snapshot does not belong to its review'
                    USING ERRCODE = '23514';
            END IF;
        END IF;
        RETURN NEW;
    END;
    $$
    """


def _arb_history_function_sql(quoted_schema):
    return f"""
    CREATE OR REPLACE FUNCTION {quoted_schema}.archie_guard_arb_cycle_history()
    RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, {quoted_schema}
    AS $$
    BEGIN
        IF TG_TABLE_NAME = 'arb_review_cycles' THEN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'ARB review cycle history is append-only'
                    USING ERRCODE = '55000';
            END IF;
            IF ROW(
                OLD.organization_id, OLD.subject_type, OLD.subject_id,
                OLD.decision_brief_id, OLD.solution_id, OLD.architecture_model_id,
                OLD.adr_id, OLD.decision_brief_version_id,
                OLD.solution_evidence_snapshot_id, OLD.subject_evidence_snapshot_id,
                OLD.review_number, OLD.cycle_number, OLD.predecessor_cycle_id,
                OLD.migration_gap_reason, OLD.legacy_source_type,
                OLD.legacy_source_id, OLD.opened_at
            ) IS DISTINCT FROM ROW(
                NEW.organization_id, NEW.subject_type, NEW.subject_id,
                NEW.decision_brief_id, NEW.solution_id, NEW.architecture_model_id,
                NEW.adr_id, NEW.decision_brief_version_id,
                NEW.solution_evidence_snapshot_id, NEW.subject_evidence_snapshot_id,
                NEW.review_number, NEW.cycle_number, NEW.predecessor_cycle_id,
                NEW.migration_gap_reason, NEW.legacy_source_type,
                NEW.legacy_source_id, NEW.opened_at
            ) THEN
                RAISE EXCEPTION 'ARB review cycle identity and evidence are immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF OLD.closed_at IS NOT NULL AND ROW(
                OLD.status, OLD.closed_at, OLD.terminal_outcome
            ) IS DISTINCT FROM ROW(
                NEW.status, NEW.closed_at, NEW.terminal_outcome
            ) THEN
                RAISE EXCEPTION 'closed ARB review cycle history is immutable'
                    USING ERRCODE = '55000';
            END IF;
        ELSIF TG_TABLE_NAME = 'arb_review_items' THEN
            IF TG_OP = 'DELETE' AND OLD.review_cycle_id IS NOT NULL THEN
                RAISE EXCEPTION 'typed ARB review history is append-only'
                    USING ERRCODE = '55000';
            END IF;
            IF TG_OP = 'UPDATE' AND OLD.review_cycle_id IS NOT NULL AND ROW(
                OLD.organization_id, OLD.subject_type, OLD.subject_id,
                OLD.decision_brief_id, OLD.solution_id, OLD.architecture_model_id,
                OLD.adr_id, OLD.decision_brief_version_id,
                OLD.solution_evidence_snapshot_id, OLD.subject_evidence_snapshot_id,
                OLD.review_cycle_id
            ) IS DISTINCT FROM ROW(
                NEW.organization_id, NEW.subject_type, NEW.subject_id,
                NEW.decision_brief_id, NEW.solution_id, NEW.architecture_model_id,
                NEW.adr_id, NEW.decision_brief_version_id,
                NEW.solution_evidence_snapshot_id, NEW.subject_evidence_snapshot_id,
                NEW.review_cycle_id
            ) THEN
                RAISE EXCEPTION 'typed ARB review projection is immutable'
                    USING ERRCODE = '55000';
            END IF;
        END IF;
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END;
    $$
    """


_ARB_REQUIRED_TRIGGERS = {
    "arb_subject_evidence_snapshots": ("trg_arb_subject_snapshot_membership",),
    "arb_review_cycles": (
        "trg_arb_cycle_membership",
        "trg_arb_cycle_history",
    ),
    "arb_review_items": (
        "trg_arb_review_cycle_membership",
        "trg_arb_review_cycle_history",
    ),
}


def _arb_catalog_state(connection):
    from sqlalchemy import text

    rows = connection.execute(
        text(
            """
            SELECT cls.relname, trigger.tgname, trigger.tgenabled
            FROM pg_trigger trigger
            JOIN pg_class cls ON cls.oid = trigger.tgrelid
            JOIN pg_namespace namespace ON namespace.oid = cls.relnamespace
            WHERE namespace.nspname = current_schema()
              AND NOT trigger.tgisinternal
              AND cls.relname IN (
                  'arb_subject_evidence_snapshots',
                  'arb_review_cycles',
                  'arb_review_items'
              )
            """
        )
    ).all()
    return {(row.relname, row.tgname): row.tgenabled for row in rows}


def inspect_arb_cycle_constraints(connection):
    """Return actionable drift for typed ARB checks, indexes and triggers."""
    if connection.dialect.name != "postgresql":
        return ["unsupported_dialect"]
    from sqlalchemy import text

    schema_name = connection.scalar(text("SELECT current_schema()"))
    tables = set(
        connection.scalars(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname = :schema_name"
            ),
            {"schema_name": schema_name},
        )
    )
    required_tables = set(_ARB_REQUIRED_TRIGGERS)
    drift = [f"table_missing:{table}" for table in sorted(required_tables - tables)]
    if drift:
        return drift

    constraints = set(
        connection.scalars(
            text(
                """
                SELECT constraint_row.conname
                FROM pg_constraint constraint_row
                JOIN pg_class cls ON cls.oid = constraint_row.conrelid
                JOIN pg_namespace namespace ON namespace.oid = cls.relnamespace
                WHERE namespace.nspname = :schema_name
                  AND constraint_row.conname IN (
                      'ck_arb_subject_evidence_snapshot_shape',
                      'ck_arb_review_cycle_shape',
                      'ck_arb_review_item_typed_shape'
                  )
                """
            ),
            {"schema_name": schema_name},
        )
    )
    for name in {
        "ck_arb_subject_evidence_snapshot_shape",
        "ck_arb_review_cycle_shape",
        "ck_arb_review_item_typed_shape",
    } - constraints:
        drift.append(f"constraint_missing:{name}")

    indexes = set(
        connection.scalars(
            text(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = :schema_name
                  AND indexname IN (
                      'uq_arb_review_cycle_number',
                      'uq_arb_review_cycle_review_number',
                      'uq_arb_review_cycle_predecessor',
                      'uq_arb_review_cycle_open_subject',
                      'uq_arb_review_item_cycle'
                  )
                """
            ),
            {"schema_name": schema_name},
        )
    )
    for name in {
        "uq_arb_review_cycle_number",
        "uq_arb_review_cycle_review_number",
        "uq_arb_review_cycle_predecessor",
        "uq_arb_review_cycle_open_subject",
        "uq_arb_review_item_cycle",
    } - indexes:
        drift.append(f"index_missing:{name}")

    trigger_state = _arb_catalog_state(connection)
    for table, names in _ARB_REQUIRED_TRIGGERS.items():
        for name in names:
            state = trigger_state.get((table, name))
            if state is None:
                drift.append(f"trigger_missing:{table}.{name}")
            elif state == "D":
                drift.append(f"trigger_disabled:{table}.{name}")
    snapshot_history_state = trigger_state.get(
        (
            "arb_subject_evidence_snapshots",
            "trg_reject_arb_subject_snapshot_mutation",
        )
    )
    if snapshot_history_state is None:
        drift.append(
            "trigger_missing:arb_subject_evidence_snapshots."
            "trg_reject_arb_subject_snapshot_mutation"
        )
    elif snapshot_history_state == "D":
        drift.append(
            "trigger_disabled:arb_subject_evidence_snapshots."
            "trg_reject_arb_subject_snapshot_mutation"
        )

    functions = set(
        connection.scalars(
            text(
                """
                SELECT procedure.proname
                FROM pg_proc procedure
                JOIN pg_namespace namespace ON namespace.oid = procedure.pronamespace
                WHERE namespace.nspname = :schema_name
                  AND procedure.proname IN (
                      'archie_validate_arb_cycle_membership',
                      'archie_guard_arb_cycle_history',
                      'archie_reject_arb_subject_snapshot_mutation'
                  )
                """
            ),
            {"schema_name": schema_name},
        )
    )
    for name in {
        "archie_validate_arb_cycle_membership",
        "archie_guard_arb_cycle_history",
        "archie_reject_arb_subject_snapshot_mutation",
    } - functions:
        drift.append(f"function_missing:{name}")
    return sorted(drift)


def ensure_arb_cycle_constraints(connection):
    """Reconcile commit-time membership and immutable typed ARB history."""
    if connection.dialect.name != "postgresql":
        return
    from sqlalchemy import text

    schema_name = connection.scalar(text("SELECT current_schema()"))
    quote = connection.dialect.identifier_preparer.quote
    quoted_schema = quote(schema_name)
    connection.exec_driver_sql(
        "SELECT pg_advisory_xact_lock(hashtext('archie_typed_arb_constraints'))"
    )
    tables = set(
        connection.scalars(
            text("SELECT tablename FROM pg_tables WHERE schemaname = :schema_name"),
            {"schema_name": schema_name},
        )
    )

    constraint_models = (
        ("arb_subject_evidence_snapshots", "ck_arb_subject_evidence_snapshot_shape"),
        ("arb_review_cycles", "ck_arb_review_cycle_shape"),
        ("arb_review_items", "ck_arb_review_item_typed_shape"),
    )
    for table_name, constraint_name in constraint_models:
        if table_name not in tables:
            continue
        exists = connection.scalar(
            text(
                """
                SELECT count(*)
                FROM pg_constraint constraint_row
                JOIN pg_class cls ON cls.oid = constraint_row.conrelid
                JOIN pg_namespace namespace ON namespace.oid = cls.relnamespace
                WHERE namespace.nspname = :schema_name
                  AND cls.relname = :table_name
                  AND constraint_row.conname = :constraint_name
                """
            ),
            {
                "schema_name": schema_name,
                "table_name": table_name,
                "constraint_name": constraint_name,
            },
        )
        if exists:
            continue
        model_table = db.metadata.tables[table_name]
        constraint = next(
            item
            for item in model_table.constraints
            if item.name == constraint_name
        )
        qualified_table = f"{quoted_schema}.{quote(table_name)}"
        connection.exec_driver_sql(
            f"ALTER TABLE {qualified_table} ADD CONSTRAINT {quote(constraint_name)} "
            f"CHECK ({constraint.sqltext}) NOT VALID"
        )
        connection.exec_driver_sql(
            f"ALTER TABLE {qualified_table} VALIDATE CONSTRAINT {quote(constraint_name)}"
        )

    if "arb_review_cycles" in tables:
        cycle_table = f"{quoted_schema}.{quote('arb_review_cycles')}"
        for statement in (
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_arb_review_cycle_number "
            f"ON {cycle_table} (organization_id, subject_type, subject_id, cycle_number)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_arb_review_cycle_review_number "
            f"ON {cycle_table} (organization_id, review_number)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_arb_review_cycle_predecessor "
            f"ON {cycle_table} (predecessor_cycle_id)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_arb_review_cycle_open_subject "
            f"ON {cycle_table} (organization_id, subject_type, subject_id) "
            "WHERE closed_at IS NULL",
        ):
            connection.exec_driver_sql(statement)
    if "arb_review_items" in tables:
        review_table = f"{quoted_schema}.{quote('arb_review_items')}"
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_arb_review_item_cycle "
            f"ON {review_table} (review_cycle_id)"
        )

    connection.exec_driver_sql(_arb_membership_function_sql(quoted_schema))
    connection.exec_driver_sql(_arb_history_function_sql(quoted_schema))
    trigger_state = _arb_catalog_state(connection)
    function_names = {
        "trg_arb_subject_snapshot_membership":
            "archie_validate_arb_cycle_membership",
        "trg_arb_cycle_membership": "archie_validate_arb_cycle_membership",
        "trg_arb_review_cycle_membership":
            "archie_validate_arb_cycle_membership",
        "trg_arb_cycle_history": "archie_guard_arb_cycle_history",
        "trg_arb_review_cycle_history": "archie_guard_arb_cycle_history",
    }
    constraint_triggers = {
        "trg_arb_subject_snapshot_membership",
        "trg_arb_cycle_membership",
        "trg_arb_review_cycle_membership",
    }
    for table_name, trigger_names in _ARB_REQUIRED_TRIGGERS.items():
        if table_name not in tables:
            continue
        qualified_table = f"{quoted_schema}.{quote(table_name)}"
        for trigger_name in trigger_names:
            if (table_name, trigger_name) in trigger_state:
                if trigger_state[(table_name, trigger_name)] == "D":
                    connection.exec_driver_sql(
                        f"ALTER TABLE {qualified_table} ENABLE TRIGGER {quote(trigger_name)}"
                    )
                continue
            qualified_function = (
                f"{quoted_schema}.{quote(function_names[trigger_name])}()"
            )
            if trigger_name in constraint_triggers:
                connection.exec_driver_sql(
                    f"CREATE CONSTRAINT TRIGGER {quote(trigger_name)} "
                    f"AFTER INSERT OR UPDATE ON {qualified_table} "
                    "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
                    f"EXECUTE FUNCTION {qualified_function}"
                )
            else:
                connection.exec_driver_sql(
                    f"CREATE TRIGGER {quote(trigger_name)} "
                    f"BEFORE UPDATE OR DELETE ON {qualified_table} FOR EACH ROW "
                    f"EXECUTE FUNCTION {qualified_function}"
                )


@event.listens_for(ARBReviewCycle.__table__, "after_create")
@event.listens_for(ARBReviewItem.__table__, "after_create")
def _install_arb_cycle_constraints(_target, connection, **_kwargs):
    ensure_arb_cycle_constraints(connection)


class ARBReviewComment(TenantMixin, db.Model):
    """Comments and discussion on ARB review items."""

    __tablename__ = "arb_review_comments"

    id = db.Column(db.Integer, primary_key=True)
    # Phase B (Wave 4): TenantMixin enabled — backfill completed in Phase A.
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)
    review_item_id = db.Column(db.Integer, db.ForeignKey("arb_review_items.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    comment_type = db.Column(
        db.String(30), default="general"
    )  # general, concern, recommendation, condition, approval
    content = db.Column(db.Text, nullable=False)

    # For threaded discussions
    parent_comment_id = db.Column(db.Integer, db.ForeignKey("arb_review_comments.id"))

    # Status
    resolved = db.Column(db.Boolean, default=False)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    resolved_at = db.Column(db.DateTime)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    review_item = db.relationship("ARBReviewItem", back_populates="comments")
    user = db.relationship("User", foreign_keys=[user_id], backref="arb_comments")
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_id])
    replies = db.relationship("ARBReviewComment", backref=db.backref("parent", remote_side=[id]))


class ARBCapabilityImpact(TenantMixin, db.Model):
    """Links ARB review items to impacted capabilities."""

    __tablename__ = "arb_capability_impacts"

    id = db.Column(db.Integer, primary_key=True)
    # Phase B (Wave 4): TenantMixin enabled — backfill completed in Phase A.
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)
    review_item_id = db.Column(db.Integer, db.ForeignKey("arb_review_items.id"), nullable=False)
    capability_id = db.Column(db.Integer, db.ForeignKey("unified_capabilities.id"), nullable=False)

    # Impact analysis
    impact_type = db.Column(
        db.String(50)
    )  # enhances, replaces, deprecates, new_implementation, modifies
    impact_level = db.Column(db.String(20))  # high, medium, low
    impact_description = db.Column(db.Text)

    # Gap analysis integration
    addresses_gap = db.Column(db.Boolean, default=False)
    gap_id = db.Column(db.Integer)  # Reference to capability gap if applicable

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    review_item = db.relationship("ARBReviewItem", back_populates="capability_links")
    capability = db.relationship("UnifiedCapability", backref="arb_impacts")

    __table_args__ = (
        db.UniqueConstraint("review_item_id", "capability_id", name="uix_arb_capability_impact"),
    )


# Global reference data (shared across tenants) — intentionally NOT TenantMixin; org column unused. See wave-4 Task-2 review.
class ARBGovernanceStandard(db.Model):
    """
    Architecture governance standards and policies.

    Defines the criteria and checklists used for ARB reviews.
    """

    __tablename__ = "arb_governance_standards"

    id = db.Column(db.Integer, primary_key=True)
    # Global reference data (shared across tenants) — intentionally NOT TenantMixin; org column unused. See wave-4 Task-2 review.
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # STD-SEC - 001
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)

    # Classification
    category = db.Column(
        db.String(50)
    )  # security, integration, data, performance, compliance, architecture
    togaf_phase = db.Column(db.String(50))  # Applicable TOGAF ADM phase
    archimate_layer = db.Column(db.String(30))  # Applicable ArchiMate layer

    # Standard details
    requirements = db.Column(db.JSON)  # List of specific requirements
    checklist_items = db.Column(db.JSON)  # Checklist for reviewers
    exceptions_allowed = db.Column(db.Boolean, default=True)
    exception_process = db.Column(db.Text)

    # Applicability
    applies_to_review_types = db.Column(db.JSON)  # List of review types this applies to
    mandatory = db.Column(db.Boolean, default=True)

    # Status
    status = db.Column(db.String(20), default="active")  # draft, active, deprecated
    effective_date = db.Column(db.Date)
    review_date = db.Column(db.Date)  # Next review date

    # Ownership
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = db.relationship("User", backref="owned_arb_standards")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "togaf_phase": self.togaf_phase,
            "archimate_layer": self.archimate_layer,
            "requirements": self.requirements,
            "checklist_items": self.checklist_items,
            "mandatory": self.mandatory,
            "status": self.status,
        }


# Default governance standards aligned with TOGAF and ArchiMate
DEFAULT_GOVERNANCE_STANDARDS = [
    {
        "code": "STD-ARCH - 001",
        "name": "Architecture Documentation Standard",
        "description": "All architecture artifacts must be properly documented with ArchiMate viewpoints",
        "category": "architecture",
        "requirements": [
            "Solution must include relevant ArchiMate viewpoints",
            "All architecture decisions must be documented as ADRs",
            "Traceability to business requirements must be established",
        ],
        "checklist_items": [
            {"item": "ArchiMate diagrams provided", "required": True},
            {"item": "ADR created for significant decisions", "required": True},
            {"item": "Business requirements traceability matrix", "required": False},
            {"item": "TOGAF phase artifacts complete", "required": True},
        ],
        "mandatory": True,
    },
    {
        "code": "STD-CAP - 001",
        "name": "Capability Alignment Standard",
        "description": "Solutions must align with enterprise capability model",
        "category": "capability",
        "requirements": [
            "Solution must map to one or more business capabilities",
            "Capability gaps addressed must be identified",
            "Impact on existing capability implementations assessed",
        ],
        "checklist_items": [
            {"item": "Capability mapping completed", "required": True},
            {"item": "Gap analysis performed", "required": True},
            {"item": "Existing capability impact assessed", "required": True},
            {"item": "Capability roadmap alignment verified", "required": False},
        ],
        "mandatory": True,
    },
    {
        "code": "STD-SEC - 001",
        "name": "Security Architecture Standard",
        "description": "All solutions must meet enterprise security requirements",
        "category": "security",
        "requirements": [
            "Security architecture review completed",
            "Data classification and protection defined",
            "Authentication and authorization mechanisms specified",
            "Compliance with security policies verified",
        ],
        "checklist_items": [
            {"item": "Security architecture diagram provided", "required": True},
            {"item": "Data classification completed", "required": True},
            {"item": "AuthN/AuthZ approach defined", "required": True},
            {"item": "Threat modeling completed", "required": False},
            {"item": "Security controls mapped", "required": True},
        ],
        "mandatory": True,
    },
    {
        "code": "STD-INT - 001",
        "name": "Integration Architecture Standard",
        "description": "Integration patterns must follow enterprise standards",
        "category": "integration",
        "requirements": [
            "Integration patterns must be from approved catalog",
            "API specifications must follow enterprise standards",
            "Data flow and transformation logic documented",
        ],
        "checklist_items": [
            {"item": "Integration pattern identified", "required": True},
            {"item": "API specification provided (OpenAPI/AsyncAPI)", "required": True},
            {"item": "Data mapping documented", "required": True},
            {"item": "Error handling strategy defined", "required": True},
        ],
        "mandatory": True,
    },
    {
        "code": "STD-TECH - 001",
        "name": "Technology Selection Standard",
        "description": "Technology selections must align with enterprise standards",
        "category": "technology",
        "requirements": [
            "Technologies must be from approved technology radar",
            "Vendor assessment completed for new technologies",
            "Total cost of ownership analyzed",
        ],
        "checklist_items": [
            {"item": "Technologies on approved radar", "required": True},
            {"item": "Vendor assessment completed", "required": False},
            {"item": "TCO analysis provided", "required": True},
            {"item": "Skills availability assessed", "required": True},
        ],
        "mandatory": True,
    },
]


# Backwards-compatible alias used by older modules
ARBSession = ArchitectureReviewBoard


# ---------------------------------------------------------------------------
# AG-003: Derogation — formal architecture waiver with expiry and conditions
# ---------------------------------------------------------------------------

if not _FAST_INIT:

    class Derogation(db.Model):
        """Formal architecture waiver approved by the ARB.

        A Derogation records a time-bounded exception to a governance standard,
        linking to the originating ARBReviewItem, the granted conditions, and
        an expiry date after which the standard must be fully met.

        TOGAF ADM Phase G: Implementation Governance — waiver management.
        """

        __tablename__ = "arb_derogations"
        __table_args__ = {"extend_existing": True}

        id = db.Column(db.Integer, primary_key=True)

        # FK to the ARB review item that requested the waiver
        arb_review_item_id = db.Column(
            db.Integer,
            db.ForeignKey("arb_review_items.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        )

        # Identity
        derogation_number = db.Column(db.String(50), unique=True, nullable=False)
        title = db.Column(db.String(255), nullable=False)
        rationale = db.Column(db.Text, nullable=False)

        # Conditions under which the waiver is granted
        conditions = db.Column(db.Text, nullable=True)

        # Governance lifecycle
        status = db.Column(db.String(30), nullable=False, default="pending")
        # Allowed status values: pending, approved, rejected, expired, revoked

        expiry_date = db.Column(db.Date, nullable=True)
        granted_by = db.Column(db.String(100), nullable=True)
        granted_at = db.Column(db.DateTime, nullable=True)

        # ADM phase reference
        adm_phase = db.Column(db.String(10), nullable=True)  # e.g. "G", "H"

        # Timestamps
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        updated_at = db.Column(
            db.DateTime,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
        )

        # Relationships
        review_item = db.relationship(
            "ARBReviewItem",
            backref=db.backref("derogations", lazy="dynamic"),
            foreign_keys=[arb_review_item_id],
        )

        def __init__(self, **kwargs):
            kwargs.setdefault("status", "pending")
            super().__init__(**kwargs)

        def is_expired(self) -> bool:
            """Return True if expiry_date has passed."""
            if self.expiry_date is None:
                return False
            return datetime.utcnow().date() > self.expiry_date

        def __repr__(self) -> str:
            return f"<Derogation {self.derogation_number} status={self.status}>"


# ---------------------------------------------------------------------------
# CM-001: ChangeRequest — formal architecture change request lifecycle model
# ---------------------------------------------------------------------------

if not _FAST_INIT:

    class ChangeRequest(db.Model):
        """Formal architecture change request for TOGAF Phase H governance.

        Records a proposed change to the current architecture baseline.
        When approved, an ADM cycle is triggered (adm_cycle_triggered=True)
        to process the change through relevant ADM phases.

        TOGAF ADM Phase H: Architecture Change Management.
        """

        __tablename__ = "arb_change_requests"
        __table_args__ = {"extend_existing": True}

        id = db.Column(db.Integer, primary_key=True)

        # Identity
        change_request_number = db.Column(db.String(50), unique=True, nullable=False)
        title = db.Column(db.String(255), nullable=False)
        description = db.Column(db.Text, nullable=False)

        # Classification
        change_type = db.Column(db.String(50), nullable=False)
        # Allowed: simplification, exception, business_change, technology_change,
        #          correction, governance_change

        impact_level = db.Column(db.String(20), nullable=True)
        # Allowed: low, medium, high, critical

        # ADM cycle management
        adm_cycle_triggered = db.Column(db.Boolean, nullable=False, default=False)
        adm_phases_affected = db.Column(db.Text, nullable=True)  # comma-separated phases

        # Lifecycle
        status = db.Column(db.String(30), nullable=False, default="draft")
        # Allowed: draft, submitted, under_review, approved, rejected, withdrawn, implemented

        submitted_by = db.Column(db.String(100), nullable=True)
        submitted_at = db.Column(db.DateTime, nullable=True)
        reviewed_by = db.Column(db.String(100), nullable=True)
        reviewed_at = db.Column(db.DateTime, nullable=True)
        decision_rationale = db.Column(db.Text, nullable=True)

        # Optional FK to the originating ARB review item
        arb_review_item_id = db.Column(
            db.Integer,
            db.ForeignKey("arb_review_items.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        )

        # Timestamps
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        updated_at = db.Column(
            db.DateTime,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
        )

        # Relationships
        review_item = db.relationship(
            "ARBReviewItem",
            backref=db.backref("change_requests", lazy="dynamic"),
            foreign_keys=[arb_review_item_id],
        )

        def __init__(self, **kwargs):
            kwargs.setdefault("status", "draft")
            kwargs.setdefault("adm_cycle_triggered", False)
            super().__init__(**kwargs)

        def __repr__(self) -> str:
            return f"<ChangeRequest {self.change_request_number} type={self.change_type} status={self.status}>"


# ---------------------------------------------------------------------------
# DOC-001: ARBDocument — supporting document attachments for ARB governance
# ---------------------------------------------------------------------------

if not _FAST_INIT:

    class ARBDocument(TenantMixin, db.Model):
        """File attachment for ARB change requests and review items.

        Provides a governance-trail document store. Each row represents one
        uploaded file attached to either a ChangeRequest or an ARBReviewItem.
        Exactly one FK must be non-null (enforced at the application layer).

        Document types:
          supporting   — background context, architecture diagrams
          evidence     — test results, benchmarks, compliance proof
          decision     — decision record, approval memo
          minutes      — meeting minutes or email thread
        """

        __tablename__ = "arb_documents"
        __table_args__ = {"extend_existing": True}

        id = db.Column(db.Integer, primary_key=True)
        # Phase B (Wave 4): TenantMixin enabled — backfill completed in Phase A.
        organization_id = db.Column(
            db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True
        )

        # Polymorphic parent — exactly one must be set.
        # change_request_id → architecture_change_requests (ArchitectureChangeRequest, Phase H form)
        # review_item_id    → arb_review_items (ARBReviewItem, solution governance review)
        change_request_id = db.Column(
            db.Integer,
            db.ForeignKey("architecture_change_requests.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        )
        review_item_id = db.Column(
            db.Integer,
            db.ForeignKey("arb_review_items.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        )

        # File metadata
        original_name = db.Column(db.String(255), nullable=False)
        stored_name = db.Column(db.String(255), nullable=False)   # secure_filename result
        file_path = db.Column(db.String(512), nullable=False)      # relative to app root
        file_size = db.Column(db.Integer, nullable=True)           # bytes
        mime_type = db.Column(db.String(100), nullable=True)

        # Classification
        document_type = db.Column(db.String(50), nullable=False, default="supporting")

        # Audit
        uploaded_by_id = db.Column(
            db.Integer,
            db.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        )
        uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

        # Relationships
        change_request = db.relationship(
            "ArchitectureChangeRequest",
            backref=db.backref("arb_documents", lazy="dynamic"),
            foreign_keys=[change_request_id],
        )
        review_item = db.relationship(
            "ARBReviewItem",
            backref=db.backref("documents", lazy="dynamic"),
            foreign_keys=[review_item_id],
        )
        uploaded_by = db.relationship("User", foreign_keys=[uploaded_by_id])

        def to_dict(self):
            return {
                "id": self.id,
                "original_name": self.original_name,
                "file_size": self.file_size,
                "mime_type": self.mime_type,
                "document_type": self.document_type,
                "uploaded_by": self.uploaded_by.email if self.uploaded_by else None,
                "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            }

        def __repr__(self) -> str:
            parent = f"cr={self.change_request_id}" if self.change_request_id else f"ri={self.review_item_id}"
            return f"<ARBDocument {self.original_name} {parent}>"

