"""SA-001: Solution projection service.

Serialises a Solution ORM object to a plain dict, including ``element_ids``
— the list of ArchiMate element IDs linked via the SolutionElement join table.
"""


def project_solution(solution) -> dict:
    """Return a dict representation of *solution* suitable for JSON responses.

    Includes ``element_ids``: list of archimate_element_id values from the
    ``solution_elements`` join table (SA-001).
    """
    from app.models.solution_element import SolutionElement

    element_ids = [
        row.archimate_element_id
        for row in SolutionElement.query.filter_by(solution_id=solution.id)
        .with_entities(SolutionElement.archimate_element_id)
        .all()
    ]

    return {
        "id": solution.id,
        "name": solution.name,
        "description": solution.description,
        "solution_type": solution.solution_type,
        "business_domain": solution.business_domain,
        "complexity_level": solution.complexity_level,
        "status": solution.status,
        "deployment_status": solution.deployment_status,
        "governance_status": solution.governance_status,
        "solution_owner": solution.solution_owner,
        "business_sponsor": solution.business_sponsor,
        "technical_lead": solution.technical_lead,
        "archimate_element_id": solution.archimate_element_id,
        # SA-001: multi-element linkage
        "element_ids": element_ids,
        "created_at": solution.created_at.isoformat() if solution.created_at else None,
        "updated_at": solution.updated_at.isoformat() if solution.updated_at else None,
    }
