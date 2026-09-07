"""Risk service for TPM-013 — risk heat map CRUD and grid data."""
from app.services.archimate_backbone import sync_archimate_element
from app import db
from app.models.risk import Risk, RiskStatus
from app.models.risk_entity_link import ENTITY_TYPES, RiskEntityLink


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
    grid = {item: {i: [] for i in range(1, 6)} for item in range(1, 6)}
    for risk in all_risks:
        item = max(1, min(5, risk.likelihood))
        i = max(1, min(5, risk.impact))
        grid[item][i].append(risk.to_dict())

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
    sync_archimate_element(risk)
    db.session.commit()
    return risk


def update_risk_status(risk_id, status):
    """Update status of an existing Risk. Returns the updated Risk."""
    risk = Risk.query.get_or_404(risk_id)
    risk.status = RiskStatus(status)
    db.session.commit()
    return risk


# H2: full edit/delete were missing entirely -- the register could create a
# risk and flip its status, nothing else. The Description and Mitigation
# plan captured at creation were consequently write-only: nothing after
# creation ever read them back.
_EDITABLE_FIELDS = ("title", "description", "likelihood", "impact", "owner", "mitigation_plan")


def update_risk(risk_id, **fields):
    """Full edit of an existing Risk. Only keys in _EDITABLE_FIELDS are applied;
    unknown keys are ignored rather than raising, so a caller can pass a whole
    form payload safely."""
    risk = Risk.query.get_or_404(risk_id)
    for key in _EDITABLE_FIELDS:
        if key in fields and fields[key] is not None:
            value = fields[key]
            if key in ("likelihood", "impact"):
                value = int(value)
            setattr(risk, key, value)
    db.session.commit()
    return risk


def delete_risk(risk_id):
    """Delete a Risk and its entity links (cascade). Does not touch the
    ArchiMate mirror row -- archimate_element_id is SET NULL on delete per
    the FK's ondelete, consistent with every other motivation-entity delete
    in this codebase."""
    risk = Risk.query.get_or_404(risk_id)
    db.session.delete(risk)
    db.session.commit()


# --- H1: entity links -------------------------------------------------

def list_risk_links(risk_id):
    return RiskEntityLink.query.filter_by(risk_id=risk_id).order_by(RiskEntityLink.id).all()


def add_risk_link(risk_id, entity_type, entity_id):
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"entity_type must be one of {ENTITY_TYPES}, got {entity_type!r}")
    Risk.query.get_or_404(risk_id)  # 404s cleanly if the risk does not exist
    existing = RiskEntityLink.query.filter_by(
        risk_id=risk_id, entity_type=entity_type, entity_id=entity_id
    ).first()
    if existing:
        return existing
    link = RiskEntityLink(risk_id=risk_id, entity_type=entity_type, entity_id=int(entity_id))
    db.session.add(link)
    db.session.commit()
    return link


def remove_risk_link(risk_id, link_id):
    link = RiskEntityLink.query.filter_by(id=link_id, risk_id=risk_id).first_or_404()
    db.session.delete(link)
    db.session.commit()


def links_for_entity(entity_type, entity_id):
    """Risks linked to one Application/Solution/Programme -- the parent-side
    read for "Linked risks" sections on those entities' own detail pages."""
    links = RiskEntityLink.query.filter_by(entity_type=entity_type, entity_id=entity_id).all()
    if not links:
        return []
    risk_ids = [link.risk_id for link in links]
    risks = Risk.query.filter(Risk.id.in_(risk_ids)).order_by(Risk.id).all()
    return [r.to_dict() for r in risks]
