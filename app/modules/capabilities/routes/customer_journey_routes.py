"""
Customer Journey routes.

Blueprint: customer_journey, url_prefix=/customer-journeys

The BIZBOK customer journey map — the third core map, alongside the capability
map and the value stream.

Pages:
- GET  /customer-journeys/                          index  - list journeys
- GET  /customer-journeys/<id>                      detail - stage swimlane +
                                                     sentiment curve +
                                                     capability x stage grid

Form posts:
- POST /customer-journeys/create
- POST /customer-journeys/<id>/edit
- POST /customer-journeys/<id>/delete
- POST /customer-journeys/<id>/stages
- POST /customer-journeys/stages/<stage_id>/edit
- POST /customer-journeys/stages/<stage_id>/delete

JSON API:
- GET    /customer-journeys/<id>/grid                     capability x stage grid
- GET    /customer-journeys/<id>/api/capabilities         capability picker
- POST   /customer-journeys/api/capability-link           upsert a grid cell
- PUT    /customer-journeys/api/capability-link           upsert a grid cell
- DELETE /customer-journeys/api/capability-link           remove a grid cell

Reads are @login_required; writes additionally require one of admin /
architect / business_architect, matching value_stream_routes.py.
"""

import logging

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.decorators import require_roles
from app.modules.capabilities.services import customer_journey_service as cj_service

logger = logging.getLogger(__name__)

customer_journey = Blueprint(
    "customer_journey", __name__, url_prefix="/customer-journeys"
)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


@customer_journey.route("/")
@login_required
def index():
    """List every customer journey."""
    load_error = False
    try:
        journeys = cj_service.list_journeys()
    except Exception:
        logger.error("Failed to load the customer journey index", exc_info=True)
        journeys = []
        load_error = True
    return render_template(
        "customer_journeys/index.html",
        journeys=journeys,
        load_error=load_error,
        total_stages=_total(journeys, "stage_count"),
        total_capabilities=_total(journeys, "capability_count"),
    )


def _total(journeys, field):
    """Sum a per-journey count, or None when any one of them could not be read.

    A partial sum looks exactly like a complete one, so the page would assert a
    number nobody measured. None renders as an em dash instead.
    """
    values = [journey.get(field) for journey in journeys]
    if any(value is None for value in values):
        return None
    return sum(values)


@customer_journey.route("/<int:journey_id>")
@login_required
def detail(journey_id):
    """Journey detail: persona, stage swimlane, sentiment curve, capability grid."""
    journey = cj_service.get_journey_with_stages(journey_id)
    if not journey:
        return (
            render_template(
                "customer_journeys/index.html",
                journeys=[],
                load_error=False,
                not_found=True,
                total_stages=None,
                total_capabilities=None,
            ),
            404,
        )
    return render_template("customer_journeys/detail.html", journey=journey)


# ---------------------------------------------------------------------------
# Journey CRUD (form posts)
# ---------------------------------------------------------------------------


