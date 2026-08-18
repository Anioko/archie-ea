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


from app import db
from app.models.ai_chat_crud_approval import AIChatApprovalAuditLog, AIChatCRUDApproval, ApprovalStatus
from app.models.user import User
from app.services.ai_data_interaction_service import AIDataInteractionService
from app.utils.duplicate_guard import normalize_name

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

    # ------------------------------------------------------------------ #
    # Audit trail (ARCH-022)                                              #
    # ------------------------------------------------------------------ #

    def _audit(
        self,
        approval: AIChatCRUDApproval,
        event: str,
        to_status: str,
        actor_user_id: Optional[int],
        from_status: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Append one immutable transition row. Never updates, never deletes.

        Refuses (raises) rather than silently writing a system-actor row for
        "approved" or "executed" — those two events must be traceable to a
        human. This is what lets application code guarantee approved_by_id is
        never null on anything that reached an executed state: the guarantee
        is enforced here, at the one place every transition passes through,
        not re-implemented at each call site.
        """
        if event in ("approved", "executed") and not actor_user_id:
            raise ValueError(
                f"Refusing to record '{event}' on approval {approval.id} with no actor_user_id "
                "— execution requires a human approver."
            )
        db.session.add(
            AIChatApprovalAuditLog(
                approval_id=approval.id,
                from_status=from_status,
                to_status=to_status,
                event=event,
                actor_user_id=actor_user_id,
                actor_type="user" if actor_user_id else "system",
                reason=reason,
            )
        )

    # ------------------------------------------------------------------ #
    # Duplicate detection (ARCH-021)                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalized_payload_key(operation_type: str, entity_type: str, payload: Dict[str, Any]) -> str:
        """A comparison key for 'is this the same operation, worded differently'.

        Reuses duplicate_guard.normalize_name (casefold + whitespace collapse)
        field-by-field rather than a byte-for-byte JSON compare, so two payloads
        differing only in description wording or key order still match — which
        is exactly the ARCH-021 case (two approvals for the same operation that
        differed only in description wording).
        """
        normalized_fields = {
            k: normalize_name(v) if isinstance(v, str) else v
            for k, v in sorted(payload.items())
            if k not in ("description", "summary", "original_command", "rationale")
        }
        return f"{operation_type}:{entity_type}:{json.dumps(normalized_fields, sort_keys=True, default=str)}"

    def find_duplicate_pending(
        self, operation_type: str, entity_type: str, payload: Dict[str, Any]
    ) -> Optional[AIChatCRUDApproval]:
        """An existing PENDING approval for the same operation, or None."""
        if not self.user_id:
            return None
        candidate_key = self._normalized_payload_key(operation_type, entity_type, payload)
        pending = (
            AIChatCRUDApproval.query.filter_by(
                user_id=self.user_id,
                operation_type=operation_type,
                entity_type=entity_type,
                status=ApprovalStatus.PENDING,
            )
            .filter(AIChatCRUDApproval.expires_at > datetime.utcnow())
            .all()
        )
        for existing in pending:
            try:
                existing_payload = json.loads(existing.operation_payload)
            except (json.JSONDecodeError, TypeError):
                continue
            existing_key = self._normalized_payload_key(operation_type, entity_type, existing_payload)
            if existing_key == candidate_key:
                return existing
        return None

    def create_pending_approval(
        self,
        operation_type: str,
        entity_type: str,
        original_command: str,
        operation_payload: Dict[str, Any],
        summary: str,
        entity_id: Optional[int] = None,
        chat_session_id: Optional[str] = None,
        agent_turn_id: Optional[str] = None,
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
            chat_session_id: Chat session identifier — ARCH-020. Every call site in
                this codebase now has one available (multi_domain_chat_service.py's
                self._stable_session_id, or AgentRunner.chat_session_id) and must
                pass it; a None here is what let approvals float free of the
                conversation that raised them.
            agent_turn_id: Identifier for the specific agent turn/run that raised
                this approval, distinct from the session (a conversation, ARCH-020).

        Returns:
            Dict with approval details and confirmation instructions
        """
        try:
            # ENT-042: Block anonymous CRUD — a None user_id creates unfilterable approvals.
            if not self.user_id:
                return {"success": False, "error": "Authentication required to request CRUD operations"}

            # ARCH-021: reuse an existing pending approval for the same operation
            # rather than creating a duplicate. Surfaced to the caller/agent so it
            # can tell the user "already pending" instead of silently re-queuing.
            duplicate = self.find_duplicate_pending(operation_type, entity_type, operation_payload)
            if duplicate:
                self.logger.info(
                    f"Duplicate pending approval detected for {operation_type} {entity_type}; "
                    f"reusing approval {duplicate.id} instead of creating a new one"
                )
                return {
                    "success": True,
                    "approval_id": duplicate.id,
                    "status": "pending_approval",
                    "operation_type": duplicate.operation_type,
                    "entity_type": duplicate.entity_type,
                    "summary": duplicate.summary,
                    "expires_at": duplicate.expires_at.isoformat(),
                    "duplicate_of_existing": True,
                    "message": (
                        f"This is already pending as approval {duplicate.id} "
                        f"(\"{duplicate.summary}\"). Type 'confirm {duplicate.id}' to execute, "
                        f"or 'reject {duplicate.id}' to cancel — I won't queue it twice."
                    ),
                    "requires_approval": True,
                }

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
                agent_turn_id=agent_turn_id,
            )

            db.session.add(approval)
            db.session.flush()
            db.session.add(
                AIChatApprovalAuditLog(
                    approval_id=approval.id,
                    from_status=None,
                    to_status=ApprovalStatus.PENDING.value,
                    event="created",
                    actor_user_id=self.user_id,
                    actor_type="user",
                )
            )
            db.session.commit()

            self.logger.info(
                f"Created pending approval {approval.id} for {operation_type} {entity_type} "
                f"(chat_session_id={chat_session_id!r}, agent_turn_id={agent_turn_id!r})"
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

            # Check expiration. An expiry transition is SYSTEM-initiated and must
            # never also execute the operation (ARCH-022) — it only ever moves
            # PENDING -> EXPIRED and returns, it never falls through to the
            # execution dispatch below.
            if approval.is_expired():
                approval.status = ApprovalStatus.EXPIRED
                db.session.add(
                    AIChatApprovalAuditLog(
                        approval_id=approval.id,
                        from_status=ApprovalStatus.PENDING.value,
                        to_status=ApprovalStatus.EXPIRED.value,
                        event="expired",
                        actor_user_id=None,
                        actor_type="system",
                        reason="expires_at passed at approval attempt",
                    )
                )
                db.session.commit()
                return {"success": False, "error": "Approval has expired. Please submit a new request."}

            # ARCH-022: execution is REFUSED without a resolvable human approver.
            # approving_user_id may be explicitly None from a caller; fall back to
            # self.user_id (already required above), but never proceed with both
            # unset — that is precisely the "approved_by_id: null reached
            # executed" defect.
            effective_approver_id = approving_user_id or self.user_id
            if not effective_approver_id:
                db.session.add(
                    AIChatApprovalAuditLog(
                        approval_id=approval.id,
                        from_status=ApprovalStatus.PENDING.value,
                        to_status=ApprovalStatus.PENDING.value,
                        event="execution_refused",
                        actor_user_id=None,
                        actor_type="system",
                        reason="no resolvable approving user id",
                    )
                )
                db.session.commit()
                return {"success": False, "error": "Execution refused: no approving user identified"}

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

            elif approval.operation_type == "tool_use":
                # AgentRunner._queue_approval (agent_runner.py) writes exactly this
                # operation_type for every queued agent tool call — both the
                # always-approve tier (update_application_status,
                # submit_for_arb_review, generate_blueprint_narrative) and, since
                # the write-approval gate, any mutating tool queued because
                # auto-execute was off. entity_type carries the tool name and
                # operation_payload carries its arguments, exactly what ToolCall
                # needs. This mirrors POST /ai-chat/tools/approve/<id>
                # (chat_core.py: approve_tool_action) — same dispatch, same
                # ToolExecutor — so both approval surfaces (the blueprint panel's
                # dedicated endpoint and the main chat's approval modal, which
                # only ever calls this service) execute a queued tool call
                # identically instead of the main chat modal 400ing with
                # "Unsupported operation type: tool_use".
                from app.modules.ai_chat.tools.executor import ToolCall, ToolExecutor

                executor = ToolExecutor(self.user_id)
                tc = ToolCall(id=str(approval_id), name=approval.entity_type, arguments=payload)
                result = executor.execute(tc)

            elif approval.operation_type == "delete":
                # Hard delete — admin-only at execution time (double guard)
                # tenant-scoping-ok: self.user_id is the acting user's own id.
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
                approval.approve(effective_approver_id)
                self._audit(
                    approval,
                    event="approved",
                    to_status=ApprovalStatus.APPROVED.value,
                    actor_user_id=effective_approver_id,
                    from_status=ApprovalStatus.PENDING.value,
                )
                approval.execute(result)
                self._audit(
                    approval,
                    event="executed",
                    to_status=ApprovalStatus.APPROVED.value,
                    actor_user_id=effective_approver_id,
                    from_status=ApprovalStatus.APPROVED.value,
                )
                db.session.commit()

                self.logger.info(f"Approved and executed operation {approval_id} by user {effective_approver_id}")

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
            db.session.add(
                AIChatApprovalAuditLog(
                    approval_id=approval.id,
                    from_status=ApprovalStatus.PENDING.value,
                    to_status=ApprovalStatus.REJECTED.value,
                    event="rejected",
                    actor_user_id=self.user_id,
                    actor_type="user",
                    reason=reason,
                )
            )
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

    def get_pending_for_session(self, chat_session_id: Optional[str]) -> List[Dict[str, Any]]:
        """Pending approvals for this user within one chat session (ARCH-020).

        This is what lets the agent answer "is anything already pending for
        THIS conversation" before deciding whether to queue a new approval or
        point the user at the existing one.
        """
        approvals = AIChatCRUDApproval.get_pending_for_session(self.user_id, chat_session_id)
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

        # ARCH-020: id-less natural-language affirmations/rejections. "I approve,
        # proceed" has no approval_id in it, so the id-anchored patterns above
        # never match — the caller must resolve this against whatever is
        # PENDING for the current session (see resolve_natural_confirmation).
        #
        # These MUST full-match. An earlier version anchored only at the start
        # (r"^go ahead\b"), so an ordinary sentence that merely BEGAN with an
        # affirming word silently executed whatever write was pending:
        # "go ahead and explain the risk register", "approve it only after you
        # have checked X", "do it later" all matched. A prefix test is not a
        # safe test for consent on a path that mutates the system of record,
        # because the words after the prefix can reverse the meaning entirely.
        # The whole message must be the affirmation and nothing else.
        core_affirm = (
            r"(?:i\s+)?approve(?:\s+it|\s+this)?"
            r"|go\s+ahead"
            r"|(?:please\s+)?proceed"
            r"|confirm(?:\s+it|\s+this)?"
            r"|looks\s+good"
            r"|do\s+it"
            r"|yes"
        )
        core_deny = (
            r"(?:i\s+)?reject(?:\s+it|\s+this)?"
            r"|cancel(?:\s+it|\s+this)?"
            r"|don'?t\s+do\s+(?:it|that)"
            r"|no"
        )
        # Politeness and a second affirming clause ("I approve, proceed") are
        # allowed; anything carrying new instructions is not.
        _filler = r"(?:\s*[,.!;]\s*|\s+)(?:please|now|thanks|thank\s+you|ok|okay)"

        def _is_bare(core):
            pattern = (
                r"\s*(?:ok|okay)?\s*[,.!;]?\s*"
                r"(?:" + core + r")"
                r"(?:(?:\s*[,.!;]\s*|\s+)(?:" + core + r"))*"
                r"(?:" + _filler + r")*"
                r"\s*[.!]*\s*"
            )
            return re.fullmatch(pattern, message) is not None

        if _is_bare(core_affirm):
            return {"action": "confirm", "approval_id": None}

        if _is_bare(core_deny):
            return {"action": "reject", "approval_id": None}

        return None

    def resolve_natural_confirmation(
        self, confirmation: Dict[str, Any], chat_session_id: Optional[str]
    ) -> Dict[str, Any]:
        """Resolve an id-less confirmation (ARCH-020) against this session's queue.

        "I approve" carries no id, so it must never be treated as a brand-new
        request — the observed defect was exactly that: the agent, unable to
        see any approval state, queued a SECOND identical approval and asked
        again. This looks up what is actually PENDING for the user's current
        chat_session_id and acts on it, or tells the user plainly there is
        nothing to approve rather than silently re-queuing anything.
        """
        if confirmation.get("approval_id") is not None:
            if confirmation["action"] == "confirm":
                return self.approve_and_execute(confirmation["approval_id"])
            return self.reject_approval(confirmation["approval_id"])

        pending = AIChatCRUDApproval.get_pending_for_session(self.user_id, chat_session_id)
        if not pending:
            return {
                "success": False,
                "requires_approval": False,
                "message": (
                    "There's nothing pending for me to approve in this conversation right now."
                ),
            }
        if len(pending) > 1:
            listing = "\n".join(f"- {p.id}: {p.summary}" for p in pending)
            return {
                "success": False,
                "requires_approval": True,
                "message": (
                    "There's more than one pending approval in this conversation — "
                    f"tell me which one by id:\n{listing}"
                ),
            }
        target = pending[0]
        if confirmation["action"] == "confirm":
            return self.approve_and_execute(target.id)
        return self.reject_approval(target.id)
