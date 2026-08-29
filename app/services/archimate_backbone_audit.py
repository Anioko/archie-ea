"""Prove the ArchiMate backbone is complete, rather than assuming it.

AGENTS.md: "ArchiMate is the backbone, not a view. Every backend CREATE for a
motivation entity must call _sync_archimate_element() so a matching
ArchiMateElement row exists ... the field IS the element."

That rule had no way to be checked. The sync swallowed its own failures and
returned None, and not one of its nine call sites inspects the return value, so a
Driver, Goal, Constraint or Requirement could commit with no element and nothing
in the product would say so. Traceability, impact analysis, line of sight and
every capability lens read from the backbone, so each of them would simply return
a quieter answer than the truth -- the worst kind of wrong for a system of record,
because it looks like a complete answer.

This module answers one question: for this organisation, which motivation rows
have no corresponding element? It reports what it measured and never guesses. A
row it cannot classify is reported as unresolved rather than assumed present.
"""

from __future__ import annotations

import logging

from app import db


logger = logging.getLogger(__name__)


# The domain -> ArchiMate mapping DESIGN.md publishes. Kept here as data so the
# audit and the reader see the same list, rather than the rule living only in
# prose that drifts from the code.
MOTIVATION_MAPPING = (
    ("SolutionDriver", "app.models.solution_architect_models", "Driver"),
    ("SolutionGoal", "app.models.solution_architect_models", "Goal"),
    ("SolutionConstraint", "app.models.solution_architect_models", "Constraint"),
    ("SolutionRequirement", "app.models.solution_architect_models", "Requirement"),
)


def _load(model_name, module_path):
    """Import a mapped model, or return None if this deployment lacks it.

    Blueprints and models register non-fatally in this repository, so a missing
    model is a real possibility. It is reported as unresolved rather than silently
    dropped: an audit that quietly skips a table would report a cleaner backbone
    than exists, which is the exact failure this module was written to end.
    """
    try:
        module = __import__(module_path, fromlist=[model_name])
        return getattr(module, model_name)
    except (ImportError, AttributeError) as exc:
        logger.warning("backbone audit could not load %s: %s", model_name, exc)
        return None


def audit_backbone(*, organization_id):
    """Report motivation rows with no ArchiMate element, for one organisation.

    Returns a dict with:
        missing        list of {model, id, name, expected_type}
        missing_total  int, or None if nothing could be measured at all
        checked        {model: rows_examined}
        unresolved     models that could not be loaded and so were NOT checked

    ``missing_total`` is None -- never 0 -- when no model could be loaded. A zero
    there would read as "the backbone is complete" when the truth is "nothing was
    looked at", and those two must never render the same.
    """
    from app.models.archimate_core import ArchiMateElement

    if not organization_id:
        return {
            "missing": [],
            "missing_total": None,
            "checked": {},
            "unresolved": ["no organisation supplied"],
        }

    # One query for the element names this organisation already has, per type.
    # Matching on (name, type) mirrors the sync's own idempotency key, so the audit
    # and the writer agree on what "already present" means.
    existing = {}
    for name, ae_type in db.session.execute(
        db.select(ArchiMateElement.name, ArchiMateElement.type).where(
            ArchiMateElement.organization_id == organization_id
        )
    ).all():
        existing.setdefault(ae_type, set()).add(name)

    missing = []
    checked = {}
    unresolved = []

    for model_name, module_path, expected_type in MOTIVATION_MAPPING:
        model = _load(model_name, module_path)
        if model is None:
            unresolved.append(model_name)
            continue

        rows = db.session.execute(
            db.select(model.id, model.name).where(
                model.organization_id == organization_id
            )
        ).all()
        checked[model_name] = len(rows)

        present = existing.get(expected_type, set())
        for row_id, row_name in rows:
            if row_name not in present:
                missing.append(
                    {
                        "model": model_name,
                        "id": row_id,
                        "name": row_name,
                        "expected_type": expected_type,
                    }
                )

    return {
        "missing": missing,
        # None only when nothing at all could be examined; a real zero means a real
        # complete backbone.
        "missing_total": len(missing) if checked else None,
        "checked": checked,
        "unresolved": unresolved,
    }


__all__ = ["MOTIVATION_MAPPING", "audit_backbone"]
