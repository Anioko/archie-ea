from flask import Blueprint, jsonify, render_template, request

from app.decorators import audit_log
from app.services.autogen_service import (
    create_override,
    list_events,
    list_overrides,
    run_health_check,
)
from flask_login import login_required

bp = Blueprint("autogen", __name__, url_prefix="/autogen")


@bp.route("/")
@login_required
def dashboard():
    events = list_events(100)
    overrides = list_overrides()
    return render_template("autogen_dashboard.html", events=events, overrides=overrides)


@bp.route("/overrides", methods=["GET", "POST"])
@login_required
@audit_log("update_overrides")
def overrides():
    if request.method == "POST":
        data = request.json or {}
        ov = create_override(
            framework=data.get("framework"),
            domain=data.get("domain"),
            target_type=data.get("target_type"),
            rule=data.get("rule", "{}"),
            description=data.get("description"),
            enabled=data.get("enabled", True),
        )
        return jsonify(ov.to_dict())
    return jsonify(list_overrides())


@bp.route("/health", methods=["GET"])
@login_required
def health():
    report = run_health_check()
    return jsonify(report)
