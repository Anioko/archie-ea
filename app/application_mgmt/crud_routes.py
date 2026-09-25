"""
Core CRUD Routes for Application Management

Create and edit now redirect to the canonical unified_applications routes
(app/modules/applications/routes/crud_routes.py); this module renders no
form of its own for either and writes nothing to the application record
along the way. Delete, the legacy detail redirect and the quick-fill patch
endpoint stay here.
"""

from flask import current_app, flash, jsonify, redirect, request, url_for
from flask_login import login_required

from .. import db
from ..models.application_portfolio import ApplicationComponent
from . import application_mgmt


@application_mgmt.route("/applications/create", methods=["GET", "POST"])
@login_required
def application_create():
    """Superseded by the canonical create route; kept only as a URL redirect
    for anything still pointed at this address."""
    return redirect(url_for("unified_applications.application_create"))


@application_mgmt.route(
    "/applications/<int:id>",
    strict_slashes=False,
    endpoint="legacy_application_detail_redirect",
)
@login_required
def legacy_application_detail_redirect(id):
    """Legacy /dashboard/applications/<id> — redirect to canonical /applications/<id>."""
    return redirect(
        url_for("unified_applications.application_detail", id=id, **request.args),
        code=301,
    )


@application_mgmt.route("/applications/<int:id>/edit", methods=["GET", "POST"])
@login_required
def application_edit(id):
    """Superseded by the canonical edit route; kept only as a URL redirect
    for anything still pointed at this address."""
    return redirect(url_for("unified_applications.application_edit", id=id))


@application_mgmt.route("/applications/<int:id>/delete", methods=["POST"])
@login_required
def application_delete(id):
    """Delete Application Component"""
    # csrf-ok: global CSRFProtect active

    app = ApplicationComponent.query.get_or_404(id)
    app_name = app.name
    element_id = app.archimate_element_id

    try:
        from app.modules.applications.routes._helpers import (
            _delete_mirror_archimate_element,
        )

        db.session.delete(app)
        db.session.flush()
        # The mirror ArchiMate element goes with the application (finding C-02).
        mirror = _delete_mirror_archimate_element(element_id)
        db.session.commit()
        if mirror["errors"]:
            flash(
                f'Application Component "{app_name}" deleted, but its ArchiMate '
                "element could not be removed — it is still referenced elsewhere.",
                "warning",
            )
        else:
            flash(
                f'Application Component "{app_name}" deleted successfully!', "success"
            )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting application {id}: {e}")
        flash("Error deleting application. Please try again.", "error")
        return redirect(url_for("unified_applications.application_detail", id=id))

    return redirect(url_for("unified_applications.application_list"))


# ---------------------------------------------------------------------------
# Quick-fill endpoint — patch a single field to nudge completeness upward
# ---------------------------------------------------------------------------
_QUICK_FILL_ALLOWED = {
    "business_owner",
    "technical_owner",
    "annual_cost",
    "criticality",
    "description",
}


@application_mgmt.route("/api/applications/<int:app_id>/quick-fill", methods=["PATCH"])
@login_required
def application_quick_fill(app_id):
    """PATCH a single data-completeness field on an application.

    Body: {"field": "<field_name>", "value": "<value>"}
    Returns: {"success": true, "completeness_score": <int>}
    """
    app_obj = ApplicationComponent.query.get_or_404(app_id)

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "JSON body required"}), 400

    field = data.get("field", "")
    value = data.get("value", "")

    if field not in _QUICK_FILL_ALLOWED:
        return jsonify({
            "success": False,
            "error": f"Field '{field}' is not patchable. Allowed: {sorted(_QUICK_FILL_ALLOWED)}",
        }), 400

    if not isinstance(value, str) or not value.strip():
        return jsonify({"success": False, "error": "value must be a non-empty string"}), 400

    # Map quick-fill field names to actual model column names
    _FIELD_MAP = {
        "business_owner": "business_owner",
        "technical_owner": "technical_owner",
        "annual_cost": "license_cost_annual",
        "criticality": "business_criticality",
        "description": "description",
    }
    model_field = _FIELD_MAP[field]

    try:
        setattr(app_obj, model_field, value.strip())
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("quick_fill error app=%s field=%s: %s", app_id, field, e)
        return jsonify({"success": False, "error": "Database error"}), 500

    return jsonify({"success": True, "completeness_score": app_obj.completeness_score})
