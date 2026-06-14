"""
AI metrics route for A95-012: routine decisions automated + solutions touch-only-for-review.
"""
from datetime import datetime

from flask import jsonify
from flask_login import login_required

from . import unified_ai_chat_bp


@unified_ai_chat_bp.route("/metrics", methods=["GET"])
@login_required
def ai_metrics():
    """Return AI automation metrics."""
    from app.modules.ai_chat.approval_gate import get_ai_action_count

    try:
        from app.models import Solution
        ai_solutions = Solution.query.filter_by(ai_generated=True).count()
    except Exception:
        ai_solutions = 0

    return jsonify({
        "routine_decisions_automated": get_ai_action_count(),
        "solutions_touch_only_for_review": ai_solutions,
        "timestamp": datetime.utcnow().isoformat(),
    })
