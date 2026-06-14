"""Risk service for TPM-013 — risk heat map CRUD and grid data."""
from app import db
from app.models.risk import Risk, RiskStatus


def get_heat_map_data(solution_id=None):
    """Return 5×5 grid with risks placed at (likelihood, impact) positions.

    Returns a dict: {grid: [[...5 rows of 5 cols...]], risks: [...all risk dicts...]}
    Each cell is a list of risk dicts for risks that fall at that position.
    Row index 0 = likelihood 5 (top), col index 0 = impact 1 (left).
    """
    q = Risk.query
    if solution_id is not None:
        q = q.filter_by(solution_id=solution_id)
    all_risks = q.all()

    # Build 5×5 grid indexed [likelihood 1-5][impact 1-5]
    grid = {l: {i: [] for i in range(1, 6)} for l in range(1, 6)}
    for risk in all_risks:
        l = max(1, min(5, risk.likelihood))
        i = max(1, min(5, risk.impact))
        grid[l][i].append(risk.to_dict())

    # Convert to list-of-lists (row 0 = likelihood 5 at top)
    grid_list = []
    for likelihood in range(5, 0, -1):
        row = []
        for impact in range(1, 6):
            row.append(grid[likelihood][impact])
        grid_list.append(row)

    return {
        "grid": grid_list,
        "risks": [r.to_dict() for r in all_risks],
    }


def create_risk(solution_id, title, description, likelihood, impact, owner, mitigation_plan):
    """Create and persist a new Risk. Returns the saved Risk instance."""
    risk = Risk(
        solution_id=solution_id,
        title=title,
        description=description,
        likelihood=int(likelihood),
        impact=int(impact),
        owner=owner,
        mitigation_plan=mitigation_plan,
        status=RiskStatus.OPEN,
    )
    db.session.add(risk)
    db.session.commit()
    return risk


def update_risk_status(risk_id, status):
    """Update status of an existing Risk. Returns the updated Risk."""
    risk = Risk.query.get_or_404(risk_id)
    risk.status = RiskStatus(status)
    db.session.commit()
    return risk
