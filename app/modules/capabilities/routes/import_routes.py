"""Capability-model bulk import — upload, preview, commit.

The commit endpoint re-reads the uploaded file and re-plans it rather than
trusting a plan the browser hands back. That costs one parse and removes a
whole class of problem: a stale preview, a tampered payload, or a model that
changed between the two requests can no longer write something the operator
never saw.

See ``CapabilityImportService`` for what a plan contains and why.
"""

from __future__ import annotations

from flask import Response, jsonify, render_template, request
from flask_login import login_required

from app.decorators import require_roles
from app.modules.capabilities.services.capability_import_service import (
    CapabilityImportError,
    CapabilityImportService,
)

from . import capability_map

MAX_PREVIEW_ROWS = 200


@capability_map.route("/import")
@login_required
def import_page():
    """The upload screen."""
    return render_template("capability_map/import.html")


@capability_map.route("/import/template.csv")
@login_required
def import_template():
    """A template with the accepted columns and a worked two-level example."""
    return Response(
        CapabilityImportService.template_csv(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=capability_model_template.csv"
        },
    )


def _plan_from_request():
    """Read the uploaded file and plan it. Returns (plan, error_response)."""
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return None, (jsonify({"success": False, "error": "No file was uploaded."}), 400)

    try:
        rows, headers = CapabilityImportService.read(uploaded.stream, uploaded.filename)
    except CapabilityImportError as exc:
        return None, (jsonify({"success": False, "error": str(exc)}), 400)

    return CapabilityImportService.plan(rows, headers), None


@capability_map.route("/import/preview", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def import_preview():
    """What would happen. Writes nothing."""
    plan, error = _plan_from_request()
    if error:
        return error

    payload = plan.as_dict()
    # The preview table is for judging the import, not for reading 5,000 rows;
    # the counts above it are the whole set either way. Truncation is stated
    # rather than silent — an import screen that quietly shows a subset is how
    # people approve something they did not look at.
    total_rows = len(payload["rows"])
    if total_rows > MAX_PREVIEW_ROWS:
        payload["rows"] = payload["rows"][:MAX_PREVIEW_ROWS]
        payload["rows_truncated"] = total_rows - MAX_PREVIEW_ROWS
    payload["success"] = True
    return jsonify(payload)


@capability_map.route("/import/commit", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def import_commit():
    """Apply the file. All of it commits, or none of it does."""
    plan, error = _plan_from_request()
    if error:
        return error

    if not plan.rows:
        return jsonify({
            "success": False,
            "error": "Nothing to import — every row was rejected.",
            "errors": [e.as_dict() for e in plan.errors],
        }), 400

    try:
        result = CapabilityImportService.apply(plan)
    except Exception as exc:  # noqa: BLE001 - the operator gets the real reason
        from flask import current_app

        current_app.logger.exception("capability import failed to commit")
        return jsonify({
            "success": False,
            "error": f"The import was rolled back: {type(exc).__name__}: {exc}",
        }), 500

    result["success"] = True
    result["rejected"] = len(plan.errors)
    result["errors"] = [e.as_dict() for e in plan.errors]
    return jsonify(result)
