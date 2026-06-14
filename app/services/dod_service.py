"""DoD (Definition of Done) service — TPM-010."""
from app import db
from app.models.dod_template import DoDCheck, DoDTemplate

_DEFAULT_TEMPLATES = [
    {
        "name": "Story DoD",
        "scope": "story",
        "criteria": [
            {"id": "s1", "text": "Unit tests written and passing", "mandatory": True},
            {"id": "s2", "text": "Code reviewed", "mandatory": True},
            {"id": "s3", "text": "Acceptance criteria met", "mandatory": True},
            {"id": "s4", "text": "No critical bugs", "mandatory": True},
            {"id": "s5", "text": "Documentation updated", "mandatory": False},
        ],
    },
    {
        "name": "Sprint DoD",
        "scope": "sprint",
        "criteria": [
            {"id": "sp1", "text": "All committed stories done", "mandatory": True},
            {"id": "sp2", "text": "Build passing", "mandatory": True},
            {"id": "sp3", "text": "Regression tests green", "mandatory": True},
            {"id": "sp4", "text": "Sprint review completed", "mandatory": False},
        ],
    },
    {
        "name": "Epic DoD",
        "scope": "epic",
        "criteria": [
            {"id": "e1", "text": "All stories done", "mandatory": True},
            {"id": "e2", "text": "Integration tested", "mandatory": True},
            {"id": "e3", "text": "Performance baseline met", "mandatory": False},
            {"id": "e4", "text": "Stakeholder sign-off", "mandatory": True},
        ],
    },
]


def seed_default_templates() -> None:
    """Idempotent seed of default DoD templates."""
    for tmpl in _DEFAULT_TEMPLATES:
        existing = DoDTemplate.query.filter_by(scope=tmpl["scope"], is_default=True).first()  # model-safety-ok: one query per scope (3 total), not a hot path
        if not existing:
            t = DoDTemplate(
                name=tmpl["name"],
                scope=tmpl["scope"],
                is_default=True,
                criteria=tmpl["criteria"],
            )
            db.session.add(t)
    db.session.commit()


def get_template(scope: str) -> DoDTemplate | None:
    """Return the default template for the given scope."""
    return DoDTemplate.query.filter_by(scope=scope, is_default=True).first()


def list_templates() -> list[DoDTemplate]:
    """Return all DoD templates."""
    return DoDTemplate.query.order_by(DoDTemplate.scope).all()


def create_dod_check(requirement_id: int | None, template_id: int, sprint_id: int | None = None) -> DoDCheck:
    """Create a new DoD check record."""
    check = DoDCheck(
        requirement_id=requirement_id,
        sprint_id=sprint_id,
        template_id=template_id,
        checked_criteria={},
        all_mandatory_met=False,
    )
    db.session.add(check)
    db.session.commit()
    return check


def update_checks(check_id: int, criterion_id: str, checked: bool) -> dict:
    """Tick or untick a criterion; recalculate all_mandatory_met."""
    check = DoDCheck.query.get_or_404(check_id)
    criteria = dict(check.checked_criteria or {})
    criteria[criterion_id] = checked
    check.checked_criteria = criteria

    # Recalculate mandatory gate
    template = DoDTemplate.query.get(check.template_id)
    if template:
        mandatory_ids = {c["id"] for c in (template.criteria or []) if c.get("mandatory")}
        check.all_mandatory_met = all(criteria.get(cid) for cid in mandatory_ids)
    else:
        check.all_mandatory_met = False

    db.session.commit()
    return check.to_dict()


def can_mark_done(requirement_id: int) -> dict:
    """Gate check: can this requirement be marked done?

    Returns {"allowed": bool, "blocking": [criterion text, ...]}.
    """
    check = (
        DoDCheck.query.filter_by(requirement_id=requirement_id)
        .order_by(DoDCheck.id.desc())
        .first()
    )
    if not check:
        return {"allowed": False, "blocking": ["No DoD check exists for this requirement"]}

    template = DoDTemplate.query.get(check.template_id)
    if not template:
        return {"allowed": False, "blocking": ["DoD template not found"]}

    blocking = []
    for criterion in template.criteria or []:
        if criterion.get("mandatory") and not (check.checked_criteria or {}).get(criterion["id"]):
            blocking.append(criterion["text"])

    return {"allowed": len(blocking) == 0, "blocking": blocking}
