"""SA-008: Solution design completeness routes.

Provides:
    GET /api/solutions/<solution_id>/completeness  — JSON report
    GET /solutions/<solution_id>/completeness      — HTML page
"""
from flask import Blueprint, jsonify, render_template
from flask_login import login_required

completeness_bp = Blueprint("completeness", __name__)


@completeness_bp.route("/api/solutions/<int:solution_id>/completeness", methods=["GET"])
@login_required
def api_completeness(solution_id: int):
    """Return JSON completeness report for a solution."""
    from app.services.solution_completeness_service import check_completeness
    report = check_completeness(solution_id)
    return jsonify(report)


@completeness_bp.route("/solutions/<int:solution_id>/completeness", methods=["GET"])
@login_required
def completeness_page(solution_id: int):
    """Render the completeness dashboard page."""
    from app.services.solution_completeness_service import check_completeness
    report = check_completeness(solution_id)
    return render_template(
        "solutions/completeness.html",
        report=report,
        solution_id=solution_id,
    )
