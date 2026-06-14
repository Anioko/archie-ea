"""
ARB Workflow Service

ARB workflow service with human-in-loop decision processes.
Implements approval flows, stakeholder coordination, and exception management.

Features:
- Multi-stage approval workflows
- Stakeholder notification and coordination
- Exception handling and escalation
- Workflow state management
- Integration with decision ledger
- Human-in-the-loop processing
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkflowStage(Enum):
    """ARB workflow stages."""

    SUBMITTED = "submitted"
    POLICY_CHECK = "policy_check"
    TECHNICAL_REVIEW = "technical_review"
    BUSINESS_REVIEW = "business_review"
    SECURITY_REVIEW = "security_review"
    APPROVAL = "approval"
    IMPLEMENTATION = "implementation"
    CLOSED = "closed"


class WorkflowAction(Enum):
    """Available workflow actions."""

    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    ESCALATE = "escalate"
    HOLD = "hold"
    RESUME = "resume"


@dataclass
class WorkflowStep:
    """Individual step in ARB workflow."""

    step_id: str
    stage: WorkflowStage
    name: str
    description: str
    required_approvers: List[str]  # User IDs or role names
    optional_reviewers: List[str] = field(default_factory=list)
    timeout_hours: int = 72  # Default 3 days
    auto_advance: bool = False
    conditions: List[str] = field(default_factory=list)  # Conditions to advance
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WorkflowInstance:
    """Instance of ARB workflow for a specific decision."""

    workflow_id: str
    decision_id: str
    current_stage: WorkflowStage
    steps: List[WorkflowStep] = field(default_factory=list)
    approvals: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # step_id -> approval data
    rejections: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # step_id -> rejection data
    comments: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    escalated: bool = False
    on_hold: bool = False


class ARBWorkflowService:
    """
    ARB workflow service with human-in-the-loop processing.

    Manages multi-stage approval workflows:
    - Policy evaluation gates
    - Stakeholder coordination
    - Exception handling
    - Progress tracking and reporting
    """

    def __init__(self):
        self.policy_engine = PolicyEngine()
        self.decision_ledger = DecisionLedger()
        self.workflows: Dict[str, WorkflowInstance] = {}
        self._define_default_workflow()

    def _define_default_workflow(self):
        """Define the default ARB approval workflow."""
        self.default_workflow = [
            WorkflowStep(
                step_id="submit",
                stage=WorkflowStage.SUBMITTED,
                name="Submission",
                description="Initial submission for ARB review",
                required_approvers=[],
                timeout_hours=24,
                auto_advance=True,
            ),
            WorkflowStep(
                step_id="policy_check",
                stage=WorkflowStage.POLICY_CHECK,
                name="Policy Evaluation",
                description="Automated policy and compliance checking",
                required_approvers=[],  # Automated
                timeout_hours=2,
                auto_advance=True,
            ),
            WorkflowStep(
                step_id="technical_review",
                stage=WorkflowStage.TECHNICAL_REVIEW,
                name="Technical Review",
                description="Technical architecture and implementation review",
                required_approvers=["architect", "tech_lead"],
                optional_reviewers=["dev_team"],
                timeout_hours=72,
            ),
            WorkflowStep(
                step_id="business_review",
                stage=WorkflowStage.BUSINESS_REVIEW,
                name="Business Review",
                description="Business value and strategic alignment review",
                required_approvers=["business_owner", "product_manager"],
                optional_reviewers=["stakeholders"],
                timeout_hours=72,
            ),
            WorkflowStep(
                step_id="security_review",
                stage=WorkflowStage.SECURITY_REVIEW,
                name="Security Review",
                description="Security and compliance review",
                required_approvers=["security_officer"],
                optional_reviewers=["compliance_team"],
                timeout_hours=48,
            ),
            WorkflowStep(
                step_id="final_approval",
                stage=WorkflowStage.APPROVAL,
                name="Final Approval",
                description="Final ARB board approval",
                required_approvers=["arb_chair", "arb_members"],
                timeout_hours=72,
            ),
            WorkflowStep(
                step_id="implementation",
                stage=WorkflowStage.IMPLEMENTATION,
                name="Implementation",
                description="Implementation and deployment",
                required_approvers=["implementation_team"],
                timeout_hours=168,  # 1 week
                auto_advance=False,
            ),
        ]

    def initiate_workflow(self, decision_data: Dict[str, Any]) -> WorkflowInstance:
        """
        Initiate ARB workflow for a decision.

        Args:
            decision_data: Decision details

        Returns:
            Workflow instance
        """
        # Record decision in ledger
        decision_entry = self.decision_ledger.record_decision(decision_data)

        # Create workflow instance
        workflow = WorkflowInstance(
            workflow_id=f"WF-{decision_entry.decision_id}",
            decision_id=decision_entry.decision_id,
            current_stage=WorkflowStage.SUBMITTED,
            steps=self.default_workflow.copy(),
        )

        self.workflows[workflow.workflow_id] = workflow

        # Start workflow processing
        self._advance_workflow(workflow)

        logger.info(
            f"Initiated ARB workflow: {workflow.workflow_id} for decision: {decision_entry.decision_id}"
        )
        return workflow

    def process_action(
        self,
        workflow_id: str,
        action: WorkflowAction,
        user_id: str,
        comments: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Process workflow action.

        Args:
            workflow_id: Workflow instance ID
            action: Action to perform
            user_id: User performing action
            comments: Optional comments
            additional_data: Additional action data

        Returns:
            True if action processed successfully
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            logger.error(f"Workflow not found: {workflow_id}")
            return False

        if workflow.completed_at:
            logger.warning(f"Workflow already completed: {workflow_id}")
            return False

        # Process action based on type
        if action == WorkflowAction.APPROVE:
            return self._process_approval(workflow, user_id, comments, additional_data)
        elif action == WorkflowAction.REJECT:
            return self._process_rejection(workflow, user_id, comments, additional_data)
        elif action == WorkflowAction.REQUEST_CHANGES:
            return self._process_change_request(workflow, user_id, comments, additional_data)
        elif action == WorkflowAction.ESCALATE:
            return self._process_escalation(workflow, user_id, comments, additional_data)
        elif action == WorkflowAction.HOLD:
            return self._process_hold(workflow, user_id, comments, additional_data)
        elif action == WorkflowAction.RESUME:
            return self._process_resume(workflow, user_id, comments, additional_data)

        return False

    def _process_approval(
        self,
        workflow: WorkflowInstance,
        user_id: str,
        comments: Optional[str],
        additional_data: Optional[Dict[str, Any]],
    ) -> bool:
        """Process approval action."""
        current_step = self._get_current_step(workflow)
        if not current_step:
            return False

        # Check if user can approve this step
        if not self._can_user_approve(user_id, current_step):
            logger.warning(f"User {user_id} cannot approve step {current_step.step_id}")
            return False

        # Record approval
        approval_data = {
            "user_id": user_id,
            "approved_at": datetime.utcnow().isoformat(),
            "comments": comments,
            "additional_data": additional_data or {},
        }

        workflow.approvals[current_step.step_id] = approval_data

        # Add comment
        if comments:
            workflow.comments.append(
                {
                    "user_id": user_id,
                    "action": "approved",
                    "step": current_step.step_id,
                    "comments": comments,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        # Check if step is complete
        if self._is_step_complete(workflow, current_step):
            self._advance_workflow(workflow)

        workflow.updated_at = datetime.utcnow()
        logger.info(
            f"Processed approval for workflow {workflow.workflow_id}, step {current_step.step_id}"
        )
        return True

    def _process_rejection(
        self,
        workflow: WorkflowInstance,
        user_id: str,
        comments: Optional[str],
        additional_data: Optional[Dict[str, Any]],
    ) -> bool:
        """Process rejection action."""
        current_step = self._get_current_step(workflow)
        if not current_step:
            return False

        # Record rejection
        rejection_data = {
            "user_id": user_id,
            "rejected_at": datetime.utcnow().isoformat(),
            "comments": comments,
            "additional_data": additional_data or {},
        }

        workflow.rejections[current_step.step_id] = rejection_data

        # Add comment
        workflow.comments.append(
            {
                "user_id": user_id,
                "action": "rejected",
                "step": current_step.step_id,
                "comments": comments,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # Update decision status
        self.decision_ledger.update_decision_status(
            workflow.decision_id, DecisionStatus.REJECTED, user_id, comments
        )

        # Mark workflow as completed
        workflow.completed_at = datetime.utcnow()
        workflow.current_stage = WorkflowStage.CLOSED

        workflow.updated_at = datetime.utcnow()
        logger.info(f"Processed rejection for workflow {workflow.workflow_id}")
        return True

    def _process_change_request(
        self,
        workflow: WorkflowInstance,
        user_id: str,
        comments: Optional[str],
        additional_data: Optional[Dict[str, Any]],
    ) -> bool:
        """Process change request action."""
        current_step = self._get_current_step(workflow)
        if not current_step:
            return False

        # Add comment
        workflow.comments.append(
            {
                "user_id": user_id,
                "action": "requested_changes",
                "step": current_step.step_id,
                "comments": comments,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # Put workflow on hold
        workflow.on_hold = True
        workflow.updated_at = datetime.utcnow()

        logger.info(f"Processed change request for workflow {workflow.workflow_id}")
        return True

    def _process_escalation(
        self,
        workflow: WorkflowInstance,
        user_id: str,
        comments: Optional[str],
        additional_data: Optional[Dict[str, Any]],
    ) -> bool:
        """Process escalation action."""
        workflow.escalated = True

        workflow.comments.append(
            {
                "user_id": user_id,
                "action": "escalated",
                "step": workflow.current_stage.value,
                "comments": comments,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        workflow.updated_at = datetime.utcnow()
        logger.info(f"Escalated workflow {workflow.workflow_id}")
        return True

    def _process_hold(
        self,
        workflow: WorkflowInstance,
        user_id: str,
        comments: Optional[str],
        additional_data: Optional[Dict[str, Any]],
    ) -> bool:
        """Process hold action."""
        workflow.on_hold = True

        workflow.comments.append(
            {
                "user_id": user_id,
                "action": "placed_on_hold",
                "step": workflow.current_stage.value,
                "comments": comments,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        workflow.updated_at = datetime.utcnow()
        logger.info(f"Placed workflow {workflow.workflow_id} on hold")
        return True

    def _process_resume(
        self,
        workflow: WorkflowInstance,
        user_id: str,
        comments: Optional[str],
        additional_data: Optional[Dict[str, Any]],
    ) -> bool:
        """Process resume action."""
        workflow.on_hold = False

        workflow.comments.append(
            {
                "user_id": user_id,
                "action": "resumed",
                "step": workflow.current_stage.value,
                "comments": comments,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        workflow.updated_at = datetime.utcnow()
        logger.info(f"Resumed workflow {workflow.workflow_id}")
        return True

    def _advance_workflow(self, workflow: WorkflowInstance):
        """Advance workflow to next stage."""
        if workflow.completed_at or workflow.on_hold:
            return

        current_step = self._get_current_step(workflow)
        if not current_step:
            return

        # Check if current step should advance
        if self._should_advance_step(workflow, current_step):
            next_step = self._get_next_step(workflow)
            if next_step:
                workflow.current_stage = next_step.stage
                logger.info(
                    f"Advanced workflow {workflow.workflow_id} to stage: {next_step.stage.value}"
                )
            else:
                # Workflow complete
                workflow.completed_at = datetime.utcnow()
                workflow.current_stage = WorkflowStage.CLOSED

                # Update decision status
                self.decision_ledger.update_decision_status(
                    workflow.decision_id,
                    DecisionStatus.APPROVED,
                    "system",
                    "Workflow completed successfully",
                )

                logger.info(f"Completed workflow {workflow.workflow_id}")

    def _get_current_step(self, workflow: WorkflowInstance) -> Optional[WorkflowStep]:
        """Get current workflow step."""
        for step in workflow.steps:
            if step.stage == workflow.current_stage:
                return step
        return None

    def _get_next_step(self, workflow: WorkflowInstance) -> Optional[WorkflowStep]:
        """Get next workflow step."""
        current_found = False
        for step in workflow.steps:
            if current_found:
                return step
            if step.stage == workflow.current_stage:
                current_found = True
        return None

    def _can_user_approve(self, user_id: str, step: WorkflowStep) -> bool:
        """Check if user can approve a step."""
        # Simplified check - in production, check roles and permissions
        return user_id in step.required_approvers or user_id in step.optional_reviewers

    def _is_step_complete(self, workflow: WorkflowInstance, step: WorkflowStep) -> bool:
        """Check if workflow step is complete."""
        # For automated steps, always complete
        if step.auto_advance:
            return True

        # For manual steps, check required approvals
        approvals = workflow.approvals.get(step.step_id, {})
        return len(approvals) >= len(step.required_approvers)

    def _should_advance_step(self, workflow: WorkflowInstance, step: WorkflowStep) -> bool:
        """Check if step should advance."""
        if step.auto_advance:
            return True

        return self._is_step_complete(workflow, step)

    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow status summary."""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return None

        return {
            "workflow_id": workflow.workflow_id,
            "decision_id": workflow.decision_id,
            "current_stage": workflow.current_stage.value,
            "created_at": workflow.created_at.isoformat(),
            "updated_at": workflow.updated_at.isoformat(),
            "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
            "escalated": workflow.escalated,
            "on_hold": workflow.on_hold,
            "steps_completed": len(workflow.approvals),
            "total_steps": len(workflow.steps),
            "comments_count": len(workflow.comments),
        }

    def get_pending_actions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get pending actions for a user."""
        pending_actions = []

        for workflow in self.workflows.values():
            if workflow.completed_at or workflow.on_hold:
                continue

            current_step = self._get_current_step(workflow)
            if not current_step:
                continue

            if self._can_user_approve(user_id, current_step):
                # Check if user hasn't already acted
                step_approvals = workflow.approvals.get(current_step.step_id, {})
                step_rejections = workflow.rejections.get(current_step.step_id, {})

                if user_id not in step_approvals and user_id not in step_rejections:
                    pending_actions.append(
                        {
                            "workflow_id": workflow.workflow_id,
                            "decision_id": workflow.decision_id,
                            "step": current_step.step_id,
                            "stage": current_step.stage.value,
                            "name": current_step.name,
                            "description": current_step.description,
                            "timeout_hours": current_step.timeout_hours,
                            "due_date": (
                                workflow.created_at + timedelta(hours=current_step.timeout_hours)
                            ).isoformat(),
                        }
                    )

        return pending_actions
