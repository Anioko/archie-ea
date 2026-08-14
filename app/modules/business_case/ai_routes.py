"""Business Case AI assist: draft one document section at a time.

Registered onto business_case_bp via a side-effect import at the bottom of
routes.py, matching the pattern used by
app/modules/architecture/routes/arb_review_ai_routes.py. Purely advisory:
this endpoint returns a drafted section and writes nothing — saving the
draft goes through the case's existing POST .../api/field write path.
"""

from __future__ import annotations

import logging

from flask import jsonify, request
from flask_login import login_required

from app.models.business_case import BusinessCase
from app.modules.business_case.ai_service import (
    BusinessCaseAIDraftError,
    generate_section_draft,
)
from app.modules.business_case.routes import business_case_bp
from app.services.feature_flag_service import FeatureFlagService

logger = logging.getLogger(__name__)


@business_case_bp.route("/api/<int:business_case_id>/ai-draft-section", methods=["POST"])
@login_required
def ai_draft_section(business_case_id):
    """POST /business-case/api/<id>/ai-draft-section

    Body: {"section": <real section key from the business-case model>}.
    Drafts content for that section from the case's other filled sections,
    its linked entities, and its own already-entered financial figures.
    Nothing is written — the user saves the draft via the section's
    existing inline editor.
    """
    feature_guard = FeatureFlagService.require_ai_for_route(
        FeatureFlagService.FEATURE_SUGGESTIONS,
        endpoint_name="business_case.ai_draft_section",
    )
    if feature_guard:
        return feature_guard

    # ORM query so TenantMixin's do_orm_execute filter applies — a case
    # belonging to another org 404s exactly like an unknown id.
    business_case = BusinessCase.query.get_or_404(business_case_id)

    payload = request.get_json(silent=True) or {}
    section_key = payload.get("section")

    try:
        draft = generate_section_draft(business_case, section_key)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except BusinessCaseAIDraftError as e:
        logger.warning(
            "Business case section draft unparseable for case %s: %s", business_case_id, e
        )
        return jsonify({"error": f"AI draft failed: {e}"}), 502
    except Exception as e:
        logger.exception(
            "Business case section draft generation failed for case %s", business_case_id
        )
        return jsonify({"error": f"AI draft failed: {e}"}), 502

    return jsonify({"draft": draft})
