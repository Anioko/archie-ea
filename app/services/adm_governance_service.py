"""
ADM Governance Service

Orchestrates Architecture Board approval workflow for ADM phase transitions.
Replaces drag-and-drop with governed transitions requiring explicit approval.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import db
from app.models.adm_kanban import ADMPhase, KanbanBoard, KanbanCard
from app.models.adm_phase_approval import (
    ADMComplianceCheckpoint,
    ADMPhaseApproval,
    ADMStakeholderConcurrence,
    ADMTransitionHistory,
    ApprovalStatus,
)

logger = logging.getLogger(__name__)


class ADMGovernanceService:
    """
    Service for managing ADM phase transition governance.

    Provides:
    - Phase transition approval workflow
    - Compliance checklist validation
    - Stakeholder concurrence tracking
    - Architecture Board integration
    - Audit trail for all transitions
    """

    # Default stakeholders required by phase
    DEFAULT_STAKEHOLDERS = {
        "PRELIM": ["enterprise_architect", "cio"],
        "A": ["enterprise_architect", "business_owner", "program_manager"],
        "B": ["business_architect", "business_owner", "process_owner"],
        "C": ["application_architect", "data_architect", "solution_architect"],
        "D": ["technology_architect", "infrastructure_architect", "security_architect"],
        "E": ["enterprise_architect", "solution_architect", "program_manager"],
        "F": ["program_manager", "project_manager", "enterprise_architect"],
        "G": ["solution_architect", "program_manager", "governance_officer"],
        "H": ["enterprise_architect", "governance_officer", "change_manager"],
        "REQ": ["business_analyst", "enterprise_architect"],
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def create_transition_request(
        self,
        card_id: int,
        target_phase_id: int,
        requested_by_id: int,
        business_justification: str,
        technical_justification: str = None,
        risk_assessment: str = None,
    ) -> ADMPhaseApproval:
        """
        Create a formal phase transition approval request.

        Args:
            card_id: ID of the card to transition
            target_phase_id: ID of target ADM phase
            requested_by_id: User ID requesting the transition
            business_justification: Business rationale for transition
            technical_justification: Technical rationale
            risk_assessment: Risk assessment

        Returns:
            Created ADMPhaseApproval instance
        """
        card = db.session.get(KanbanCard, card_id)
        if not card:
            raise ValueError(f"Card {card_id} not found")

        target_phase = db.session.get(ADMPhase, target_phase_id)
        if not target_phase:
            raise ValueError(f"Target phase {target_phase_id} not found")

        # Check if there's already a pending approval for this transition
        existing = (
            ADMPhaseApproval.query.filter_by(
                card_id=card_id,
                target_phase_id=target_phase_id,
                status="submitted",
            )
            .filter(ADMPhaseApproval.status.in_(["draft", "submitted", "under_review"]))
            .first()
        )

        if existing:
            raise ValueError(f"Pending approval already exists for this transition: {existing.approval_number}")

        approval = ADMPhaseApproval(
            approval_number=ADMPhaseApproval.generate_approval_number(),
            card_id=card_id,
            board_id=card.board_id,
            source_phase_id=card.adm_phase_id,
            target_phase_id=target_phase_id,
            requested_by_id=requested_by_id,
            business_justification=business_justification,
            technical_justification=technical_justification,
            risk_assessment=risk_assessment,
            status=ApprovalStatus.DRAFT.value,
        )

        db.session.add(approval)
        db.session.flush()  # Get ID for checkpoint creation

        # Create compliance checkpoints based on target phase
        self._create_compliance_checkpoints(approval, target_phase)

        # Create stakeholder concurrence records
        self._create_stakeholder_concurrences(approval, target_phase)

        db.session.commit()

        self.logger.info(f"Created transition request {approval.approval_number}")
        return approval

    def _create_compliance_checkpoints(self, approval: ADMPhaseApproval, target_phase: ADMPhase):
        """Create compliance checkpoints based on phase gate criteria."""

        # Standard checkpoints for all phases
        standard_checkpoints = [
            {
                "name": "Phase Gate Criteria Review",
                "category": "governance",
                "description": f"Architecture Board gate criteria for {target_phase.name} satisfied",
                "required": True,
                "evidence_required": True,
            },
            {
                "name": "Required Inputs Verified",
                "category": "deliverable",
                "description": "All required inputs for phase are available",
                "required": True,
                "evidence_required": True,
            },
            {
                "name": "Stakeholder Concurrence",
                "category": "stakeholder",
                "description": "Required stakeholder approvals obtained",
                "required": True,
                "evidence_required": False,
            },
        ]

        # Phase-specific checkpoints
        phase_checkpoints = target_phase.governance_checkpoints or []

        for checkpoint_data in standard_checkpoints:
            checkpoint = ADMComplianceCheckpoint(
                approval_id=approval.id,
                checkpoint_name=checkpoint_data["name"],
                checkpoint_category=checkpoint_data["category"],
                description=checkpoint_data["description"],
                is_required=checkpoint_data["required"],
                evidence_required=checkpoint_data["evidence_required"],
            )
            db.session.add(checkpoint)

        # Add phase-specific checkpoints
        for idx, phase_checkpoint in enumerate(phase_checkpoints, 1):
            checkpoint = ADMComplianceCheckpoint(
                approval_id=approval.id,
                checkpoint_name=f"Phase Checkpoint {idx}",
                checkpoint_category="governance",
                description=phase_checkpoint,
                is_required=True,
                evidence_required=True,
            )
            db.session.add(checkpoint)

    def _create_stakeholder_concurrences(self, approval: ADMPhaseApproval, target_phase: ADMPhase):
        """Create stakeholder concurrence records based on phase requirements."""

        required_stakeholders = self.DEFAULT_STAKEHOLDERS.get(target_phase.code, ["enterprise_architect"])

        for stakeholder_role in required_stakeholders:
            concurrence = ADMStakeholderConcurrence(
                approval_id=approval.id,
                stakeholder_role=stakeholder_role,
                status="pending",
            )
            db.session.add(concurrence)

    def submit_for_review(self, approval_id: int) -> ADMPhaseApproval:
        """
        Submit a draft approval request for Architecture Board review.

        Validates that required checkpoints are completed before submission.
        """
        approval = db.session.get(ADMPhaseApproval, approval_id)
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")

        if approval.status != ApprovalStatus.DRAFT.value:
            raise ValueError("Only draft approvals can be submitted")

        # Validate minimum requirements
        validation = self._validate_submission_readiness(approval)
        if not validation["valid"]:
            raise ValueError(f"Submission requirements not met: {validation['issues']}")

        approval.status = ApprovalStatus.SUBMITTED.value
        approval.requested_at = datetime.utcnow()

        db.session.commit()

        self.logger.info(f"Submitted approval {approval.approval_number} for review")
        return approval

    def _validate_submission_readiness(self, approval: ADMPhaseApproval) -> Dict[str, Any]:
        """Validate that approval request is ready for submission."""

        issues = []

        # Check required checkpoints
        required_checkpoints = [
            cp for cp in approval.checkpoints if cp.is_required and not cp.is_completed
        ]
        if required_checkpoints:
            issues.append(f"{len(required_checkpoints)} required checkpoints incomplete")

        # Check stakeholder concurrence
        pending_stakeholders = [
            sc for sc in approval.stakeholder_concurrences if sc.status == "pending"
        ]
        if pending_stakeholders:
            issues.append(f"{len(pending_stakeholders)} stakeholder approvals pending")

        # Check justifications
        if not approval.business_justification:
            issues.append("Business justification required")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
        }

    def assign_reviewer(self, approval_id: int, reviewer_id: int) -> ADMPhaseApproval:
        """Assign an Architecture Board reviewer to the approval request."""

        approval = db.session.get(ADMPhaseApproval, approval_id)
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")

        approval.reviewer_id = reviewer_id
        approval.status = ApprovalStatus.UNDER_REVIEW.value
        approval.review_started_at = datetime.utcnow()

        db.session.commit()

        self.logger.info(f"Assigned reviewer to approval {approval.approval_number}")
        return approval

    def record_decision(
        self,
        approval_id: int,
        decision: str,
        rationale: str,
        decided_by_id: int,
        conditions: List[Dict] = None,
    ) -> ADMPhaseApproval:
        """
        Record Architecture Board decision on phase transition.

        Args:
            approval_id: Approval request ID
            decision: approved, approved_with_conditions, rejected, or deferred
            rationale: Decision explanation
            decided_by_id: User ID recording decision
            conditions: Optional conditions for conditional approval
        """

        approval = db.session.get(ADMPhaseApproval, approval_id)
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")

        if approval.status not in ["submitted", "under_review", "pending_information"]:
            raise ValueError(f"Cannot record decision for approval in status: {approval.status}")

        approval.decision = decision
        approval.decision_rationale = rationale
        approval.decided_by_id = decided_by_id
        approval.decision_date = datetime.utcnow()
        approval.review_completed_at = datetime.utcnow()

        if conditions:
            approval.conditions = conditions

        # Update status based on decision
        if decision == "approved":
            approval.status = ApprovalStatus.APPROVED.value
        elif decision == "approved_with_conditions":
            approval.status = ApprovalStatus.APPROVED_WITH_CONDITIONS.value
        elif decision == "rejected":
            approval.status = ApprovalStatus.REJECTED.value
        elif decision == "deferred":
            approval.status = ApprovalStatus.DEFERRED.value

        db.session.commit()

        self.logger.info(f"Recorded decision {decision} for approval {approval.approval_number}")
        return approval

    def execute_transition(self, approval_id: int, executed_by_id: int) -> KanbanCard:
        """
        Execute the approved phase transition.

        This moves the card to the target phase after approval.
        """

        approval = db.session.get(ADMPhaseApproval, approval_id)
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")

        if not approval.is_approved():
            raise ValueError(f"Cannot execute transition: approval status is {approval.status}")

        card = approval.card
        old_phase_id = card.adm_phase_id

        # Update card phase
        card.adm_phase_id = approval.target_phase_id

        # Record in transition history
        history = ADMTransitionHistory(
            card_id=card.id,
            board_id=card.board_id,
            source_phase_id=approval.source_phase_id,
            target_phase_id=approval.target_phase_id,
            approval_id=approval.id,
            transitioned_by_id=executed_by_id,
            notes=f"Transition approved via {approval.approval_number}",
        )
        db.session.add(history)

        db.session.commit()

        self.logger.info(
            f"Executed transition for card {card.id}: "
            f"{approval.source_phase.code} -> {approval.target_phase.code}"
        )
        return card

    def get_pending_approvals(self, board_id: int = None) -> List[ADMPhaseApproval]:
        """Get all pending approval requests."""

        query = ADMPhaseApproval.query.filter(
            ADMPhaseApproval.status.in_(["draft", "submitted", "under_review", "pending_information"])
        )

        if board_id:
            query = query.filter_by(board_id=board_id)

        return query.order_by(ADMPhaseApproval.created_at.desc()).all()

    def get_approval_summary(self, card_id: int) -> Dict[str, Any]:
        """Get summary of approval status for a card."""

        approvals = ADMPhaseApproval.query.filter_by(card_id=card_id).all()

        return {
            "total_approvals": len(approvals),
            "approved": len([a for a in approvals if a.is_approved()]),
            "pending": len([a for a in approvals if a.status in ["draft", "submitted", "under_review"]]),
            "rejected": len([a for a in approvals if a.status == "rejected"]),
            "recent_approvals": [a.to_dict() for a in approvals[:5]],
        }

    def complete_checkpoint(
        self,
        checkpoint_id: int,
        completed_by_id: int,
        evidence_url: str = None,
        evidence_notes: str = None,
    ) -> ADMComplianceCheckpoint:
        """Mark a compliance checkpoint as completed."""

        checkpoint = db.session.get(ADMComplianceCheckpoint, checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")

        checkpoint.is_completed = True
        checkpoint.completed_at = datetime.utcnow()
        checkpoint.completed_by_id = completed_by_id

        if evidence_url:
            checkpoint.evidence_url = evidence_url
        if evidence_notes:
            checkpoint.evidence_notes = evidence_notes

        db.session.commit()

        self.logger.info(f"Completed checkpoint {checkpoint.checkpoint_name}")
        return checkpoint

    def record_stakeholder_concurrence(
        self,
        concurrence_id: int,
        status: str,
        comments: str = None,
        concerns: str = None,
    ) -> ADMStakeholderConcurrence:
        """Record stakeholder concurrence (approval/rejection/abstention)."""

        concurrence = db.session.get(ADMStakeholderConcurrence, concurrence_id)
        if not concurrence:
            raise ValueError(f"Concurrence {concurrence_id} not found")

        concurrence.status = status
        concurrence.concurrence_date = datetime.utcnow()
        concurrence.responded_at = datetime.utcnow()

        if comments:
            concurrence.comments = comments
        if concerns:
            concurrence.concerns = concerns

        db.session.commit()

        self.logger.info(f"Recorded stakeholder concurrence: {concurrence.stakeholder_role} -> {status}")
        return concurrence


# Singleton instance
adm_governance_service = ADMGovernanceService()
