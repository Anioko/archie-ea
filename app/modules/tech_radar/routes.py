"""Routes for the Tech Radar module (ARCH-124).

Blueprint: tech_radar_bp, url_prefix="/technology/radar".
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app.decorators import require_roles
from app.models.tech_radar import RADAR_RING_LABELS, RADAR_RINGS

from . import service

logger = logging.getLogger(__name__)

tech_radar_bp = Blueprint("tech_radar", __name__, url_prefix="/technology/radar")


@tech_radar_bp.route("/")
@login_required
def index():
    """The radar: real Technology-layer ArchiMateElements, grouped by their
    architect-set adopt/trial/assess/hold ring. Empty state when the tenant
    has no technology-layer elements at all."""
    state = service.radar_state()
    return render_template(
        "tech_radar/index.html",
        state=state,
        rings=RADAR_RINGS,
        ring_labels=RADAR_RING_LABELS,
    )


@tech_radar_bp.route("/api")
@login_required
def api_state():
    state = service.radar_state()
    return jsonify({
        "success": True,
        "total_candidates": state["total_candidates"],
        "classified_count": state["classified_count"],
        "unclassified_count": len(state["unclassified"]),
        "rings": {
            ring: [
                {**row["entry"].to_dict()}
                for row in rows
            ]
            for ring, rows in state["rings"].items()
        },
    })


@tech_radar_bp.route("/classify", methods=["POST"])
@login_required
@require_roles("admin", "administrator", "architect", "enterprise_architect", "cto", "platform_admin")
def classify():
    """Set/update the ring for one Technology-layer element. Rejects
    anything that is not a real, already-modelled technology element —
    a radar entry can never be created out of thin air."""
    element_id = request.form.get("archimate_element_id", type=int)
    ring = (request.form.get("ring") or "").strip().lower()
    rationale = request.form.get("rationale") or ""

    if not element_id or ring not in RADAR_RINGS:
        return jsonify({"success": False, "error": "archimate_element_id and a valid ring are required"}), 400

    try:
        entry = service.classify(element_id, ring, rationale, current_user.id)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception:  # noqa: BLE001
        logger.exception("tech radar classify failed for element %s", element_id)
        return jsonify({"success": False, "error": "Could not save classification"}), 500

    return jsonify({"success": True, "entry": entry.to_dict()})
