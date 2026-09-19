"""T-003 / task 03: the intelligence module's two query surfaces (API-7, API-2).

Exactly two routes at L1 (NFR-8) -- the US-1 impact endpoint is T-004 and is
NOT added here:

  POST /api/v1/intelligence/derivation/recompute   (DE-4, API-7)
  GET  /api/v1/intelligence/derived/<derived_id>    (DE-3 read path, API-2)

CSRF is covered by Flask-WTF's global ``CSRFProtect`` (see
``app/_bootstrap/extensions.py``); no per-route decorator is needed for a
standard session-authenticated POST, consistent with every other write route
in this codebase.
"""

from __future__ import annotations

from flask import Blueprint, current_app, g, request
from flask_login import current_user, login_required

from app.utils.api_response import error_response, not_found_response, success_response

intelligence_api = Blueprint(
    "intelligence_api", __name__, url_prefix="/api/v1/intelligence"
)


def _current_organization_id() -> int | None:
    """The plain int this request belongs to -- never an ORM object.

    ``g.current_org_id`` is what the tenant-isolation listeners key off
    (CLAUDE.md "Multi-tenancy is implicit"), and is what
    ``run_for_each_tenant``'s per-tenant loop restores when it finishes, so
    reading it here (rather than ``current_user.organization`` -- an ORM
    relationship) is both the correct source and avoids holding an object
    reference across the recompute call.
    """
    org_id = getattr(g, "current_org_id", None)
    if org_id is not None:
        return int(org_id)
    org_id = getattr(current_user, "organization_id", None)
    return int(org_id) if org_id is not None else None


@intelligence_api.route("/derivation/recompute", methods=["POST"])
@login_required
def recompute_derivation():
    """API-7: on-demand recompute for the caller's own tenant.

    Body: ``{"scope": "tenant"}`` -- any other scope is rejected with a
    clear 4xx, never a silent tenant-wide or estate-wide run (constraint,
    task 03).
    """
    payload = request.get_json(silent=True) or {}
    scope = payload.get("scope")
    if scope != "tenant":
        return error_response(
            "scope must be \"tenant\" -- no other recompute scope is supported at L1",
            code="INVALID_SCOPE",
            status_code=400,
        )

    organization_id = _current_organization_id()
    if organization_id is None:
        return error_response(
            "no tenant context for this request", code="NO_TENANT_CONTEXT", status_code=400
        )

    from app.modules.intelligence.services.recompute_job import (
        recompute_derived_facts_on_demand,
    )

    app = current_app._get_current_object()
    run = recompute_derived_facts_on_demand(app, organization_id)

    if run.skipped_locked:
        return error_response(
            "a recompute is already running for this tenant -- try again shortly",
            code="RECOMPUTE_LOCKED",
            status_code=409,
        )

    if not run.results:
        return error_response(
            "recompute did not run for this tenant", code="RECOMPUTE_NOT_RUN", status_code=500
        )

    result = run.results[0]
    if not result.ok:
        return error_response(
            f"recompute failed: {result.error}",
            code="RECOMPUTE_FAILED",
            status_code=500,
        )

    value = result.value or {}
    if value.get("skipped_locked"):
        return error_response(
            "a recompute is already running for this tenant -- try again shortly",
            code="RECOMPUTE_LOCKED",
            status_code=409,
        )

    return success_response(
        {
            "organization_id": organization_id,
            "explicit_count": value.get("explicit_count"),
            "derived_count": value.get("derived_count"),
            "ratio": value.get("ratio"),
            "duration_ms": value.get("duration_ms"),
            "engine_version": value.get("engine_version"),
        }
    )


@intelligence_api.route("/derived/<int:derived_id>", methods=["GET"])
@login_required
def get_derived_fact_provenance(derived_id: int):
    """API-2: expand one derived row's provenance chain to explicit relationships.

    Tenant-scoped: a cross-tenant id is invisible -- the ORM tenant-isolation
    listener (``app/middleware/tenant_isolation.py``) injects a
    ``WHERE organization_id = g.current_org_id`` predicate on the
    ``TenantMixin``-backed model this reads, and the explicit
    ``organization_id`` argument passed to ``get_derived_fact`` below
    double-scopes it -- so this 404s -- never 403, never a leak of another
    tenant's row existing.
    """
    organization_id = _current_organization_id()
    if organization_id is None:
        return error_response(
            "no tenant context for this request", code="NO_TENANT_CONTEXT", status_code=400
        )

    from app.modules.intelligence.services.derived_facts import get_derived_fact

    fact = get_derived_fact(organization_id, derived_id, include_stale=True)
    if fact is None:
        return not_found_response("Derived relationship")

    from app.extensions import db

    # No tenant_scope() here (round-1 refuter finding D4): this route already
    # runs inside a request with g.current_org_id set by the normal request
    # lifecycle, and the existing do_orm_execute tenant-isolation listener
    # already filters this read -- tenant_scope() is a background-job
    # harness whose db.session.remove() calls destroy the REQUEST's own
    # session (detaching flask_login's cached current_user, clobbering
    # g.current_org for the rest of the request) when used inside a request.
    expanded = []
    if fact["chain"]:
        from app.models import ArchiMateRelationship

        rows = (
            db.session.execute(
                db.select(ArchiMateRelationship).where(
                    ArchiMateRelationship.id.in_(fact["chain"]),
                    ArchiMateRelationship.organization_id == organization_id,
                )
            )
            .scalars()
            .all()
        )
        by_id = {r.id: r for r in rows}
        for rel_id in fact["chain"]:
            rel = by_id.get(rel_id)
            if rel is None:
                # A chain link that no longer resolves (D6): recording an
                # explicit unresolved marker instead of silently shortening
                # the array -- a shorter-but-complete-looking chain is
                # exactly the kind of fabricated-looking gap CLAUDE.md's
                # "never invent data" rule warns about.
                expanded.append({"id": rel_id, "unresolved": True, "derived_from": fact["id"]})
                continue
            expanded.append(
                {
                    "id": rel.id,
                    "type": rel.type,
                    "source_id": rel.source_id,
                    "target_id": rel.target_id,
                    "derived_from": fact["id"],
                }
            )

    fact_out = dict(fact)
    fact_out["expanded_chain"] = expanded
    return success_response(fact_out)


__all__ = ["intelligence_api"]
