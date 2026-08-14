"""ARB queue clerk: AI assist for triage, session agenda and minutes drafts.

The reviewer side already gets an AI pre-brief per review
(arb_review_ai_routes.py). The board-secretary side had nothing: no help
prioritising the raw pending queue, no agenda draft for an upcoming
session, no minutes draft from decisions already recorded. These three
endpoints are purely advisory — nothing here is written back to any review
or session. A human still schedules sessions, orders agendas, and records
minutes through the existing controls.

Registered onto arb_bp via a side-effect import in arb_routes.py, matching
the existing arb_review_ai_routes.py / arb_decision_routes.py pattern.
"""
from __future__ import annotations

import logging

from flask import jsonify
from flask_login import login_required

from app.modules.architecture.routes.arb_routes import arb_bp
from app.models.architecture_review_board import ARBReviewItem, ArchitectureReviewBoard
from app.modules.architecture.services.arb_queue_ai_service import (
    ARBQueueAIError,
    MAX_QUEUE_ITEMS,
    generate_queue_triage,
    generate_session_agenda,
    generate_session_minutes,
    get_decided_review_items,
)
from app.services.feature_flag_service import FeatureFlagService

logger = logging.getLogger(__name__)


@arb_bp.route("/api/queue/ai-triage", methods=["POST"])
@login_required
def ai_queue_triage():
    """POST /arb/api/queue/ai-triage

    Generates an AI triage of the pending ARB queue: a summary, a
    complexity assessment per pending review, and a suggested review order.
    Advisory only — nothing here is persisted or reorders the real queue.
    """
    feature_guard = FeatureFlagService.require_ai_for_route(
        FeatureFlagService.FEATURE_SUGGESTIONS,
        endpoint_name="arb.ai_queue_triage",
    )
    if feature_guard:
        return feature_guard

    # TenantMixin's do_orm_execute filter scopes this to the current org.
    review_items = (
        ARBReviewItem.query.filter(ARBReviewItem.status.in_(["pending", "submitted"]))
        .order_by(ARBReviewItem.created_at.asc())
        .limit(MAX_QUEUE_ITEMS)
        .all()
    )

    if not review_items:
        return jsonify({"triage": None, "message": "No pending reviews"})

    try:
        triage = generate_queue_triage(review_items)
    except ARBQueueAIError as e:
        logger.warning("ARB queue triage unparseable: %s", e)
        return jsonify({"error": f"AI triage failed: {e}"}), 502
    except Exception as e:
        logger.exception("ARB queue triage generation failed")
        return jsonify({"error": f"AI triage failed: {e}"}), 502

    return jsonify({"triage": triage})


@arb_bp.route("/api/sessions/<int:session_id>/ai-agenda", methods=["POST"])
@login_required
def ai_session_agenda(session_id):
    """POST /arb/api/sessions/<id>/ai-agenda

    Generates an AI agenda draft for an ARB session from the session's own
    fields and its linked review items. Advisory only — nothing here is
    persisted as the session's real agenda.
    """
    feature_guard = FeatureFlagService.require_ai_for_route(
        FeatureFlagService.FEATURE_SUGGESTIONS,
        endpoint_name="arb.ai_session_agenda",
    )
    if feature_guard:
        return feature_guard

    session = ArchitectureReviewBoard.query.get_or_404(session_id)

    try:
        agenda = generate_session_agenda(session)
    except ARBQueueAIError as e:
        logger.warning("ARB session agenda unparseable for session %s: %s", session_id, e)
        return jsonify({"error": f"AI agenda draft failed: {e}"}), 502
    except Exception as e:
        logger.exception("ARB session agenda generation failed for session %s", session_id)
        return jsonify({"error": f"AI agenda draft failed: {e}"}), 502

    return jsonify({"agenda": agenda})


@arb_bp.route("/api/sessions/<int:session_id>/ai-minutes-draft", methods=["POST"])
@login_required
def ai_session_minutes_draft(session_id):
    """POST /arb/api/sessions/<id>/ai-minutes-draft

    Generates an AI minutes draft for an ARB session from decisions already
    recorded on the session's review items. Advisory only — the draft is
    rendered into a copyable textarea by the caller and is never persisted
    as the session's real minutes.
    """
    feature_guard = FeatureFlagService.require_ai_for_route(
        FeatureFlagService.FEATURE_SUGGESTIONS,
        endpoint_name="arb.ai_session_minutes_draft",
    )
    if feature_guard:
        return feature_guard

    session = ArchitectureReviewBoard.query.get_or_404(session_id)

    decided_items = get_decided_review_items(session)
    if not decided_items:
        return jsonify({"error": "No recorded decisions to draft minutes from"}), 409

    try:
        minutes = generate_session_minutes(session, decided_items)
    except ARBQueueAIError as e:
        logger.warning("ARB session minutes draft unparseable for session %s: %s", session_id, e)
        return jsonify({"error": f"AI minutes draft failed: {e}"}), 502
    except Exception as e:
        logger.exception("ARB session minutes draft generation failed for session %s", session_id)
        return jsonify({"error": f"AI minutes draft failed: {e}"}), 502

    return jsonify({"minutes": minutes})
