"""Value-stream AI assist: BIZBOK capability x stage mapping suggestions.

Registered onto the ``value_stream`` blueprint via a side-effect import in
value_stream_routes.py, matching the pattern used by
app/modules/architecture/routes/arb_review_ai_routes.py. Purely advisory:
this endpoint returns suggested (stage, capability) pairs and writes
nothing — applying a suggestion in the UI goes through the grid's existing
POST /value-streams/api/mapping write path.
"""

from __future__ import annotations

import logging

from flask import jsonify
from flask_login import login_required

from app.models.unified_capability import ValueStream
from app.modules.capabilities.routes.value_stream_routes import value_stream
from app.modules.capabilities.services.value_stream_ai_service import (
    ValueStreamAISuggestError,
    generate_stage_mapping_suggestions,
)
from app.services.feature_flag_service import FeatureFlagService

logger = logging.getLogger(__name__)


@value_stream.route("/api/<int:stream_id>/ai-suggest-mappings", methods=["POST"])
@login_required
def ai_suggest_mappings(stream_id):
    """POST /value-streams/api/<id>/ai-suggest-mappings

    Suggests candidate capability x stage mappings for this value stream,
    drawn from the stream's real stages and this org's real capability
    catalog. Nothing is written — the reviewer applies a suggestion via the
    grid's existing cell-set endpoint.
    """
    feature_guard = FeatureFlagService.require_ai_for_route(
        FeatureFlagService.FEATURE_SUGGESTIONS,
        endpoint_name="value_stream.ai_suggest_mappings",
    )
    if feature_guard:
        return feature_guard

    # ORM query so TenantMixin's do_orm_execute filter applies — a stream
    # belonging to another org 404s exactly like an unknown id.
    stream = ValueStream.query.get_or_404(stream_id)

    try:
        result = generate_stage_mapping_suggestions(stream)
    except ValueStreamAISuggestError as e:
        logger.warning(
            "Value stream mapping suggestions unparseable for stream %s: %s", stream_id, e
        )
        return jsonify({"error": f"AI suggestion failed: {e}"}), 502
    except Exception as e:
        logger.exception(
            "Value stream mapping suggestion generation failed for stream %s", stream_id
        )
        return jsonify({"error": f"AI suggestion failed: {e}"}), 502

    return jsonify(result)
