"""Routes for the Business Model Canvas + Operating Model module.

Blueprint: business_model_bp, url_prefix="/business-model".
Index endpoint (linked from the sidebar by the orchestrator post-merge):
    business_model.index
"""

import logging

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

# Destructive and mutating routes were guarded by @login_required only, so any
# authenticated user could delete another user's records. Matches the gating
# already used by app/modules/capabilities/routes/enterprise_crud_routes.py.
from app.decorators import require_roles

from app.models.business_model import CANVAS_BLOCKS, OPERATING_MODEL_TYPES
from app.utils.api_response import error_response, not_found_response, success_response

from . import service

logger = logging.getLogger(__name__)

business_model_bp = Blueprint(
    "business_model", __name__, url_prefix="/business-model"
)


@business_model_bp.route("/")
@login_required
def index():
    """List all Business Model Canvases for the current tenant."""
    canvases = service.list_canvases()
    return render_template(
        "business_model/index.html",
        canvases=canvases,
        operating_model_types=OPERATING_MODEL_TYPES,
    )


@business_model_bp.route("/create", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def create():
    """Create a new canvas and redirect to its detail/canvas view."""
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    operating_model_type = request.form.get("operating_model_type") or None

    try:
        canvas = service.create_canvas(
            name=name or "Untitled Canvas",
            description=description,
            operating_model_type=operating_model_type,
        )
    except ValueError as exc:
        logger.warning("Invalid canvas create payload: %s", exc)
        return redirect(url_for("business_model.index"))

    return redirect(url_for("business_model.detail", canvas_id=canvas.id))


@business_model_bp.route("/<int:canvas_id>")
@login_required
def detail(canvas_id):
    """The 9-box Business Model Canvas view for a single canvas."""
    canvas = service.get_canvas_or_none(canvas_id)
    if canvas is None:
        return render_template("business_model/not_found.html", canvas_id=canvas_id), 404

    return render_template(
        "business_model/detail.html",
        canvas=canvas,
        canvas_blocks=CANVAS_BLOCKS,
        operating_model_types=OPERATING_MODEL_TYPES,
    )


@business_model_bp.route("/<int:canvas_id>/update", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def update_canvas(canvas_id):
    """Update canvas name / description / operating model type (JSON API)."""
    canvas = service.get_canvas_or_none(canvas_id)
    if canvas is None:
        return not_found_response("Business Model Canvas")

    payload = request.get_json(silent=True) or request.form
    name = payload.get("name")
    description = payload.get("description")
    operating_model_type = payload.get("operating_model_type")

    try:
        canvas = service.update_canvas_meta(
            canvas,
            name=name,
            description=description,
            operating_model_type=operating_model_type,
        )
    except ValueError as exc:
        return error_response(str(exc), code="VALIDATION_ERROR", status_code=400)

    return success_response(canvas.to_dict())


@business_model_bp.route("/<int:canvas_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete_canvas(canvas_id):
    """Delete a canvas."""
    canvas = service.get_canvas_or_none(canvas_id)
    if canvas is None:
        return not_found_response("Business Model Canvas")

    service.delete_canvas(canvas)
    return redirect(url_for("business_model.index"))


@business_model_bp.route("/<int:canvas_id>/api/block", methods=["POST", "PUT"])
@login_required
@require_roles("admin", "architect", "business_architect")
def save_block(canvas_id):
    """Save one of the 9 Business Model Canvas blocks.

    Payload: {"block": "key_partners", "content": "..."}
    """
    canvas = service.get_canvas_or_none(canvas_id)
    if canvas is None:
        return not_found_response("Business Model Canvas")

    payload = request.get_json(silent=True) or {}
    block_key = payload.get("block")
    content = payload.get("content", "")

    if not block_key:
        return error_response("Missing 'block' field", code="VALIDATION_ERROR", status_code=400)

    try:
        canvas = service.save_block(canvas, block_key, content)
    except ValueError as exc:
        return error_response(str(exc), code="VALIDATION_ERROR", status_code=400)

    return success_response(canvas.to_dict())


# Import AI block-draft route — adds POST /api/<id>/ai-draft-block to this
# blueprint (side-effect import), matching the
# app/modules/architecture/routes/arb_review_ai_routes.py pattern.
from app.modules.business_model_canvas import ai_routes  # noqa: F401, E402  # dead-code-ok