@customer_journey.route("/create", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def create():
    try:
        journey = cj_service.create_journey(request.form.to_dict())
    except Exception:
        db.session.rollback()
        logger.error("Failed to create a customer journey", exc_info=True)
        flash("The customer journey could not be created.", "error")
        return redirect(url_for("customer_journey.index"))
    return redirect(url_for("customer_journey.detail", journey_id=journey.id))


@customer_journey.route("/<int:journey_id>/edit", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def edit(journey_id):
    try:
        journey = cj_service.update_journey(journey_id, request.form.to_dict())
    except Exception:
        db.session.rollback()
        logger.error("Failed to update customer journey %s", journey_id, exc_info=True)
        flash("The customer journey could not be updated.", "error")
        return redirect(url_for("customer_journey.detail", journey_id=journey_id))
    if not journey:
        flash("That customer journey no longer exists.", "error")
        return redirect(url_for("customer_journey.index"))
    return redirect(url_for("customer_journey.detail", journey_id=journey_id))


@customer_journey.route("/<int:journey_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete(journey_id):
    try:
        cj_service.delete_journey(journey_id)
    except Exception:
        db.session.rollback()
        logger.error("Failed to delete customer journey %s", journey_id, exc_info=True)
        flash("The customer journey could not be deleted.", "error")
        return redirect(url_for("customer_journey.detail", journey_id=journey_id))
    return redirect(url_for("customer_journey.index"))


# ---------------------------------------------------------------------------
# Stage CRUD (form posts)
# ---------------------------------------------------------------------------


@customer_journey.route("/<int:journey_id>/stages", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def create_stage(journey_id):
    try:
        cj_service.create_stage(journey_id, request.form.to_dict())
    except Exception:
        db.session.rollback()
        logger.error(
            "Failed to create a stage on customer journey %s", journey_id, exc_info=True
        )
        flash("The stage could not be saved.", "error")
        return redirect(url_for("customer_journey.detail", journey_id=journey_id))
    return redirect(url_for("customer_journey.detail", journey_id=journey_id))


@customer_journey.route("/stages/<int:stage_id>/edit", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def edit_stage(stage_id):
    journey_id = request.form.get("journey_id")
    try:
        stage = cj_service.update_stage(stage_id, request.form.to_dict())
    except Exception:
        db.session.rollback()
        logger.error("Failed to update journey stage %s", stage_id, exc_info=True)
        stage = None
        flash("The stage could not be saved.", "error")
        if journey_id:
            return redirect(
                url_for("customer_journey.detail", journey_id=journey_id)
            )
    if stage is not None:
        journey_id = stage.journey_id
    if journey_id:
        return redirect(url_for("customer_journey.detail", journey_id=journey_id))
    flash("That stage no longer exists.", "error")
    return redirect(url_for("customer_journey.index"))


@customer_journey.route("/stages/<int:stage_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete_stage(stage_id):
    journey_id = request.form.get("journey_id")
    try:
        cj_service.delete_stage(stage_id)
    except Exception:
        db.session.rollback()
        logger.error("Failed to delete journey stage %s", stage_id, exc_info=True)
        flash("The stage could not be deleted.", "error")
        if journey_id:
            return redirect(
                url_for("customer_journey.detail", journey_id=journey_id)
            )
    if journey_id:
        return redirect(url_for("customer_journey.detail", journey_id=journey_id))
    return redirect(url_for("customer_journey.index"))


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------


@customer_journey.route("/<int:journey_id>/grid")
@login_required
def api_grid(journey_id):
    """The capability x stage grid, with the applications behind each capability."""
    try:
        grid = cj_service.build_capability_grid(journey_id)
    except Exception:
        logger.error(
            "Failed to build the grid for customer journey %s", journey_id, exc_info=True
        )
        return jsonify({"error": "An internal error occurred"}), 500

    if not grid.get("journey"):
        return jsonify({"error": "Customer journey not found"}), 404
    return jsonify({"success": True, **grid})


@customer_journey.route("/<int:journey_id>/api/capabilities")
@login_required
def api_capabilities(journey_id):
    """Capability search results for adding a new row to the grid."""
    search = request.args.get("q", "").strip()
    limit = request.args.get("limit", 25, type=int)
    try:
        capabilities = cj_service.list_linkable_capabilities(
            journey_id, search=search, limit=limit
        )
    except Exception:
        logger.error(
            "Failed to search capabilities for customer journey %s",
            journey_id,
            exc_info=True,
        )
        return jsonify({"error": "An internal error occurred"}), 500
    return jsonify({"success": True, "capabilities": capabilities})


@customer_journey.route("/api/capability-link", methods=["POST", "PUT"])
@login_required
@require_roles("admin", "architect", "business_architect")
def api_upsert_capability_link():
    """
    Create or update one (stage, capability) cell.

    Request body:
    {
        "stage_id": 17,
        "capability_id": 123,
        "support_type": "primary",   # primary | secondary | supporting
        "support_level": 4,          # 1-5, omit for "linked, not yet assessed"
        "notes": null
    }
    """
    data = request.get_json(silent=True) or {}
    try:
        stage_id = int(data.get("stage_id"))
        capability_id = int(data.get("capability_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "stage_id and capability_id must be integers"}), 400

    try:
        link = cj_service.upsert_capability_link(stage_id, capability_id, data)
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        logger.error("Failed to upsert a journey capability link", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500

    return jsonify(
        {
            "success": True,
            "link": {
                "id": link.id,
                "journey_id": link.journey_id,
                "stage_id": link.stage_id,
                "capability_id": link.capability_id,
                "support_type": link.support_type,
                "support_level": link.support_level,
                "notes": link.notes,
            },
        }
    )


@customer_journey.route("/api/capability-link", methods=["DELETE"])
@login_required
@require_roles("admin", "architect", "business_architect")
def api_delete_capability_link():
    """Remove one (stage, capability) cell. Body needs only the two ids."""
    data = request.get_json(silent=True) or {}
    try:
        stage_id = int(data.get("stage_id"))
        capability_id = int(data.get("capability_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "stage_id and capability_id must be integers"}), 400

    try:
        deleted = cj_service.delete_capability_link(stage_id, capability_id)
    except Exception:
        db.session.rollback()
        logger.error("Failed to delete a journey capability link", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500
    return jsonify({"success": True, "deleted": deleted})
