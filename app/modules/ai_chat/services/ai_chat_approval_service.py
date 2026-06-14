"""
-> app.modules.ai_chat.services

AI Chat Approval Service

Manages approval workflow for CRUD operations initiated via AI chat.
Ensures no data modifications happen without explicit user confirmation.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from flask import current_app  # dead-code-ok: used in exception logging via self.logger which is app-context-aware

from app import db
from app.models.ai_chat_crud_approval import AIChatCRUDApproval, ApprovalStatus
from app.models.user import User
from app.services.ai_data_interaction_service import AIDataInteractionService

logger = logging.getLogger(__name__)


class AIChatApprovalService:
    """
    Service for managing AI chat CRUD operation approvals.

    All CRUD operations detected in natural language chat messages are
    converted to pending approvals that require explicit user confirmation.
    """

    # Default expiration time for pending approvals (15 minutes)
    DEFAULT_EXPIRY_MINUTES = 15

    def __init__(self, user_id: Optional[int] = None):
        self.user_id = user_id
        self.logger = logging.getLogger(__name__)

    def create_pending_approval(
        self,
        operation_type: str,
        entity_type: str,
        original_command: str,
        operation_payload: Dict[str, Any],
        summary: str,
        entity_id: Optional[int] = None,
        chat_session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a pending approval for a CRUD operation.

        Args:
            operation_type: Type of operation (create, update, delete)
            entity_type: Type of entity being modified (capability, application, etc.)
            original_command: The natural language command that triggered this
            operation_payload: The data payload for the operation
            summary: Human-readable summary of what will happen
            entity_id: ID of entity (for update/delete operations)
            chat_session_id: Optional chat session identifier

        Returns:
            Dict with approval details and confirmation instructions
        """
        try:
            # ENT-042: Block anonymous CRUD — a None user_id creates unfilterable approvals.
            if not self.user_id:
                return {"success": False, "error": "Authentication required to request CRUD operations"}

            # Create approval record
            approval = AIChatCRUDApproval(
                user_id=self.user_id,
                operation_type=operation_type,
                entity_type=entity_type,
                entity_id=entity_id,
                original_command=original_command,
                operation_payload=json.dumps(operation_payload),
                summary=summary,
                status=ApprovalStatus.PENDING,
                expires_at=datetime.utcnow() + timedelta(minutes=self.DEFAULT_EXPIRY_MINUTES),
                chat_session_id=chat_session_id,
            )

            db.session.add(approval)
            db.session.commit()

            self.logger.info(
                f"Created pending approval {approval.id} for {operation_type} {entity_type}"
            )

            return {
                "success": True,
                "approval_id": approval.id,
                "status": "pending_approval",
                "operation_type": operation_type,
                "entity_type": entity_type,
                "summary": summary,
                "expires_at": approval.expires_at.isoformat(),
                "message": (
                    f"I've prepared a {operation_type} operation for {entity_type}. "
                    f"Please review and confirm:\n\n"
                    f"**Summary:** {summary}\n\n"
                    f"**Action Required:** Type 'confirm {approval.id}' to execute, "
                    f"or 'reject {approval.id}' to cancel. "
                    f"This request expires in {self.DEFAULT_EXPIRY_MINUTES} minutes."
                ),
                "requires_approval": True,
            }

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to create approval: {e}")
            return {
                "success": False,
                "error": f"Failed to create approval: {str(e)}",
            }

    def approve_and_execute(
        self, approval_id: int, approving_user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Approve and execute a pending CRUD operation.

        Args:
            approval_id: ID of the approval to execute
            approving_user_id: User ID of the approver (may differ from requester)

        Returns:
            Dict with execution result
        """
        try:
            approval = AIChatCRUDApproval.query.get(approval_id)

            if not approval:
                return {"success": False, "error": f"Approval {approval_id} not found"}

            # ENT-042: Require an authenticated user to avoid None==None bypass.
            if not self.user_id:
                return {"success": False, "error": "Authentication required to approve CRUD operations"}

            # Verify ownership — both IDs must be non-None and equal.
            if approval.user_id is None or approval.user_id != self.user_id:
                return {
                    "success": False,
                    "error": "You can only approve your own pending operations",
                }

            # Check status
            if approval.status != ApprovalStatus.PENDING:
                return {
                    "success": False,
                    "error": f"Approval is already {approval.status.value}",
                }

            # Check expiration
            if approval.is_expired():
                approval.status = ApprovalStatus.EXPIRED
                db.session.commit()
                return {"success": False, "error": "Approval has expired. Please submit a new request."}

            # Parse operation payload
            try:
                payload = json.loads(approval.operation_payload)
            except json.JSONDecodeError:
                return {"success": False, "error": "Invalid operation payload"}

            # Execute the operation
            data_service = AIDataInteractionService(user_id=self.user_id)

            if approval.operation_type == "create":
                if approval.entity_type == "capability":
                    result = data_service.create_capability(payload)
                elif approval.entity_type == "application":
                    result = data_service.create_application(payload)
                elif approval.entity_type == "vendor":
                    result = data_service.create_vendor(payload)
                elif approval.entity_type == "capability_mapping":
                    result = data_service.create_capability_mapping(payload)
                elif approval.entity_type == "work_package":
                    result = data_service.create_work_package(payload)
                else:
                    return {"success": False, "error": f"Unknown entity type: {approval.entity_type}"}

            elif approval.operation_type == "link":
                if approval.entity_type == "application_capability_mapping":
                    result = data_service.link_application_to_capability(payload)
                else:
                    return {"success": False, "error": f"Unknown link entity type: {approval.entity_type}"}

            elif approval.operation_type == "update":
                entity_id = approval.entity_id
                if approval.entity_type == "capability":
                    result = data_service.update_capability(entity_id, payload)
                elif approval.entity_type == "application":
                    result = data_service.update_application(entity_id, payload)
                elif approval.entity_type == "vendor":
                    result = data_service.update_vendor(entity_id, payload)
                else:
                    return {"success": False, "error": f"Unknown entity type: {approval.entity_type}"}

            elif approval.operation_type == "delete":
                # Hard delete — admin-only at execution time (double guard)
                actor = User.query.get(self.user_id)
                if not actor or not actor.is_admin():
                    return {"success": False, "error": "Delete operations require administrator privileges"}
                entity_id = approval.entity_id
                if approval.entity_type == "capability":
                    result = data_service.delete_capability(entity_id)
                elif approval.entity_type == "application":
                    result = data_service.delete_application(entity_id)
                elif approval.entity_type == "vendor":
                    result = data_service.delete_vendor(entity_id)
                else:
                    return {"success": False, "error": f"Unknown entity type for delete: {approval.entity_type}"}

            else:
                return {
                    "success": False,
                    "error": f"Unsupported operation type: {approval.operation_type}",
                }

            # Update approval record
            if result.get("success"):
                approval.approve(approving_user_id or self.user_id)
                approval.execute(result)
                db.session.commit()

                self.logger.info(f"Approved and executed operation {approval_id}")

                return {
                    "success": True,
                    "message": f"{approval.operation_type} operation executed successfully.",
                    "result": result,
                    "approval_id": approval_id,
                }
            else:
                # Execution failed but we still mark it as attempted
                approval.execute(result)
                db.session.commit()

                return {
                    "success": False,
                    "error": result.get("error", "Operation failed"),
                    "approval_id": approval_id,
                }

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to approve/execute operation {approval_id}: {e}")
            return {"success": False, "error": f"Execution failed: {str(e)}"}

    def reject_approval(self, approval_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Reject a pending approval.

        Args:
            approval_id: ID of the approval to reject
            reason: Optional reason for rejection

        Returns:
            Dict with rejection result
        """
        try:
            approval = AIChatCRUDApproval.query.get(approval_id)

            if not approval:
                return {"success": False, "error": f"Approval {approval_id} not found"}

            # Verify ownership
            if approval.user_id != self.user_id:
                return {
                    "success": False,
                    "error": "You can only reject your own pending operations",
                }

            # Check status
            if approval.status != ApprovalStatus.PENDING:
                return {
                    "success": False,
                    "error": f"Approval is already {approval.status.value}",
                }

            approval.reject(reason)
            db.session.commit()

            self.logger.info(f"Rejected approval {approval_id}")

            return {
                "success": True,
                "message": f"{approval.operation_type} operation rejected.",
                "approval_id": approval_id,
            }

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to reject approval {approval_id}: {e}")
            return {"success": False, "error": f"Rejection failed: {str(e)}"}

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """
        Get all pending approvals for the current user.

        Returns:
            List of pending approval dictionaries
        """
        approvals = AIChatCRUDApproval.get_pending_for_user(self.user_id)
        return [approval.to_dict() for approval in approvals]

    def check_for_confirmation_command(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Check if a chat message is a confirmation command.

        Supports:
        - "confirm [approval_id]"
        - "approve [approval_id]"
        - "reject [approval_id]"
        - "cancel [approval_id]"

        Args:
            message: The chat message to check

        Returns:
            Dict with action and approval_id if matched, None otherwise
        """
        import re

        message = message.strip().lower()

        # Match confirmation commands
        confirm_patterns = [
            r'^confirm\s+(\d+)',
            r'^approve\s+(\d+)',
            r'^yes\s+(\d+)',
        ]

        for pattern in confirm_patterns:
            match = re.match(pattern, message)
            if match:
                return {
                    "action": "confirm",
                    "approval_id": int(match.group(1)),
                }

        # Match rejection commands
        reject_patterns = [
            r'^reject\s+(\d+)',
            r'^cancel\s+(\d+)',
            r'^no\s+(\d+)',
        ]

        for pattern in reject_patterns:
            match = re.match(pattern, message)
            if match:
                return {
                    "action": "reject",
                    "approval_id": int(match.group(1)),
                }

        return None
