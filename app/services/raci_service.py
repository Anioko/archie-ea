"""RACI Matrix Service.

Provides helpers to read and write RACI assignments for solution stakeholders.
RACI data is stored on SolutionStakeholderMapping (the junction table that
already links a stakeholder to a specific solution).
"""

import logging

from app import db
from app.models.solution_stakeholder import SolutionStakeholder, SolutionStakeholderMapping

logger = logging.getLogger(__name__)

_RACI_COLS = {"R": "raci_responsible", "A": "raci_accountable", "C": "raci_consulted", "I": "raci_informed"}


def get_raci_matrix(solution_id: int) -> list[dict]:
    """Return RACI data for all stakeholders mapped to *solution_id*.

    Returns a list of dicts, one per stakeholder:
        {
            "stakeholder_id": int,
            "name": str,
            "R": bool, "A": bool, "C": bool, "I": bool,
        }
    """
    mappings = (
        SolutionStakeholderMapping.query
        .filter_by(solution_id=solution_id)
        .join(SolutionStakeholder, SolutionStakeholderMapping.stakeholder_id == SolutionStakeholder.id)
        .add_columns(SolutionStakeholder.name)
        .all()
    )

    result = []
    for mapping, name in mappings:
        result.append({
            "stakeholder_id": mapping.stakeholder_id,
            "name": name,
            "R": bool(mapping.raci_responsible),
            "A": bool(mapping.raci_accountable),
            "C": bool(mapping.raci_consulted),
            "I": bool(mapping.raci_informed),
        })
    return result


def set_raci_assignment(solution_id: int, stakeholder_id: int, raci_type: str, value: bool) -> dict:
    """Toggle a single RACI cell.

    Args:
        solution_id: ID of the solution.
        stakeholder_id: ID of the stakeholder.
        raci_type: One of "R", "A", "C", "I".
        value: True/False.

    Returns:
        Updated mapping as a dict, or raises ValueError on bad input.
    """
    if raci_type not in _RACI_COLS:
        raise ValueError(f"Invalid raci_type '{raci_type}'. Must be one of R, A, C, I.")

    mapping = SolutionStakeholderMapping.query.filter_by(
        solution_id=solution_id, stakeholder_id=stakeholder_id
    ).first()

    if mapping is None:
        raise LookupError(
            f"No stakeholder mapping for solution={solution_id}, stakeholder={stakeholder_id}"
        )

    col = _RACI_COLS[raci_type]
    setattr(mapping, col, bool(value))
    db.session.commit()

    return {
        "stakeholder_id": mapping.stakeholder_id,
        "solution_id": mapping.solution_id,
        "R": bool(mapping.raci_responsible),
        "A": bool(mapping.raci_accountable),
        "C": bool(mapping.raci_consulted),
        "I": bool(mapping.raci_informed),
    }
