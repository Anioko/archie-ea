"""
Value Stream routes.

Blueprint: value_stream, url_prefix=/value-streams

Brings the existing (previously orphaned) ValueStream / ValueStreamStage /
CapabilityValueStreamMapping models to life:

- GET  /value-streams/                          index  - list value streams
- GET  /value-streams/<id>                      detail - stage swimlane + BIZBOK grid
- GET  /value-streams/<id>/report.<fmt>          the stream as pdf/docx/xlsx/html
- POST /value-streams/create                    create a value stream
- POST /value-streams/<id>/edit                 edit a value stream
- POST /value-streams/<id>/delete                delete a value stream
- POST /value-streams/<id>/stages                create a stage
- POST /value-streams/stages/<stage_id>/edit     edit a stage
- POST /value-streams/stages/<stage_id>/delete   delete a stage

JSON API:
- GET    /value-streams/<id>/grid                          BIZBOK grid data
- GET    /value-streams/<id>/api/unmapped-capabilities      capability picker
- POST   /value-streams/api/mapping                          upsert a grid cell
- PUT    /value-streams/api/mapping                          upsert a grid cell
- DELETE /value-streams/api/mapping                          remove a grid cell
"""

import logging

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

# Destructive and mutating routes were guarded by @login_required only, so any
# authenticated user could delete another user's records. Matches the gating
# already used by app/modules/capabilities/routes/enterprise_crud_routes.py.
from app.decorators import require_roles

from app import db

from app.modules.capabilities.services import value_stream_service as vs_service

logger = logging.getLogger(__name__)

value_stream = Blueprint(
    "value_stream", __name__, url_prefix="/value-streams"
)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


@value_stream.route("/")
@login_required
def index():
    """List all value streams."""
    try:
        streams = vs_service.list_value_streams()
    except Exception:
        logger.error("Failed to load value streams index", exc_info=True)
        streams = []
    return render_template("value_streams/index.html", streams=streams)


@value_stream.route("/<int:value_stream_id>")
@login_required
def detail(value_stream_id):
    """Value stream detail: stage swimlane + BIZBOK capability x stage grid."""
    vs_data = vs_service.get_value_stream_with_stages(value_stream_id)
    if not vs_data:
        return render_template("value_streams/index.html", streams=[], not_found=True), 404
    return render_template("value_streams/detail.html", value_stream=vs_data)


@value_stream.route("/<int:value_stream_id>/report.<fmt>")
@login_required
def value_stream_report(value_stream_id, fmt):
    """One value stream as a document: PDF, Word, Excel or a shareable page.

    The BIZBOK grid on the detail page is a working surface. This is the thing
    that goes to an operating committee — the stage flow, the capability behind
    each stage, and the stages with nothing behind them at all.

    A format that cannot be produced on this deployment answers with the reason
    and a 503, not a 500 and not a zero-byte file: WeasyPrint is a binding over
    native libraries that are absent on Windows and on slim images, and the
    other three formats still work when it is missing.
    """
    from app.modules.capabilities.services.value_stream_report_service import (
        ValueStreamReportError,
        ValueStreamReportService,
    )
    from app.utils.report_export import (
        REPORT_FORMATS,
        current_organisation_name,
        normalise_format,
        report_response,
        safe_filename_stem,
        unsupported_format_response,
    )

    fmt = normalise_format(fmt)
    if fmt not in REPORT_FORMATS:
        return unsupported_format_response(fmt)

    try:
        report = ValueStreamReportService.build(
            value_stream_id, organisation_name=current_organisation_name()
        )
        if report is None:
            return (
                jsonify({"success": False, "error": "Value stream not found."}),
                404,
            )
        if fmt == "pdf":
            payload = ValueStreamReportService.render_pdf(report)
        elif fmt == "docx":
            payload = ValueStreamReportService.render_docx(report)
        elif fmt == "xlsx":
            payload = ValueStreamReportService.render_xlsx(report)
        else:
            payload = ValueStreamReportService.render_html(report)
    except ValueStreamReportError as exc:
        current_app.logger.warning("value stream report unavailable as %s: %s", fmt, exc)
        return jsonify({"success": False, "error": str(exc)}), 503
    except Exception:  # noqa: BLE001
        current_app.logger.exception(
            "value stream %s report failed to render as %s", value_stream_id, fmt
        )
        return (
            jsonify({
                "success": False,
                "error": "The value stream report could not be generated. The "
                         "failure has been logged.",
            }),
            500,
        )

    stem = safe_filename_stem(
        report["stream"]["code"] or report["stream"]["name"], "value_stream"
    )
    return report_response(payload, fmt, f"value_stream_{stem}")


# ---------------------------------------------------------------------------
# Value Stream CRUD (form posts)
# ---------------------------------------------------------------------------


