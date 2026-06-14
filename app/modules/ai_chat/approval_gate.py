"""
Approval gate for AI-originated CRUD operations (A95-008).

When REQUIRE_AI_APPROVAL=true, any endpoint decorated with @require_ai_approval
returns HTTP 202 Accepted with a pending_approval payload instead of executing
the write immediately.  A human operator must then approve/reject via the
/approvals/ dashboard (approval_routes.py / AIChatApprovalService).
"""

import logging
from functools import wraps

from flask import current_app, jsonify, request

_ai_action_logger = logging.getLogger('ai_originated_actions')
_ai_action_count = 0  # incremented by tag_ai_action


def tag_ai_action(action_type: str, entity_type: str, entity_id=None, metadata: dict = None):
    """Log an AI-originated action for the 'routine decisions automated' metric."""
    global _ai_action_count
    _ai_action_count += 1
    _ai_action_logger.info(
        'ai_action',
        extra={
            'ai_originated': True,
            'action_type': action_type,
            'entity_type': entity_type,
            'entity_id': str(entity_id) if entity_id else None,
            'metadata': metadata or {},
        }
    )


def get_ai_action_count():
    """Return the number of AI-originated actions recorded in this process."""
    return _ai_action_count


def require_ai_approval(f):
    """Decorator: gate AI-originated CRUD behind human approval.

    When ``REQUIRE_AI_APPROVAL`` is ``True`` in the Flask config the decorated
    view is *not* executed.  Instead a 202 response is returned containing the
    ``pending_approval`` payload so the UI can surface it in the approval
    dashboard.  When the flag is ``False`` (the default) the view runs normally.

    Either way, the action is tagged via ``tag_ai_action`` for the
    'routine decisions automated' metric (A95-009).
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        if current_app.config.get("REQUIRE_AI_APPROVAL", False):
            payload = request.get_json(silent=True) or {}
            return (
                jsonify(
                    {
                        "status": "pending_approval",
                        "message": (
                            "AI-originated action requires human approval "
                            "before execution."
                        ),
                        "action": request.endpoint,
                        "payload": payload,
                        "ai_originated": True,
                    }
                ),
                202,
            )
        tag_ai_action(
            action_type=request.endpoint,
            entity_type='unknown',
            metadata={'method': request.method, 'path': request.path},
        )
        return f(*args, **kwargs)

    return decorated
