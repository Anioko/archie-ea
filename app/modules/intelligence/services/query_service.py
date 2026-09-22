"""Cross-layer intelligence queries. ``cross_layer_impact`` (L1, "if this
fails, what stops and who owns it"), ``risk_for_element`` (L6, "what could
hurt this, and what does it touch" -- reuses the same traversal per risk
seed), ``portfolio_component_for_element`` (L3, resolves an element to its
ApplicationComponent for the one existing deep link), ``programme_for_element``
(L5, "what are we changing, is it on time and on budget" -- reuses the same
traversal per work-package seed) and ``value_streams_at_risk`` -- "which
value streams depend on a capability below threshold", the curated path
only (T-S1). Coverage over derived and explicit relationships for the
value-stream question is reserved for a later task and is not added here.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.extensions import db
from app.middleware.tenant_context import current_org_id
from app.modules.intelligence.services.derived_facts import list_derived_facts
from app.modules.intelligence.services.latency_probe import record_query_latency
from app.modules.intelligence.services.plain_terms import plain_terms_sentence
from app.modules.intelligence.services.reason_codes import validate_reason_code

VALID_DIRECTIONS = {"downstream", "upstream", "both"}

NO_OWNERSHIP_REASON = validate_reason_code("no_ownership_recorded")
NO_TENANT_CONTEXT_REASON = validate_reason_code("no_tenant_context")
ELEMENT_NOT_FOUND_REASON = validate_reason_code("element_not_found")
DERIVATION_NOT_COMPUTED_REASON = validate_reason_code("derivation_not_computed")
NO_RISK_RECORDED_REASON = validate_reason_code("no_risk_recorded")
NO_APPLICATION_COMPONENT_REASON = validate_reason_code("no_application_component")
NO_WORK_PACKAGE_RECORDED_REASON = validate_reason_code("no_work_package_recorded")
NOT_COSTED_REASON = validate_reason_code("not_costed")

# T-005 (D1): the NFR-5 measurement point is this exact, PINNED series --
# never widened, never aggregated across label values.
NFR5_QUERY = "cross_layer_impact"
NFR5_DEPTH = "4"
NFR5_INCLUDE_DERIVED = "true"

# T-005 (ADR-009): NFR-5's stated measurement threshold. Appears only as the
# Shape-B trigger's threshold_seconds -- never as a yield target (task 02
# constraint: no fabricated target anywhere in the payload).
SHAPE_B_THRESHOLD_SECONDS = 2.0


def _include_derived_gate(include_derived: bool) -> bool:
    """The ``include_derived=False`` filter, isolated as its own seam (same
    pattern as ``_sec09_tenant_check`` and ``derived_facts.py``'s
    ``_apply_default_staleness_filter``) so the mutation-proof test
    (acceptance item 12) can monkeypatch exactly this to always return True
    and confirm criterion 2 goes red, without editing source under test.
    """
    return bool(include_derived)


def _sec09_tenant_check(component_org_id: Optional[int], org_id: int) -> bool:
    """The SEC-09 assertion, isolated as its own seam.

    Mirrors ``derived_facts.py``'s ``_apply_default_staleness_filter`` seam:
    the task 01 mutation-proof test (acceptance item 12) monkeypatches
    exactly this function to simulate "the tenant assertion was removed" and
    confirms the cross-tenant owner-leak test goes red, without editing
    source under test.
    """
    return component_org_id == org_id


def _resolve_owners_batch(
    element_ids: List[int], org_id: int
) -> Dict[int, Tuple[Optional[Dict[str, Any]], Optional[str]]]:
    """AA-5/SEC-09 owner attach: element -> component -> ownership -> unit,
    batched across MANY element ids in a small constant number of queries
    (M7 fix -- see the build report's B2/NEW-3 sections for why this is now
    the ONLY owner-resolution implementation on this path; a per-row
    ``_resolve_owner``/``_find_component_for_element`` pair used to exist
    alongside this and was deleted as dead code -- ``cross_layer_impact`` is
    this function's only production caller).

    ``ApplicationComponent`` carries ``TenantMixin`` so the component select
    below is already fenced by ``do_orm_execute`` (a cross-tenant row is
    simply not returned in a normal request); ``_sec09_tenant_check`` is the
    belt-and-braces assertion applied on top of that ORM fencing.
    ``ApplicationOwnership`` and ``OrganizationUnit`` carry no
    ``organization_id`` column at all, so they are reached ONLY through the
    already-fenced, already-asserted component -- never queried first.

    ``archimate_element_id`` is indexed but NOT unique (a component created
    before the maintaining listener existed, or by a raw-SQL/import path,
    can point two components at the same element) -- ``.scalars().all()``
    with a deterministic ``order_by(id)`` plus ``setdefault`` below picks the
    same "first" component every time instead of risking
    ``MultipleResultsFound``.
    """
    from app.models.application_portfolio import ApplicationComponent
    from app.models.enterprise_intelligence import ApplicationOwnership, OrganizationUnit

    distinct_ids = sorted(set(element_ids))
    results: Dict[int, Tuple[Optional[Dict[str, Any]], Optional[str]]] = {
        eid: (None, NO_OWNERSHIP_REASON) for eid in distinct_ids
    }
    if not distinct_ids:
        return results

    components = (
        db.session.execute(
            db.select(ApplicationComponent)
            .where(ApplicationComponent.archimate_element_id.in_(distinct_ids))
            .order_by(ApplicationComponent.id)
        )
        .scalars()
        .all()
    )

    # Deterministic "first" component per element_id -- same ordering
    # _find_component_for_element uses for the single-row case.
    component_by_element: Dict[int, Any] = {}
    for comp in components:
        component_by_element.setdefault(comp.archimate_element_id, comp)

    # SEC-09: drop any component that fails the tenant assertion before it
    # is ever used to reach ownership/unit data.
    guarded_components = {
        eid: comp
        for eid, comp in component_by_element.items()
        if _sec09_tenant_check(comp.organization_id, org_id)
    }
    if not guarded_components:
        return results

    component_ids = [comp.id for comp in guarded_components.values()]
    ownerships = (
        db.session.execute(
            db.select(ApplicationOwnership).where(
                ApplicationOwnership.application_id.in_(component_ids)
            )
        )
        .scalars()
        .all()
    )
    ownership_by_component: Dict[int, Any] = {}
    for ownership in ownerships:
        ownership_by_component.setdefault(ownership.application_id, ownership)

    unit_ids = [o.organization_unit_id for o in ownership_by_component.values()]
    units: Dict[int, Any] = {}
    if unit_ids:
        units = {
            unit.id: unit
            for unit in db.session.execute(
                db.select(OrganizationUnit).where(OrganizationUnit.id.in_(unit_ids))
            )
            .scalars()
            .all()
        }

    for eid, comp in guarded_components.items():
        ownership = ownership_by_component.get(comp.id)
        if ownership is None:
            continue
        unit = units.get(ownership.organization_unit_id)
        if unit is None:
            continue
        results[eid] = (
            {
                "organization_unit_id": unit.id,
                "name": unit.name,
                "ownership_type": ownership.ownership_type,
            },
            None,
        )
    return results


def _resolve_elements_batch(element_ids: Iterable[int], org_id: Optional[int]) -> Dict[str, Dict[str, Any]]:
    """The element identity map -- ``{str(id): {id, name, type, layer}}``.

    ONE batched ``select`` over ``ArchiMateElement`` for every id in the WHOLE
    result set (same shape as ``_resolve_owners_batch``: collect first, then
    resolve in a constant number of queries -- never one per row).

    The four-key ceiling is enforced at the query, not only when the dict is
    built: only ``id``, ``name``, ``type`` and ``layer`` are selected, so no
    other column of the element (description, documentation, properties, the
    strategic / cost / scoring columns) is ever read, let alone serialised.
    SEC-02 keeps the projection on this path narrow so a later MCP twin
    cannot leak; widening it here would widen it there.

    Tenancy is two layers. ``ArchiMateElement`` carries ``TenantMixin``, so the
    ORM tenant-isolation listener fences the select inside a request. The
    explicit ``organization_id`` predicate below is defence in depth, exactly
    as in ``derived_facts.list_derived_facts``: it is what keeps this function
    correct when it is called with no ambient request context (a job, a CLI
    command, a test looping tenants in one session), where the listener would
    no-op entirely.

    An id that does not resolve inside ``org_id`` -- another tenant's element,
    a soft-deleted element, an element that no longer exists -- is simply
    ABSENT from the result. It is never present with a null name, a
    placeholder, or a name found anywhere else. ``org_id`` of ``None`` yields
    an empty map (there is no tenant whose elements could be named).
    """
    from app.models import ArchiMateElement

    distinct_ids = sorted({eid for eid in element_ids if eid is not None})
    if not distinct_ids or org_id is None:
        return {}

    stmt = db.select(
        ArchiMateElement.id,
        ArchiMateElement.name,
        ArchiMateElement.type,
        ArchiMateElement.layer,
    ).where(
        ArchiMateElement.id.in_(distinct_ids),
        ArchiMateElement.organization_id == org_id,
    )

    elements: Dict[str, Dict[str, Any]] = {}
    for element_id, name, element_type, layer in db.session.execute(stmt).all():
        if name is None:
            # Leave the id out rather than emit an entry with a null name.
            continue
        elements[str(element_id)] = {
            "id": element_id,
            "name": name,
            "type": element_type,
            # ``layer`` comes back as a case-insensitive ``str`` subclass
            # (canonical lower case); hand callers a plain ``str``.
            "layer": str(layer) if layer is not None else None,
        }
    return elements


def _element_ids_in_rows(rows: List[Dict[str, Any]]) -> List[int]:
    """Every element id a row can name: its ``element_id`` and each id in its
    ``relation.chain_elements``. These -- and only these -- are the keys of the
    identity map.
    """
    ids: List[int] = []
    for row in rows:
        ids.append(row["element_id"])
        ids.extend(row["relation"].get("chain_elements") or [])
    return ids


def _name_in(elements: Dict[str, Dict[str, Any]], element_id: Optional[int]) -> Optional[str]:
    entry = elements.get(str(element_id))
    return entry["name"] if entry is not None else None


def _attach_plain_terms(rows: List[Dict[str, Any]], elements: Dict[str, Dict[str, Any]]) -> None:
    """Fill ``relation.plain_terms`` on every DERIVED row (explicit rows keep
    ``None``). The names come from the identity map built for this same
    response; ``plain_terms_sentence`` returns ``None`` when either is absent.

    The derived fact's STORED source and target are passed through as they are,
    together with its stored type; ``plain_terms_sentence`` decides which is
    named first so the sentence never reverses the relationship. Nothing here
    depends on which end the caller started from, so one derived fact reads the
    same sentence from every surface and every query direction.
    """
    for row in rows:
        relation = row["relation"]
        if relation["kind"] != "derived":
            continue
        source_id, target_id = row["_endpoints"]
        relation["plain_terms"] = plain_terms_sentence(
            source_name=_name_in(elements, source_id),
            target_name=_name_in(elements, target_id),
            relation_type=relation["type"],
            depth=relation["depth"],
            confidence=relation["confidence"],
        )


def _explicit_row(rel, depth: int, chain: List[int], chain_elements: List[int], element_id: int) -> Dict[str, Any]:
    return {
        "element_id": element_id,
        "_endpoints": (rel.source_id, rel.target_id),
        "relation": {
            "kind": "explicit",
            "type": rel.type,
            "depth": depth,
            "rule_id": None,
            "chain": chain,
            "chain_elements": chain_elements,
            "confidence": None,
            "provenance": "explicit",
            "computed_at": None,
            "stale": False,
            # Derived-fact-only fields; an explicit row has no derived fact,
            # so all three are null.
            "derived_id": None,
            "engine_version": None,
            "plain_terms": None,
        },
    }


def _walk_explicit(root_id: int, max_depth: int, direction: str) -> List[Dict[str, Any]]:
    """BFS over ``ArchiMateRelationship`` (TenantMixin-fenced, no hand-written
    predicate needed) up to ``max_depth`` hops, in the requested direction.

    Cycle-safe: a node already visited is never re-queued, so this
    terminates even on a cyclic graph within ``max_depth`` iterations.
    """
    from app.models import ArchiMateRelationship

    frontier: Dict[int, Dict[str, List[int]]] = {root_id: {"chain": [], "chain_elements": [root_id]}}
    visited = {root_id}
    rows: List[Dict[str, Any]] = []

    for depth in range(1, max_depth + 1):
        if not frontier:
            break
        frontier_ids = list(frontier.keys())
        conditions = []
        if direction in ("downstream", "both"):
            conditions.append(ArchiMateRelationship.source_id.in_(frontier_ids))
        if direction in ("upstream", "both"):
            conditions.append(ArchiMateRelationship.target_id.in_(frontier_ids))
        if not conditions:
            break

        rels = (
            db.session.execute(db.select(ArchiMateRelationship).where(db.or_(*conditions)))
            .scalars()
            .all()
        )

        next_frontier: Dict[int, Dict[str, List[int]]] = {}
        for rel in rels:
            if direction in ("downstream", "both") and rel.source_id in frontier:
                to_node = rel.target_id
                if to_node not in visited:
                    prior = frontier[rel.source_id]
                    new_chain = prior["chain"] + [rel.id]
                    new_elements = prior["chain_elements"] + [to_node]
                    rows.append(_explicit_row(rel, depth, new_chain, new_elements, to_node))
                    next_frontier[to_node] = {"chain": new_chain, "chain_elements": new_elements}
                    visited.add(to_node)
            if direction in ("upstream", "both") and rel.target_id in frontier:
                to_node = rel.source_id
                if to_node not in visited:
                    prior = frontier[rel.target_id]
                    new_chain = prior["chain"] + [rel.id]
                    new_elements = prior["chain_elements"] + [to_node]
                    rows.append(_explicit_row(rel, depth, new_chain, new_elements, to_node))
                    next_frontier[to_node] = {"chain": new_chain, "chain_elements": new_elements}
                    visited.add(to_node)
        frontier = next_frontier

    return rows


def _filter_explicit_by_layer(rows: List[Dict[str, Any]], layer: str) -> List[Dict[str, Any]]:
    from app.models import ArchiMateElement

    element_ids = set()
    for row in rows:
        element_ids.update(row["_endpoints"])
    if not element_ids:
        return []
    layers = dict(
        db.session.execute(
            db.select(ArchiMateElement.id, ArchiMateElement.layer).where(
                ArchiMateElement.id.in_(element_ids)
            )
        ).all()
    )
    return [
        row
        for row in rows
        if any(layers.get(eid) == layer for eid in row["_endpoints"])
    ]


def _derived_row(fact: Dict[str, Any], root_id: int) -> Dict[str, Any]:
    if fact["source_element_id"] == root_id:
        element_id = fact["target_element_id"]
    else:
        element_id = fact["source_element_id"]
    return {
        "element_id": element_id,
        # Internal join key (popped before return, like the explicit rows'):
        # the fact's own endpoints, so ``_attach_plain_terms`` can name both
        # ends once the identity map exists.
        "_endpoints": (fact["source_element_id"], fact["target_element_id"]),
        "relation": {
            "kind": "derived",
            "type": fact["derived_type"],
            "depth": fact["depth"],
            "rule_id": fact["rule_id"],
            "chain": fact["chain"],
            "chain_elements": fact["chain_element_ids"],
            "confidence": fact["confidence"],
            "provenance": fact["provenance"],
            "computed_at": fact["computed_at"],
            "stale": fact["stale"],
            # ``derived_id`` and ``engine_version`` come straight from the dict
            # ``list_derived_facts`` returns.
            "derived_id": fact["id"],
            "engine_version": fact["engine_version"],
            # Filled by ``_attach_plain_terms`` once the identity map exists.
            "plain_terms": None,
        },
        "reason": fact.get("reason"),
    }


def _derived_filter_args(
    element_id: int, direction: str
) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """Translate US-1's (element_id, direction) into ``list_derived_facts``'s
    (source_element_id, target_element_id, direction) calling convention.

    ``direction="both"`` passes the SAME id as both filters -- the exact
    convention ``list_derived_facts`` documents for its ``source = X OR
    target = X`` branch.
    """
    if direction == "downstream":
        return element_id, None, None
    if direction == "upstream":
        return None, element_id, None
    return element_id, element_id, "both"


def _not_computed_counts() -> Dict[str, Any]:
    """T-005 task 02 acceptance item 12: the not-computed branch's null
    counts, isolated as their own seam (same pattern as
    ``_include_derived_gate`` / ``_sec09_tenant_check`` above and
    ``derived_facts.py``'s ``_apply_default_staleness_filter``) so the
    mutation-proof test can monkeypatch exactly this function to emit ``0``
    instead of ``None`` and confirm the not-computed/measured-zero
    distinguishability test goes red, without editing source under test.
    """
    return {
        "explicit_count": None,
        "derived_count": None,
        "ratio": None,
        "computed_at": None,
        "engine_version": None,
        "stale_count": None,
        "last_recompute_duration_ms": None,
    }


class IntelligenceQueryService:
    """DE-9: read-only cross-layer intelligence queries."""

    @staticmethod
    def derivation_yield(organization_id: int) -> Dict[str, Any]:
        """"How much does derivation add", for one tenant.

        p95 is read from the impact-query histogram at a PINNED selector via
        a bucket-edge read -- never computed in application code, never
        widened, never aggregated across label values. It is process-local
        and estate-wide, not per tenant, so it is reported as its own
        nested, self-describing block on BOTH branches (it measures query
        latency, not derivation -- suppressing it on the not-computed branch
        would hide a real breach).

        ``explicit_count``/``derived_count``/``ratio``/
        ``last_recompute_duration_ms`` come from the tenant's
        ``DerivationRun`` row itself -- the SAME values the recompute
        response already returns (two surfaces, one answer; a store-
        agreement test pins this). ``computed_at``/``engine_version``/
        ``stale_count`` come from ``derived_fact_aggregates`` -- the store's
        OWN current state (never the ``ENGINE_VERSION`` module constant).
        """
        from app.modules.intelligence.services.derived_facts import (
            derived_fact_aggregates,
            latest_derivation_run,
        )
        from app.modules.intelligence.services.latency_probe import read_p95_bucket_edge
        from app.modules.intelligence.services.observability import record_shape_b_trigger

        # D2: this call is wrapped in its OWN series (query="derivation_yield")
        # -- the p95 read below is pinned to "cross_layer_impact" only, and is
        # therefore unaffected by calling this endpoint repeatedly.
        with record_query_latency("derivation_yield") as scope:
            scope.organization_id = organization_id

            p95_read = read_p95_bucket_edge(
                query=NFR5_QUERY, depth=NFR5_DEPTH, include_derived=NFR5_INCLUDE_DERIVED
            )
            p95_block: Dict[str, Any] = {
                "latency_seconds": p95_read["latency_seconds"],
                "sample_count": p95_read["sample_count"],
                "scope": "process_estate_wide",
                "query": NFR5_QUERY,
                "depth": int(NFR5_DEPTH),
                "include_derived": True,
                "reason": p95_read["reason"],
            }
            if p95_read.get("p95_exceeds_seconds") is not None:
                p95_block["p95_exceeds_seconds"] = p95_read["p95_exceeds_seconds"]

            # D3/D11: a real value OR the honest "exceeds the highest
            # declared bucket" fact both constitute a genuine breach signal
            # -- the Shape-B trigger must fire on either (task 02 acceptance
            # item 6), never only on the interpolated case.
            breach_value = p95_read["latency_seconds"]
            if breach_value is None and p95_read["reason"] == "p95_above_highest_bucket":
                breach_value = p95_read.get("p95_exceeds_seconds")

            shape_b_trigger = None
            if breach_value is not None and breach_value > SHAPE_B_THRESHOLD_SECONDS:
                record = record_shape_b_trigger(
                    measured_p95_seconds=breach_value,
                    threshold_seconds=SHAPE_B_THRESHOLD_SECONDS,
                    sample_count=p95_read["sample_count"],
                    query=NFR5_QUERY,
                    depth=NFR5_DEPTH,
                    include_derived=NFR5_INCLUDE_DERIVED,
                )
                shape_b_trigger = record.as_dict()

            run = latest_derivation_run(organization_id)
            if run is None:
                payload: Dict[str, Any] = {
                    "organization_id": organization_id,
                    "state": "not_computed",
                    "reason": DERIVATION_NOT_COMPUTED_REASON,
                    "reasons": [],
                    **_not_computed_counts(),
                    "p95": p95_block,
                    "shape_b_trigger": shape_b_trigger,
                }
            else:
                agg = derived_fact_aggregates(organization_id)
                payload = {
                    "organization_id": organization_id,
                    "state": "computed",
                    "explicit_count": run.explicit_count,
                    "derived_count": run.derived_count,
                    "ratio": float(run.ratio) if run.ratio is not None else None,
                    "computed_at": agg["computed_at"].isoformat() if agg["computed_at"] else None,
                    # D-5 (refuter): the derived-fact store's own computed_at
                    # is honestly null for a tenant whose latest run produced
                    # zero derived facts (nothing lands in
                    # archimate_derived_relationships to stamp). last_run_at
                    # is a distinct fact -- when derivation itself last
                    # genuinely ran, from intelligence_derivation_runs -- so a
                    # measured-zero tenant is not under-reporting a timestamp
                    # the system already has. Never repurposes computed_at,
                    # which still specifically describes store freshness.
                    "last_run_at": run.finished_at.isoformat() if run.finished_at else None,
                    "engine_version": agg["engine_versions"],
                    "stale_count": agg["stale_count"],
                    "last_recompute_duration_ms": run.duration_ms,
                    "p95": p95_block,
                    "shape_b_trigger": shape_b_trigger,
                    "reasons": [],
                }

        return payload

    @staticmethod
    def cross_layer_impact(
        element_id: int,
        *,
        include_derived: bool = True,
        include_stale: bool = False,
        max_depth: int = 3,
        direction: str = "downstream",
        layer: Optional[str] = None,
        with_owner: bool = True,
    ) -> Dict[str, Any]:
        if direction not in VALID_DIRECTIONS:
            raise ValueError(f"direction must be one of {sorted(VALID_DIRECTIONS)}")
        if not (1 <= max_depth <= 5):
            raise ValueError("max_depth must be between 1 and 5")

        org_id = current_org_id()

        with record_query_latency("cross_layer_impact") as scope:
            scope.organization_id = org_id
            scope.depth = max_depth
            scope.include_derived = include_derived

            # The identity map: empty on every branch that returns no rows,
            # otherwise filled below from one tenant-fenced batched select.
            elements: Dict[str, Dict[str, Any]] = {}

            if org_id is None:
                rows: List[Dict[str, Any]] = []
                summary = {
                    "explicit_count": 0,
                    "derived_count": 0,
                    "stale_count": 0,
                    "derivation_state": "not_computed",
                }
                reasons = [NO_TENANT_CONTEXT_REASON]
            else:
                from app.models import ArchiMateElement

                element = db.session.execute(
                    db.select(ArchiMateElement).where(ArchiMateElement.id == element_id)
                ).scalar_one_or_none()

                if element is None:
                    rows = []
                    summary = {
                        "explicit_count": 0,
                        "derived_count": 0,
                        "stale_count": 0,
                        "derivation_state": "not_computed",
                    }
                    reasons = [ELEMENT_NOT_FOUND_REASON]
                else:
                    explicit_rows = _walk_explicit(element_id, max_depth, direction)
                    if layer is not None:
                        explicit_rows = _filter_explicit_by_layer(explicit_rows, layer)

                    src, tgt, dir_kw = _derived_filter_args(element_id, direction)

                    # Fetched regardless of include_derived: the summary's
                    # derivation_state must always be a real measurement,
                    # never fabricated when include_derived=False.
                    all_matching_derived = list_derived_facts(
                        org_id,
                        include_stale=True,
                        source_element_id=src,
                        target_element_id=tgt,
                        max_depth=max_depth,
                        direction=dir_kw,
                        layer=layer,
                    )
                    if not all_matching_derived:
                        derivation_state = "not_computed"
                    elif all(r["stale"] for r in all_matching_derived):
                        derivation_state = "stale"
                    else:
                        derivation_state = "current"

                    derived_rows: List[Dict[str, Any]] = []
                    if _include_derived_gate(include_derived):
                        matching = list_derived_facts(
                            org_id,
                            include_stale=include_stale,
                            source_element_id=src,
                            target_element_id=tgt,
                            max_depth=max_depth,
                            direction=dir_kw,
                            layer=layer,
                        )
                        derived_rows = [_derived_row(fact, element_id) for fact in matching]

                    rows = explicit_rows + derived_rows

                    # Resolve every element id the result set can name in ONE
                    # batched select, INSIDE the latency scope so
                    # ``summary.latency_ms`` and the histogram measure it,
                    # then let the derived rows name both of their ends.
                    elements = _resolve_elements_batch(_element_ids_in_rows(rows), org_id)
                    _attach_plain_terms(rows, elements)

                    # M7 fix: batch owner resolution instead of N+1 --
                    # collect every distinct element id needing a lookup
                    # across the WHOLE result set first, then resolve in a
                    # small constant number of queries.
                    owners_by_element: Dict[int, Tuple[Optional[Dict[str, Any]], Optional[str]]] = {}
                    if with_owner and rows:
                        owners_by_element = _resolve_owners_batch(
                            [row["element_id"] for row in rows], org_id
                        )

                    for row in rows:
                        if with_owner:
                            owner, reason = owners_by_element.get(
                                row["element_id"], (None, NO_OWNERSHIP_REASON)
                            )
                        else:
                            owner, reason = None, None
                        row["owner"] = owner
                        # Derived rows may already carry a staleness reason
                        # (set by _derived_row, e.g. "derivation_stale"). That
                        # takes precedence; an owner-absence reason only fills
                        # in when the row has no reason of its own yet.
                        existing_reason = row.get("reason")
                        row["reason"] = existing_reason if existing_reason else reason
                        # NEW-5: keep element_id on every row -- this task's
                        # whole point is "what stops", so a row that cannot
                        # name what element it is about is not answering the
                        # question. Only the internal join key (_endpoints)
                        # is stripped.
                        row.pop("_endpoints", None)

                    explicit_count = sum(1 for r in rows if r["relation"]["kind"] == "explicit")
                    derived_count = sum(1 for r in rows if r["relation"]["kind"] == "derived")
                    stale_count = sum(1 for r in rows if r["relation"].get("stale"))

                    scope.explicit_rows = explicit_count
                    scope.derived_rows = derived_count
                    scope.stale_rows = stale_count

                    summary = {
                        "explicit_count": explicit_count,
                        "derived_count": derived_count,
                        "stale_count": stale_count,
                        "derivation_state": derivation_state,
                    }
                    reasons = []

        summary["latency_ms"] = scope.latency_ms
        return {"rows": rows, "summary": summary, "reasons": reasons, "elements": elements}

    @staticmethod
    def risk_for_element(
        element_id: int,
        *,
        max_depth: int = 3,
        include_derived: bool = True,
    ) -> Dict[str, Any]:
        """L6, "what could hurt <element>, and what does it touch": every
        ``Risk`` seeded directly on this element (``Risk.archimate_element_id
        == element_id``), each with the SAME blast-radius traversal
        ``cross_layer_impact`` already runs for L1 -- no second traversal
        algorithm, per the platform convention against parallel scoring
        logic.

        Scope note, not silently dropped: ``RiskEntityLink`` (a risk
        threatening an Application/Solution/Programme with no direct
        ``archimate_element_id`` of its own on this element) is not resolved
        here -- none of those three models carry an ArchiMate mirror id
        today, so there is no element to seed a traversal from. Only
        directly-mirrored risks are answered; an indirect risk is invisible
        to this query, not wrongly reported as "none". Tracked as a
        follow-up, not implemented speculatively.

        Score is a **display** label, not a stored fact (per
        ``intelligence-lenses-v1.md`` L6): each risk's own
        ``likelihood x impact`` is shown on its row; when a risk's blast
        radius reaches other elements, the chain's aggregate score is the
        single worst (max) risk reaching it, the conservative choice
        documented in the L3/L6 brief, not a summed exposure figure.
        """
        from app.models.risk import Risk

        org_id = current_org_id()

        with record_query_latency("risk_for_element") as scope:
            scope.organization_id = org_id

            if org_id is None:
                return {
                    "risks": [],
                    "reasons": [NO_TENANT_CONTEXT_REASON],
                    "elements": {},
                }

            from app.models import ArchiMateElement

            element = db.session.execute(
                db.select(ArchiMateElement).where(ArchiMateElement.id == element_id)
            ).scalar_one_or_none()
            if element is None:
                return {
                    "risks": [],
                    "reasons": [ELEMENT_NOT_FOUND_REASON],
                    "elements": {},
                }

            seed_risks = (
                db.session.execute(
                    db.select(Risk).where(Risk.archimate_element_id == element_id)
                )
                .scalars()
                .all()
            )

            if not seed_risks:
                return {
                    "risks": [],
                    "reasons": [NO_RISK_RECORDED_REASON],
                    "elements": {},
                }

            all_elements: Dict[str, Dict[str, Any]] = {}
            risk_payloads: List[Dict[str, Any]] = []
            for risk in seed_risks:
                blast = IntelligenceQueryService.cross_layer_impact(
                    element_id,
                    include_derived=include_derived,
                    max_depth=max_depth,
                    with_owner=True,
                )
                all_elements.update(blast.get("elements") or {})
                risk_payloads.append(
                    {
                        "risk_id": risk.id,
                        "title": risk.title,
                        "status": risk.status.value if risk.status else None,
                        "likelihood": risk.likelihood,
                        "impact": risk.impact,
                        "risk_score": risk.risk_score,
                        "risk_level": risk.risk_level,
                        "owner": risk.owner,
                        "mitigation_plan": risk.mitigation_plan,
                        "affected_rows": blast.get("rows", []),
                        "affected_summary": blast.get("summary", {}),
                    }
                )

        return {"risks": risk_payloads, "reasons": [], "elements": all_elements}

    @staticmethod
    def portfolio_component_for_element(element_id: int) -> Dict[str, Any]:
        """L3, "what do we run, what does it cost, who owns it, what's
        duplicated?": resolves an element to the ``ApplicationComponent``
        row the rationalization/duplicate/TCO pages are keyed on, so the
        caller can build the ONE genuine deep link that exists today
        (``unified_applications.rationalization_planning``).

        No query of its own beyond that resolution -- reuses the exact
        dual-lookup already established in
        ``app/modules/solutions_strategic/v2/routes/strategic_routes.py``
        (the element's own ``application_component_id`` FK first, the
        reverse ``ApplicationComponent.archimate_element_id`` lookup for
        legacy rows second) rather than inventing a second answer to the
        same question.

        Duplicate-detection and TCO history were checked against this same
        brief and found to have NO per-application HTML page today (both
        are JSON-only API endpoints, `GET .../enterprise/analysis/<id>` and
        `GET /api/advanced-tco/history` keyed by `vendor_product_id` not an
        element/app id) -- so this method, deliberately, resolves only what
        the one real page needs. Linking to a JSON response would not be a
        deep link a person can read; not built.
        """
        from app.models import ArchiMateElement
        from app.models.application_portfolio import ApplicationComponent

        org_id = current_org_id()
        if org_id is None:
            return {"application_component_id": None, "reasons": [NO_TENANT_CONTEXT_REASON]}

        element = db.session.execute(
            db.select(ArchiMateElement).where(ArchiMateElement.id == element_id)
        ).scalar_one_or_none()
        if element is None:
            return {"application_component_id": None, "reasons": [ELEMENT_NOT_FOUND_REASON]}

        component = None
        if getattr(element, "application_component_id", None):
            component = db.session.get(ApplicationComponent, element.application_component_id)
        if component is None and (element.type or "") == "ApplicationComponent":
            component = ApplicationComponent.query.filter_by(archimate_element_id=element.id).first()

        if component is None:
            return {"application_component_id": None, "reasons": [NO_APPLICATION_COMPONENT_REASON]}

        return {"application_component_id": component.id, "reasons": []}

    @staticmethod
    def programme_for_element(
        element_id: int,
        *,
        max_depth: int = 3,
        include_derived: bool = True,
    ) -> Dict[str, Any]:
        """L5, "what are we changing, is it on time and on budget, what does
        each change touch?": every ``UnifiedWorkPackage`` seeded directly on
        the picked element (``archimate_element_id`` FK), each with the SAME
        blast-radius traversal L1/L6 already run -- no second traversal
        algorithm.

        Tenant-safety note, verified not assumed: ``UnifiedWorkPackage``
        carries no ``TenantMixin``/``organization_id`` of its own. This
        method never lists work packages independently of an element --
        every row it returns is filtered by ``archimate_element_id ==
        element_id``, and ``element_id`` is only ever reached here after
        the element itself was confirmed to belong to the caller's tenant
        (below). A cross-tenant work package cannot share a seed element id
        with the wrong org's element, since ``archimate_elements.id`` is a
        real primary key each row of which belongs to exactly one tenant.
        This does not make ``UnifiedWorkPackage`` itself tenant-safe for any
        OTHER read path against it -- flagged as a separate, pre-existing
        gap in the L5 brief, not fixed here.

        Cost variance is read from the model's own ``estimated_cost``/
        ``actual_cost`` fields directly, NOT via
        ``UnifiedWorkPackage.calculate_budget_variance()`` -- that helper
        returns a bare 0 both when there is no cost data and when the
        package is exactly on budget, the same not-computed-vs-measured-
        zero collision CLAUDE.md's no-fabrication rule exists to catch.
        Variance is only reported when ``estimated_cost`` is a real
        positive number; otherwise the row carries the honest
        ``not_costed`` reason.
        """
        from app.models import ArchiMateElement
        from app.models.unified_work_package import UnifiedWorkPackage

        org_id = current_org_id()

        with record_query_latency("programme_for_element") as scope:
            scope.organization_id = org_id

            if org_id is None:
                return {
                    "work_packages": [],
                    "reasons": [NO_TENANT_CONTEXT_REASON],
                    "elements": {},
                }

            element = db.session.execute(
                db.select(ArchiMateElement).where(ArchiMateElement.id == element_id)
            ).scalar_one_or_none()
            if element is None:
                return {
                    "work_packages": [],
                    "reasons": [ELEMENT_NOT_FOUND_REASON],
                    "elements": {},
                }

            seed_packages = (
                db.session.execute(
                    db.select(UnifiedWorkPackage).where(
                        UnifiedWorkPackage.archimate_element_id == element_id
                    )
                )
                .scalars()
                .all()
            )

            if not seed_packages:
                return {
                    "work_packages": [],
                    "reasons": [NO_WORK_PACKAGE_RECORDED_REASON],
                    "elements": {},
                }

            from app.models.user import User

            owner_ids = {wp.owner_id for wp in seed_packages if wp.owner_id}
            owners_by_id: Dict[int, str] = {}
            if owner_ids:
                for user in db.session.execute(
                    db.select(User).where(User.id.in_(owner_ids))
                ).scalars():
                    owners_by_id[user.id] = user.full_name or user.email

            all_elements: Dict[str, Dict[str, Any]] = {}
            wp_payloads: List[Dict[str, Any]] = []
            for wp in seed_packages:
                blast = IntelligenceQueryService.cross_layer_impact(
                    element_id,
                    include_derived=include_derived,
                    max_depth=max_depth,
                    with_owner=True,
                )
                all_elements.update(blast.get("elements") or {})

                if wp.estimated_cost and wp.estimated_cost > 0:
                    cost_variance_pct = (
                        (wp.actual_cost or 0.0) - wp.estimated_cost
                    ) / wp.estimated_cost * 100
                    cost_reason = None
                else:
                    cost_variance_pct = None
                    cost_reason = NOT_COSTED_REASON

                wp_payloads.append(
                    {
                        "work_package_id": wp.id,
                        "name": wp.name,
                        "status": wp.status,
                        "progress_percentage": wp.progress_percentage,
                        "start_date": wp.start_date.isoformat() if wp.start_date else None,
                        "end_date": wp.end_date.isoformat() if wp.end_date else None,
                        "is_overdue": wp.is_overdue(),
                        "owner": owners_by_id.get(wp.owner_id),
                        "cost_variance_pct": cost_variance_pct,
                        "cost_reason": cost_reason,
                        "affected_rows": blast.get("rows", []),
                        "affected_summary": blast.get("summary", {}),
                    }
                )

        return {"work_packages": wp_payloads, "reasons": [], "elements": all_elements}

    # ------------------------------------------------------------------ #
    # T-S1: value streams at risk -- the curated path (DA-S1). Helpers are
    # staticmethods immediately above the method itself, inside the class,
    # per the implementation plan's free-region rule for this file (plan
    # § 5.2) -- not module-level functions near ``_not_computed_counts``.
    # ------------------------------------------------------------------ #

    @staticmethod
    def _value_stream_tenant_predicate(model, organization_id: int):
        """The explicit ``organization_id ==`` predicate ``ValueStream``,
        ``CapabilityValueStreamMapping`` and ``ValueStreamStage`` each carry
        on this path, isolated as its own seam -- the same pattern as
        ``derived_facts._apply_default_staleness_filter`` -- so the
        cross-tenant mutation-proof test can monkeypatch exactly this one
        function to a no-op and confirm the named test goes red, without
        editing source under test or inlining the predicate separately at
        each of the three call sites.

        All three models already carry ``TenantMixin``, so this predicate is
        defence in depth inside a request and is what keeps the method
        correct when called with no ambient request context (a job, a CLI
        command, a test looping tenants in one session), where the ORM
        listener would otherwise no-op entirely.
        """
        return model.organization_id == organization_id

    @staticmethod
    def _at_risk_for_maturity(current_maturity: Optional[int], threshold: int) -> Optional[bool]:
        """Whether a capability counts as at risk, isolated as its own seam
        so the mutation-proof test (acceptance item 11) can monkeypatch
        exactly this function to always return ``False`` for a null maturity
        and confirm the null-maturity-is-neutral test goes red, without
        editing source under test.

        ``None`` in, ``None`` out -- a capability with no maturity recorded
        is neither at risk nor safe (US-2 AC-2), never ``False``.
        """
        if current_maturity is None:
            return None
        return current_maturity < threshold

    @staticmethod
    def value_streams_at_risk(
        organization_id: int,
        *,
        threshold: int = 3,
        value_stream_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """T-S1 (DA-S1, ADR-S1, ADR-S2): "which value streams depend on a
        capability below *threshold*" -- the curated path only. A person's
        own ``capability_value_stream_mapping`` row is the whole of the
        evidence; there is no graph read here (no derived fact, no
        explicit-relationship walk) and no ``include_derived`` /
        ``include_stale`` / ``max_depth`` parameter -- those belong to T-S3.

        Four batched selects regardless of row count, in this order,
        following ``_resolve_owners_batch``'s own collect-then-resolve shape:
        value streams for the tenant (narrowed by ``value_stream_id`` when
        given); mapping rows for those value-stream ids, joined to
        ``ValueStreamStage`` for the stage id and name; capability identity
        for the distinct capability ids; maturity through the accessor.
        Never one select per row.

        Tenancy (design § 3.2): ``ValueStream``,
        ``CapabilityValueStreamMapping`` and ``ValueStreamStage`` each carry
        the strict, explicit predicate through
        ``_value_stream_tenant_predicate``. ``UnifiedCapability`` is read
        TWICE with two deliberately different predicates -- identity uses
        the permissive ``or_(... is_(None))``, written out in full below,
        because a tenant's own mapping row may name a shared catalogue
        capability and that mapping is honoured; maturity uses the strict
        accessor (``maturity_for_capability_ids``, ``organization_id``
        required), so a shared catalogue row contributes its mapping and
        never its maturity -- a shared number is not this tenant's
        assessment. Maturity is read only through the accessor; no module on
        this path reads ``current_maturity_level`` off a row directly.
        """
        from app.models.unified_capability import (
            CapabilityValueStreamMapping,
            UnifiedCapability,
            ValueStream,
            ValueStreamStage,
        )

        with record_query_latency("value_streams_at_risk") as scope:
            scope.organization_id = organization_id

            vs_stmt = db.select(ValueStream).where(
                IntelligenceQueryService._value_stream_tenant_predicate(
                    ValueStream, organization_id
                )
            )
            if value_stream_id is not None:
                vs_stmt = vs_stmt.where(ValueStream.id == value_stream_id)
            value_streams = (
                db.session.execute(vs_stmt.order_by(ValueStream.id)).scalars().all()
            )

            if not value_streams:
                rows: List[Dict[str, Any]] = []
                summary: Dict[str, Any] = {
                    "value_streams_considered": 0,
                    "value_streams_at_risk": 0,
                    "capabilities_considered": 0,
                    "capabilities_below_threshold": 0,
                    "capabilities_with_no_maturity": 0,
                    "value_streams_not_linked_to_model": 0,
                }
                reasons = [validate_reason_code("no_value_stream_recorded")]
            else:
                vs_ids = [vs.id for vs in value_streams]

                mapping_stmt = (
                    db.select(CapabilityValueStreamMapping, ValueStreamStage)
                    .join(
                        ValueStreamStage,
                        CapabilityValueStreamMapping.value_stream_stage_id
                        == ValueStreamStage.id,
                    )
                    .where(
                        CapabilityValueStreamMapping.value_stream_id.in_(vs_ids),
                        IntelligenceQueryService._value_stream_tenant_predicate(
                            CapabilityValueStreamMapping, organization_id
                        ),
                        IntelligenceQueryService._value_stream_tenant_predicate(
                            ValueStreamStage, organization_id
                        ),
                    )
                    .order_by(CapabilityValueStreamMapping.id)
                )
                mapping_rows = db.session.execute(mapping_stmt).all()

                capability_ids = sorted({m.capability_id for m, _stage in mapping_rows})

                identity_by_id: Dict[int, Dict[str, Any]] = {}
                if capability_ids:
                    identity_stmt = db.select(
                        UnifiedCapability.id,
                        UnifiedCapability.name,
                        UnifiedCapability.code,
                    ).where(
                        UnifiedCapability.id.in_(capability_ids),
                        # Permissive predicate, written out in full (§ 3.2):
                        # a tenant's own mapping row may name a shared
                        # catalogue capability, and that mapping is honoured.
                        db.or_(
                            UnifiedCapability.organization_id == organization_id,
                            UnifiedCapability.organization_id.is_(None),
                        ),
                    )
                    for cap_id, name, code in db.session.execute(identity_stmt).all():
                        identity_by_id[cap_id] = {"id": cap_id, "name": name, "code": code}

                # Maturity through the accessor -- never off the columns.
                # Strict predicate, required kwarg: a shared catalogue row's
                # maturity is never read as this tenant's own.
                maturity_by_id = UnifiedCapability.maturity_for_capability_ids(
                    capability_ids, organization_id=organization_id
                )

                mappings_by_vs: Dict[int, List[Tuple[Any, Any]]] = {}
                for mapping, stage in mapping_rows:
                    mappings_by_vs.setdefault(mapping.value_stream_id, []).append(
                        (mapping, stage)
                    )

                rows = []
                value_streams_at_risk_count = 0
                capabilities_considered: set = set()
                capabilities_below_threshold = 0
                capabilities_with_no_maturity = 0
                value_streams_not_linked_to_model = 0

                for vs in value_streams:
                    if vs.archimate_element_id is None:
                        value_streams_not_linked_to_model += 1

                    capability_rows: List[Dict[str, Any]] = []
                    at_risk_count = 0
                    for mapping, stage in mappings_by_vs.get(vs.id, []):
                        identity = identity_by_id.get(mapping.capability_id)
                        if identity is None:
                            # Named by this tenant's own mapping row but not
                            # resolvable under either predicate (deleted, or
                            # never existed) -- omitted rather than
                            # fabricated with a placeholder name.
                            continue
                        capabilities_considered.add(mapping.capability_id)

                        maturity = maturity_by_id.get(mapping.capability_id) or {
                            "current_maturity_level": None,
                            "target_maturity_level": None,
                            "reason_code": validate_reason_code("no_maturity_recorded"),
                        }
                        current = maturity["current_maturity_level"]
                        target = maturity["target_maturity_level"]
                        at_risk = IntelligenceQueryService._at_risk_for_maturity(
                            current, threshold
                        )
                        if current is None:
                            capabilities_with_no_maturity += 1
                            cap_reason = maturity["reason_code"]
                        else:
                            cap_reason = None
                            if at_risk:
                                at_risk_count += 1
                                capabilities_below_threshold += 1

                        capability_rows.append(
                            {
                                "id": identity["id"],
                                "name": identity["name"],
                                "code": identity["code"],
                                "current_maturity": current,
                                "target_maturity": target,
                                "maturity_source": "unified_capabilities",
                                "at_risk": at_risk,
                                "dependency": {
                                    "link_kind": "curated",
                                    "support_type": mapping.support_type,
                                    "support_level": mapping.support_level,
                                    "impact_level": mapping.impact_level,
                                    "stage": (
                                        {"id": stage.id, "name": stage.name}
                                        if stage is not None
                                        else None
                                    ),
                                },
                                "reason": cap_reason,
                            }
                        )

                    row_reason = (
                        validate_reason_code("no_capability_linked")
                        if not capability_rows
                        else None
                    )

                    rows.append(
                        {
                            "value_stream": {
                                "id": vs.id,
                                "name": vs.name,
                                "code": vs.code,
                                "archimate_element_id": vs.archimate_element_id,
                            },
                            "at_risk_capability_count": at_risk_count,
                            "capabilities": capability_rows,
                            "reason": row_reason,
                        }
                    )
                    if at_risk_count > 0:
                        value_streams_at_risk_count += 1

                summary = {
                    "value_streams_considered": len(value_streams),
                    "value_streams_at_risk": value_streams_at_risk_count,
                    "capabilities_considered": len(capabilities_considered),
                    "capabilities_below_threshold": capabilities_below_threshold,
                    "capabilities_with_no_maturity": capabilities_with_no_maturity,
                    "value_streams_not_linked_to_model": value_streams_not_linked_to_model,
                }
                reasons = []

        summary["latency_ms"] = scope.latency_ms
        return {
            "threshold": threshold,
            "threshold_basis": "current_maturity_level < threshold",
            "rows": rows,
            "summary": summary,
            "reasons": reasons,
        }


__all__ = ["IntelligenceQueryService"]