@value_stream.route("/create", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def create():
    try:
        vs = vs_service.create_value_stream(request.form.to_dict())
        return redirect(url_for("value_stream.detail", value_stream_id=vs.id))
    except Exception:
        db.session.rollback()
        logger.error("Failed to create value stream", exc_info=True)
        return redirect(url_for("value_stream.index"))


@value_stream.route("/<int:value_stream_id>/edit", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def edit(value_stream_id):
    try:
        vs = vs_service.update_value_stream(value_stream_id, request.form.to_dict())
        if not vs:
            return redirect(url_for("value_stream.index"))
        return redirect(url_for("value_stream.detail", value_stream_id=value_stream_id))
    except Exception:
        db.session.rollback()
        logger.error("Failed to update value stream %s", value_stream_id, exc_info=True)
        return redirect(url_for("value_stream.detail", value_stream_id=value_stream_id))


@value_stream.route("/<int:value_stream_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete(value_stream_id):
    try:
        vs_service.delete_value_stream(value_stream_id)
    except Exception:
        logger.error("Failed to delete value stream %s", value_stream_id, exc_info=True)
    return redirect(url_for("value_stream.index"))


# ---------------------------------------------------------------------------
# Stage CRUD (form posts)
# ---------------------------------------------------------------------------


@value_stream.route("/<int:value_stream_id>/stages", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def create_stage(value_stream_id):
    try:
        vs_service.create_stage(value_stream_id, request.form.to_dict())
    except Exception:
        db.session.rollback()
        logger.error("Failed to create stage for value stream %s", value_stream_id, exc_info=True)
    return redirect(url_for("value_stream.detail", value_stream_id=value_stream_id))


@value_stream.route("/stages/<int:stage_id>/edit", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def edit_stage(stage_id):
    stage = None
    try:
        stage = vs_service.update_stage(stage_id, request.form.to_dict())
    except Exception:
        db.session.rollback()
        logger.error("Failed to update stage %s", stage_id, exc_info=True)
    value_stream_id = stage.value_stream_id if stage else request.form.get("value_stream_id")
    if value_stream_id:
        return redirect(url_for("value_stream.detail", value_stream_id=value_stream_id))
    return redirect(url_for("value_stream.index"))


@value_stream.route("/stages/<int:stage_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete_stage(stage_id):
    value_stream_id = request.form.get("value_stream_id")
    try:
        vs_service.delete_stage(stage_id)
    except Exception:
        logger.error("Failed to delete stage %s", stage_id, exc_info=True)
    if value_stream_id:
        return redirect(url_for("value_stream.detail", value_stream_id=value_stream_id))
    return redirect(url_for("value_stream.index"))


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------


@value_stream.route("/<int:value_stream_id>/grid")
@login_required
def api_grid(value_stream_id):
    """Return the BIZBOK capability x stage grid for a value stream."""
    try:
        grid = vs_service.build_bizbok_grid(value_stream_id)
    except Exception:
        logger.error("Failed to build grid for value stream %s", value_stream_id, exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500

    if not grid.get("value_stream"):
        return jsonify({"error": "Value stream not found"}), 404
    return jsonify({"success": True, **grid})


@value_stream.route("/<int:value_stream_id>/api/unmapped-capabilities")
@login_required
def api_unmapped_capabilities(value_stream_id):
    """Capability search results for adding a new row to the grid."""
    search = request.args.get("q", "").strip()
    limit = request.args.get("limit", 25, type=int)
    try:
        capabilities = vs_service.list_unmapped_capabilities(
            value_stream_id, search=search, limit=limit
        )
    except Exception:
        logger.error(
            "Failed to search unmapped capabilities for value stream %s",
            value_stream_id,
            exc_info=True,
        )
        return jsonify({"error": "An internal error occurred"}), 500
    return jsonify({"success": True, "capabilities": capabilities})


@value_stream.route("/api/mapping", methods=["POST", "PUT"])
@login_required
@require_roles("admin", "architect", "business_architect")
def api_upsert_mapping():
    """
    Create or update a single BIZBOK grid cell.

    Request body:
    {
        "capability_id": 123,
        "value_stream_id": 4,
        "value_stream_stage_id": 17,
        "support_type": "primary",       # primary | secondary | supporting
        "support_level": 4,               # 1-5
        "capability_contribution": 70,    # 0-100
        "impact_level": "high",
        "stage_criticality": "high",
        "cycle_time_impact": null,
        "quality_impact": null,
        "cost_impact": null,
        "assessment_notes": null
    }
    """
    data = request.get_json(silent=True) or {}
    try:
        capability_id = int(data.get("capability_id"))
        value_stream_id = int(data.get("value_stream_id"))
        value_stream_stage_id = int(data.get("value_stream_stage_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "capability_id, value_stream_id and value_stream_stage_id must be integers"}), 400

    try:
        mapping = vs_service.upsert_mapping_cell(
            capability_id, value_stream_id, value_stream_stage_id, data
        )
        return jsonify(
            {
                "success": True,
                "mapping": {
                    "id": mapping.id,
                    "capability_id": mapping.capability_id,
                    "value_stream_id": mapping.value_stream_id,
                    "value_stream_stage_id": mapping.value_stream_stage_id,
                    "support_type": mapping.support_type,
                    "support_level": mapping.support_level,
                    "capability_contribution": mapping.capability_contribution,
                    "impact_level": mapping.impact_level,
                    "stage_criticality": mapping.stage_criticality,
                },
            }
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        db.session.rollback()
        logger.error("Failed to upsert value stream mapping cell", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@value_stream.route("/api/mapping", methods=["DELETE"])
@login_required
@require_roles("admin")
def api_delete_mapping():
    """Remove a BIZBOK grid cell. Same body shape as the upsert (only the three ids are required)."""
    data = request.get_json(silent=True) or {}
    try:
        capability_id = int(data.get("capability_id"))
        value_stream_id = int(data.get("value_stream_id"))
        value_stream_stage_id = int(data.get("value_stream_stage_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "capability_id, value_stream_id and value_stream_stage_id must be integers"}), 400

    try:
        deleted = vs_service.delete_mapping_cell(
            capability_id, value_stream_id, value_stream_stage_id
        )
        return jsonify({"success": True, "deleted": deleted})
    except Exception:
        db.session.rollback()
        logger.error("Failed to delete value stream mapping cell", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500
