"""Business Model Canvas AI assist: draft one block at a time.

Registered onto business_model_bp via a side-effect import at the bottom
of routes.py, matching the pattern used by
app/modules/architecture/routes/arb_review_ai_routes.py. Purely advisory:
this endpoint returns a drafted block and writes nothing — saving the
draft goes through the canvas's existing POST .../api/block write path.
"""

from __future__ import annotations

import logging

from flask import jsonify, request
from flask_login import login_required

from app.models.business_model import BusinessModelCanvas
from app.modules.business_model_canvas.ai_service import (
    BusinessModelAIDraftError,
    generate_block_draft,
)
from app.modules.business_model_canvas.routes import business_model_bp
from app.services.feature_flag_service import FeatureFlagService

logger = logging.getLogger(__name__)


@business_model_bp.route("/api/<int:canvas_id>/ai-draft-block", methods=["POST"])
@login_required
def ai_draft_block(canvas_id):
    """POST /business-model/api/<id>/ai-draft-block

    Body: {"block": <one of the 9 real block keys>}. Drafts content for
    that block from the canvas's other filled blocks plus cheap
    app/capability aggregates. Nothing is written — the user saves the
    draft via the block's existing inline editor.
    """
    feature_guard = FeatureFlagService.require_ai_for_route(
        FeatureFlagService.FEATURE_SUGGESTIONS,
        endpoint_name="business_model.ai_draft_block",
    )
    if feature_guard:
        return feature_guard

    # ORM query so TenantMixin's do_orm_execute filter applies — a canvas
    # belonging to another org 404s exactly like an unknown id.
    canvas = BusinessModelCanvas.query.get_or_404(canvas_id)

    payload = request.get_json(silent=True) or {}
    block_key = payload.get("block")

    try:
        draft = generate_block_draft(canvas, block_key)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except BusinessModelAIDraftError as e:
        logger.warning("BMC block draft unparseable for canvas %s: %s", canvas_id, e)
        return jsonify({"error": f"AI draft failed: {e}"}), 502
    except Exception as e:
        logger.exception("BMC block draft generation failed for canvas %s", canvas_id)
        return jsonify({"error": f"AI draft failed: {e}"}), 502

    return jsonify({"draft": draft})
