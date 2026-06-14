"""
CA-001: Capability ArchiMate coverage API routes.

Blueprint: capability_archimate_bp
Prefix:    /api/capabilities
"""
from flask import Blueprint, jsonify
from flask_login import login_required

capability_archimate_bp = Blueprint(
    "capability_archimate",
    __name__,
    url_prefix="/api/capabilities",
)


@capability_archimate_bp.route("/archimate-coverage", methods=["GET"])
@login_required
def get_archimate_coverage():
    """
    Return capability ↔ ArchiMate binding coverage summary.

    Response:
        200 {total_capabilities, matched, unmatched, coverage_pct}
        500 on unexpected error
    """
    try:
        from app.services.capability_archimate_binding_service import (
            CapabilityArchiMateBindingService,
        )
        svc = CapabilityArchiMateBindingService()
        summary = svc.get_coverage_summary()
        return jsonify(summary), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
