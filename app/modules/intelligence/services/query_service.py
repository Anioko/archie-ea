"""Cross-layer intelligence queries. One method -- ``cross_layer_impact``,
"if this fails, what stops and who owns it". Value-streams-at-risk / risk
/ coverage are Release 2 and are not added here.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.extensions import db
from app.middleware.tenant_context import current_org_id
from app.modules.intelligence.services.derived_facts import list_derived_facts
from app.modules.intelligence.services.latency_probe import record_query_latency
from app.modules.intelligence.services.plain_terms import plain_terms_sentence
from app.modules.intelligence.services.reason_codes import validate_reason_code

logger = logging.getLogger(__name__)

VALID_DIRECTIONS = {"downstream", "upstream", "both"}

NO_OWNERSHIP_REASON = validate_reason_code("no_ownership_recorded")
NO_TENANT_CONTEXT_REASON = validate_reason_code("no_tenant_context")
ELEMENT_NOT_FOUND_REASON = validate_reason_code("element_not_found")
DERIVATION_NOT_COMPUTED_REASON = validate_reason_code("derivation_not_computed")
NO_RECOMPUTE_DURATION_REASON = validate_reason_code("no_recompute_duration_recorded")
SOURCE_UNAVAILABLE_REASON = validate_reason_code("source_unavailable")
DRIFT_COUNT_NOT_REQUESTED_REASON = validate_reason_code("drift_count_not_requested")
MODEL_TOO_LARGE_REASON = validate_reason_code("model_too_large_for_drift_check")

# T-005 (D1): the NFR-5 measurement point is this exact, PINNED series --
# never widened, never aggregated across label values.
NFR5_QUERY = "cross_layer_impact"
NFR5_DEPTH = "4"
NFR5_INCLUDE_DERIVED = "true"

# T-005 (ADR-009): NFR-5's stated measurement threshold. Appears only as the
# Shape-B trigger's threshold_seconds -- never as a yield target (task 02
# constraint: no fabricated target anywhere in the payload).
SHAPE_B_THRESHOLD_SECONDS = 2.0

# One observation per request, on the request's own series of the query-latency
# histogram. Neither is the pinned response-time series above, which stays the
# only one the response-time figure reads.
DERIVATION_YIELD_SERIES = "derivation_yield"
MODEL_DRIFT_SERIES = "model_drift_count"

# The model check runs the drift detector, whose near-duplicate stage compares
# every pair of same-layer names, so its cost grows with the square of the
# element count: about 1.4 s at 1,000 elements, 5.7 s at 2,000 and 13 s at
# 3,000 on a model with no findings, and past the worker's time limit near
# 10,000. Above this many elements the model check does not run it and says so.
# The bound is enforced before the work starts, by size, because a clock that
# fires part way through would already have spent the worker.
DRIFT_COUNT_MAX_ELEMENTS = 1000


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


def _detector_total(organization_id: int) -> Tuple[Optional[int], Optional[str]]:
    """The drift detector's total for the tenant, or ``None`` and a reason.

    This is the only place the detector is called from, and only the model
    check reaches it (behind the size guard). Only the report's own
    ``summary["total"]`` is read; the findings, their severities and their
    fixes belong to the page that owns them. A detector that cannot be read is
    reported as unavailable, never as a count of zero, which would read as "no
    drift". A total that is not a non-negative whole number (a negative, a
    boolean, a fraction, a string) is not a count of anything and is reported
    the same way.
    """
    try:
        from app.modules.genome.services.drift_detector import detect_model_drift

        total = detect_model_drift(organization_id)["summary"]["total"]
    except Exception:
        logger.warning(
            "intelligence.yield: the drift detector could not be read for organization %s",
            organization_id,
            exc_info=True,
        )
        # A failed read can leave the session mid-transaction; the rest of the
        # request still needs it.
        db.session.rollback()
        return None, SOURCE_UNAVAILABLE_REASON
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        logger.warning(
            "intelligence.yield: the drift detector returned %r as its total for organization %s",
            total,
            organization_id,
        )
        return None, SOURCE_UNAVAILABLE_REASON
    return total, None


class IntelligenceQueryService:
    """DE-9: read-only cross-layer intelligence queries."""

    @staticmethod
    def derivation_yield(organization_id: int) -> Dict[str, Any]:
        """DE-11 (US-5): "how much does derivation add, and how fresh is it",
        for one tenant: the figures read of the yield endpoint.

        Every count is the tenant's own and every absent value is ``None``
        with a reason code in ``reasons``, never a zero:

        - ``explicit_count`` is the tenant's explicit relationship rows, the
          same rows the derivation runner counts.
        - ``derived_count`` is every row the derived-fact store holds for the
          tenant, current and stale. (The aggregate's ``current_count`` is a
          different number: the rows that are not stale.) ``stale_count`` is
          the part of ``derived_count`` that has gone out of date. ``ratio`` is
          ``derived_count`` over ``explicit_count``, ``None`` when there are no
          explicit relationships.
        - ``state`` is ``not_computed`` when derivation has never run for the
          tenant (no run record and no stored fact), ``stale`` when any stored
          fact is out of date, else ``current``. A run that derived nothing is
          ``current`` with a derived count of zero: a measured zero, which
          reads differently from never having run.
        - ``explicit_count``/``derived_count``/``ratio``/
          ``last_recompute_duration_ms`` come from the tenant's
          ``DerivationRun`` row itself -- the SAME values the recompute
          response already returns (two surfaces, one answer; a store-
          agreement test pins this). ``computed_at``/``engine_version``/
          ``stale_count`` come from ``derived_fact_aggregates`` -- the store's
          OWN current state (never the ``ENGINE_VERSION`` module constant).
        - ``last_recompute_duration_ms`` is the last completed run's own
          measured duration, ``None`` with ``no_recompute_duration_recorded``
          when there is no run to read it from.
        - ``p95_latency_seconds`` and ``sample_count`` are read from one
          pinned label set of the query-latency histogram (see
          ``read_p95_bucket_edge``) via a bucket-edge read -- never computed
          in application code, never widened, never aggregated across label
          values; the same reading is carried, with its scope, in the nested
          ``p95`` block. It is process-local and estate-wide, not per tenant,
          so it is reported as its own nested, self-describing block on BOTH
          branches (it measures query latency, not derivation -- suppressing
          it on the not-computed branch would hide a real breach).
        - ``drift_finding_count`` is always ``None`` here, with
          ``drift_count_not_requested`` in ``reasons``: this read never runs
          the drift detector. The model check (``model_check``) is the read
          that does.

        The whole read, including the assembly of the payload, is inside its
        one timed block, so its observation is the request's own time.
        """
        from app.modules.intelligence.services.derived_facts import (
            derived_fact_aggregates,
            explicit_relationship_count,
            latest_derivation_run,
        )
        from app.modules.intelligence.services.latency_probe import read_p95_bucket_edge
        from app.modules.intelligence.services.observability import record_shape_b_trigger

        # This read is wrapped in its OWN series (query="derivation_yield")
        # -- the p95 read below is pinned to "cross_layer_impact" only, and is
        # therefore unaffected by calling this endpoint repeatedly.
        with record_query_latency(DERIVATION_YIELD_SERIES) as scope:
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

            # A real value OR the honest "exceeds the highest declared
            # bucket" fact both constitute a genuine breach signal -- the
            # Shape-B trigger fires on either, never only on the interpolated
            # case.
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
            agg = derived_fact_aggregates(organization_id)
            computed = run is not None or agg["total_count"] > 0

            reasons: List[str] = []
            if not computed:
                reasons.append(DERIVATION_NOT_COMPUTED_REASON)
            if p95_read["reason"] is not None:
                reasons.append(validate_reason_code(p95_read["reason"]))
            duration_ms = run.duration_ms if run is not None else None
            if duration_ms is None:
                reasons.append(NO_RECOMPUTE_DURATION_REASON)
            reasons.append(DRIFT_COUNT_NOT_REQUESTED_REASON)

            payload: Dict[str, Any] = {
                "organization_id": organization_id,
                "p95_latency_seconds": p95_read["latency_seconds"],
                "sample_count": p95_read["sample_count"],
                "p95": p95_block,
                "shape_b_trigger": shape_b_trigger,
                "last_recompute_duration_ms": duration_ms,
                "drift_finding_count": None,
            }
            if not computed:
                payload.update(
                    {
                        "state": "not_computed",
                        "reason": DERIVATION_NOT_COMPUTED_REASON,
                        **_not_computed_counts(),
                    }
                )
            else:
                explicit_count = explicit_relationship_count(organization_id)
                derived_count = agg["total_count"]
                payload.update(
                    {
                        "state": "stale" if agg["stale_count"] > 0 else "current",
                        "explicit_count": explicit_count,
                        "derived_count": derived_count,
                        "ratio": (derived_count / explicit_count) if explicit_count else None,
                        "computed_at": agg["computed_at"].isoformat() if agg["computed_at"] else None,
                        # A run that derived nothing leaves no stored fact to
                        # stamp, so the store's own ``computed_at`` is honestly
                        # null for it. ``last_run_at`` is a distinct fact: when
                        # derivation itself last finished, from the run record.
                        # It never stands in for ``computed_at``, which
                        # describes the freshness of the stored facts.
                        "last_run_at": (
                            run.finished_at.isoformat() if run is not None and run.finished_at else None
                        ),
                        "engine_version": (
                            agg["engine_versions"]
                            or ([run.engine_version] if run is not None and run.engine_version else None)
                        ),
                        "stale_count": agg["stale_count"],
                    }
                )
            payload["reasons"] = reasons

        return payload

    @staticmethod
    def model_check(organization_id: int) -> Dict[str, Any]:
        """DE-11 (US-5): the model-check read of the yield endpoint: how many
        things the drift detector found in the tenant's model.

        The detector's cost grows with the square of the element count, so it
        runs only when the tenant has ``DRIFT_COUNT_MAX_ELEMENTS`` elements or
        fewer. Above that the answer is ``drift_finding_count: None`` with
        ``model_too_large_for_drift_check``, and the detector is never called.
        A detector that raises, or returns a total that is not a non-negative
        whole number, is ``None`` with ``source_unavailable``. A count of zero
        is only ever a detector's own zero.

        ``element_count`` is the number of elements the size guard measured.
        The whole read (the element count, the comparison and the detector call
        when it happens) is inside one timed block, on the model check's own
        series, and nothing is added to the answer after the block closes.
        """
        from app.modules.intelligence.services.derived_facts import active_element_count

        with record_query_latency(MODEL_DRIFT_SERIES) as scope:
            scope.organization_id = organization_id

            element_count = active_element_count(organization_id)
            reasons: List[str] = []
            if element_count > DRIFT_COUNT_MAX_ELEMENTS:
                drift_finding_count: Optional[int] = None
                reasons.append(MODEL_TOO_LARGE_REASON)
            else:
                drift_finding_count, reason = _detector_total(organization_id)
                if reason is not None:
                    reasons.append(reason)

            payload: Dict[str, Any] = {
                "organization_id": organization_id,
                "drift_finding_count": drift_finding_count,
                "element_count": element_count,
                "reasons": reasons,
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


__all__ = ["IntelligenceQueryService"]
