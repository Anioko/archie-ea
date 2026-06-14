"""TPM-013: Risk heat map route — /solutions/<id>/risks/heatmap."""
import logging

from flask import Blueprint, render_template
from flask_login import login_required

from app.models.solution_models import Solution
from app.models.solution_lifecycle_models import SolutionRisk

logger = logging.getLogger(__name__)

solutions_bp = Blueprint("solutions_risk", __name__, url_prefix="/solutions")

# Map text-level values to integers 1-5 for the 5×5 heat-map grid.
_LEVEL_MAP = {
    "very_low": 1,
    "very low": 1,
    "low": 2,
    "medium": 3,
    "high": 4,
    "very_high": 5,
    "very high": 5,
    "critical": 5,
}


def _level_to_int(val, default=3):
    """Convert a string or integer probability/impact value to an integer 1-5."""
    if isinstance(val, int):
        return max(1, min(5, val))
    if isinstance(val, str) and val.isdigit():
        return max(1, min(5, int(val)))
    return _LEVEL_MAP.get(str(val).lower().strip(), default)


@solutions_bp.route("/<int:solution_id>/export/narrative")
@login_required
def export_narrative(solution_id):
    """SA-004: Export solution narrative document."""
    from app.services.solution_narrative_service import generate_sad as _gen
    ctx = _gen(solution_id)
    solution = Solution.query.get_or_404(solution_id)
    risks = SolutionRisk.query.filter_by(solution_id=solution_id).all()
    return render_template(
        "exports/solution_design_document.html",
        solution=solution,
        options=solution.options if hasattr(solution, 'options') else [],
        risks=risks,
        capabilities=[],
        requirements=[],
    )


@solutions_bp.route("/<int:solution_id>/risks/heatmap")
@login_required
def risk_heatmap(solution_id):
    """Render the 5×5 risk heat-map page for a solution."""
    solution = Solution.query.get_or_404(solution_id)
    risks = SolutionRisk.query.filter_by(solution_id=solution_id).all()
    risks_data = [
        {
            "id": r.id,
            "title": r.risk_description[:60] if r.risk_description else f"Risk {r.id}",
            "description": r.risk_description or "",
            "probability": _level_to_int(r.probability),
            "impact": _level_to_int(r.impact),
            "mitigation": r.mitigation or "",
            "status": r.status or "open",
            "owner": r.owner or "",
        }
        for r in risks
    ]
    return render_template(
        "solutions/risk_heatmap.html",
        solution=solution,
        risks_data=risks_data,
    )
