"""Pre-write duplicate detection for named entities (ARCH-030).

The August 2026 QA sweep found the repository 46% duplicated at 145 ArchiMate
elements — 25 duplicate-name groups covering 67 rows, many triplicated — plus
four near-identical Solutions and an ``/applications/create`` endpoint that
returned ``201 Created`` three times in a row for a byte-identical name. There
was no duplicate check anywhere on the write path, and the AI agent creates
entities autonomously, so the duplication accrues at machine speed.

This module supplies the check. It is deliberately *application*-level rather
than a database ``UNIQUE`` constraint:

* ``flask reconcile-schema`` is ADD-COLUMN-only and cannot add a constraint, and
  deploys do not run ``flask db upgrade`` (see CLAUDE.md, "Schema management").
* 67 duplicate rows already exist in production, so a unique index would fail to
  build against the live data.

Tenancy
-------
Models inheriting ``TenantMixin`` already get ``WHERE organization_id =
g.current_org_id`` injected by ``do_orm_execute``, so the queries here add **no**
organization predicate for them — doing so would double-filter. For models that
are tenant-owned but not mixed in, pass ``organization_id=`` explicitly. For
genuinely global reference data (``VendorOrganization``) pass nothing.
"""

from __future__ import annotations

from typing import Any

from flask import jsonify

__all__ = [
    "normalize_name",
    "find_duplicate_by_name",
    "duplicate_conflict_response",
    "allow_duplicate_requested",
]


def normalize_name(value: Any) -> str:
    """Casefold and collapse whitespace so 'HxGN  EAM ' == 'hxgn eam'."""
    if value is None:
        return ""
    return " ".join(str(value).split()).casefold()


def find_duplicate_by_name(
    model,
    name: Any,
    *,
    name_field: str = "name",
    organization_id: int | None = None,
    extra_filters: list | None = None,
):
    """Return an existing row whose name matches ``name``, or ``None``.

    Matching is case-insensitive and whitespace-normalised, done in SQL so it
    uses an index scan rather than loading the table.

    Args:
        model: the mapped class to search.
        name: the candidate name.
        name_field: column holding the name (``title`` on some models).
        organization_id: pass ONLY for tenant-owned models that do **not**
            inherit ``TenantMixin``; mixed-in models are already filtered and
            passing this double-filters.
        extra_filters: further SQLAlchemy criteria to narrow the match, e.g.
            ``[ArchiMateElement.element_type == "ApplicationService"]``.

    Returns:
        The first matching instance, or ``None`` when the name is blank or no
        match exists.
    """
    normalized = normalize_name(name)
    if not normalized:
        return None

    from app import db

    column = getattr(model, name_field)
    query = model.query.filter(db.func.lower(db.func.btrim(column)) == normalized)

    if organization_id is not None and hasattr(model, "organization_id"):
        # Only apply it where the middleware has not already — otherwise this is
        # the double-filter CLAUDE.md warns about. Outside a request context
        # (agent runner, CLI, scheduler) there is no g.current_org_id and the
        # explicit predicate is the *only* thing scoping the lookup, so a
        # missing one would silently compare names across every tenant.
        from flask import g, has_request_context

        already_scoped = has_request_context() and getattr(g, "current_org_id", None)
        if not already_scoped:
            query = query.filter(model.organization_id == organization_id)

    for criterion in extra_filters or []:
        query = query.filter(criterion)

    return query.first()


def duplicate_conflict_response(entity_label: str, existing, name_field: str = "name"):
    """A 409 naming the record that already exists.

    Never merges and never silently rejects: the caller — including the AI agent
    — is told exactly what it collided with so it can decide whether to reuse
    the existing record or retry with ``allow_duplicate``.
    """
    existing_name = getattr(existing, name_field, None)
    return (
        jsonify(
            {
                "success": False,
                "error": (
                    f"{entity_label} named '{existing_name}' already exists. "
                    "Reuse it, choose a different name, or resend with "
                    "allow_duplicate=true if the duplicate is intentional."
                ),
                "code": "DUPLICATE_NAME",
                "duplicate_of": {"id": existing.id, "name": existing_name},
            }
        ),
        409,
    )


_TRUTHY = {"1", "true", "yes", "on"}


def allow_duplicate_requested(data=None) -> bool:
    """True when the caller explicitly opted into creating a duplicate.

    Honours ``?allow_duplicate=true`` on the query string, the same key in a
    JSON or form body, and the ``X-Allow-Duplicate`` header. Some organisations
    genuinely run two systems with the same name in different domains, so the
    escape hatch has to exist — it just has to be deliberate.
    """
    from flask import has_request_context, request

    if isinstance(data, dict):
        raw = data.get("allow_duplicate")
        if isinstance(raw, bool):
            if raw:
                return True
        elif raw is not None and str(raw).strip().lower() in _TRUTHY:
            return True
    elif data is not None:
        raw = data.get("allow_duplicate")
        if raw is not None and str(raw).strip().lower() in _TRUTHY:
            return True

    if not has_request_context():
        return False

    if str(request.args.get("allow_duplicate", "")).strip().lower() in _TRUTHY:
        return True
    if str(request.headers.get("X-Allow-Duplicate", "")).strip().lower() in _TRUTHY:
        return True
    return False
