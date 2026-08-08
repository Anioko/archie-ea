"""AI chat approval workflow routes."""

from flask import jsonify, request
from flask_login import current_user, login_required

from app.modules.ai_chat.services.ai_chat_approval_service import AIChatApprovalService

from . import unified_ai_chat_bp


def _approval_service():
    return AIChatApprovalService(current_user.id)


@unified_ai_chat_bp.route("/approvals/pending", methods=["GET"])
@login_required
def pending_approvals():
    approvals = _approval_service().get_pending_approvals()
    return jsonify({"success": True, "approvals": approvals})


@unified_ai_chat_bp.route("/approvals/<int:approval_id>/approve", methods=["POST"])
@login_required
def approve_pending_approval(approval_id):
    # approve_and_execute, not approve_approval: the latter has never existed on
    # AIChatApprovalService, so every approve click from the /ai-chat modal
    # (static/js/ai_chat/approval_modal.js) raised AttributeError and 500'd. The
    # queue itself worked - the blueprint page reaches it via a different route -
    # so the flow was sound and only this call site was wrong.
    result = _approval_service().approve_and_execute(approval_id, current_user.id)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@unified_ai_chat_bp.route("/approvals/<int:approval_id>/reject", methods=["POST"])
@login_required
def reject_pending_approval(approval_id):
    payload = request.get_json(silent=True) or {}
    reason = payload.get("reason")
    result = _approval_service().reject_approval(approval_id, reason)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


__all__ = [
    "pending_approvals",
    "approve_pending_approval",
    "reject_pending_approval",
]
