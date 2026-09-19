"""T-003/T-004: the intelligence module's query surfaces (API-7, API-2, API-1).

  POST /api/v1/intelligence/derivation/recompute   (DE-4, API-7)
  GET  /api/v1/intelligence/derived/<derived_id>    (DE-3 read path, API-2)
  GET  /api/v1/intelligence/impact/<element_id>     (DE-9, API-1 -- T-004)

T-004 adds the third route to this EXISTING blueprint rather than a new
module/blueprint on the same URL prefix -- see
``docs/buckets/t004-us1-impact-endpoint/tasks/00-verification-notes.md``
defect D1 (ADR 0008 rule 3: two blueprints on one prefix).

CSRF is covered by Flask-WTF's global ``CSRFProtect`` (see
``app/_bootstrap/extensions.py``); no per-route decorator is needed for a
standard session-authenticated POST, consistent with every other write route
in this codebase.
"""

from __future__ import annotations

from flask import Blueprint, current_app, g, request
from flask_login import current_user, login_required

from app.modules.intelligence.services.reason_codes import validate_reason_code
from app.utils.api_response import error_response, not_found_response, success_response

# NEW-4 fix: these two DE-14 reason codes are structurally unreachable in the
# 200 ``reasons`` list this route returns, because both conditions they name
# are already intercepted by an early 400/404 return below, before
# ``IntelligenceQueryService.cross_layer_impact`` (the only place that would
# put them in a 200 body) is ever called. Rather than leave them as dead
# members only a direct unit test can reach, they are surfaced in the error
# body of the exact 400/404 responses that ARE their real, reachable home.
_NO_TENANT_CONTEXT_REASON = validate_reason_code("no_tenant_context")
_ELEMENT_NOT_FOUND_REASON = validate_reason_code("element_not_found")

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


_TRUE_STRINGS = {"true", "1", "yes"}
_FALSE_STRINGS = {"false", "0", "no"}
_VALID_DIRECTIONS = {"downstream", "upstream", "both"}


def _parse_bool_param(raw: str | None, *, default: bool, param_name: str):
    """Strict boolean query-param parsing: any non-boolean-looking value is a
    400, never a silent default (task 02 constraint: "never a silent
    default").

    Returns ``(value, error_response_or_None)``.
    """
    if raw is None:
        return default, None
    lowered = raw.strip().lower()
    if lowered in _TRUE_STRINGS:
        return True, None
    if lowered in _FALSE_STRINGS:
        return False, None
    return None, error_response(
        f"{param_name} must be a boolean (true/false)",
        code="INVALID_PARAMETER",
        status_code=400,
    )


@intelligence_api.route("/impact/<int:element_id>", methods=["GET"])
@login_required
def cross_layer_impact(element_id: int):
    """API-1 (DE-9): US-1's "if this fails, what stops and who owns it".

    Serialises ``IntelligenceQueryService.cross_layer_impact`` through
    ``success_response`` -- no business logic here (task 02 constraint).
    """
    include_derived, err = _parse_bool_param(
        request.args.get("include_derived"), default=False, param_name="include_derived"
    )
    if err is not None:
        return err

    include_stale, err = _parse_bool_param(
        request.args.get("include_stale"), default=False, param_name="include_stale"
    )
    if err is not None:
        return err

    with_owner, err = _parse_bool_param(
        request.args.get("with_owner"), default=True, param_name="with_owner"
    )
    if err is not None:
        return err

    max_depth_raw = request.args.get("max_depth")
    if max_depth_raw is None:
        max_depth = 3
    else:
        try:
            max_depth = int(max_depth_raw)
        except (TypeError, ValueError):
            return error_response(
                "max_depth must be an integer between 1 and 5",
                code="INVALID_PARAMETER",
                status_code=400,
            )
        if not (1 <= max_depth <= 5):
            return error_response(
                "max_depth must be between 1 and 5",
                code="INVALID_PARAMETER",
                status_code=400,
            )

    direction = request.args.get("direction", "downstream")
    if direction not in _VALID_DIRECTIONS:
        return error_response(
            f"direction must be one of {sorted(_VALID_DIRECTIONS)}",
            code="INVALID_PARAMETER",
            status_code=400,
        )

    layer = request.args.get("layer")

    organization_id = _current_organization_id()
    if organization_id is None:
        return error_response(
            "no tenant context for this request",
            code="NO_TENANT_CONTEXT",
            details={"reason": _NO_TENANT_CONTEXT_REASON},
            status_code=400,
        )

    from app.models import ArchiMateElement

    element = ArchiMateElement.query.filter_by(id=element_id).first()
    if element is None:
        # Same call site, same status/code/message for "does not exist" and
        # "belongs to another tenant" -- the tenant-isolation listener has
        # already made the two indistinguishable at the query level (task 02
        # acceptance item 4). ``details`` carries the same reason value on
        # both branches (there is only one branch), so D3 indistinguishability
        # is unaffected.
        return error_response(
            "Element not found",
            code="NOT_FOUND",
            details={"reason": _ELEMENT_NOT_FOUND_REASON},
            status_code=404,
        )

    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    result = IntelligenceQueryService.cross_layer_impact(
        element_id,
        include_derived=include_derived,
        include_stale=include_stale,
        max_depth=max_depth,
        direction=direction,
        layer=layer,
        with_owner=with_owner,
    )

    if result.get("rows") is None:
        return not_found_response("Element")

    return success_response(
        {
            "rows": result["rows"],
            "summary": result["summary"],
            "reasons": result.get("reasons") or [],
            "elements": result.get("elements") or {},
        }
    )


__all__ = ["intelligence_api"]
