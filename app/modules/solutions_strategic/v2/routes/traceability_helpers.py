"""
Traceability helpers for solution derivation chains.

Provides parse/build utilities for prefixed IDs used in LLM prompts/responses,
and persistence/query functions for TraceabilityLink rows scoped to a solution.
"""

import logging

from app import db
from app.models.traceability import TraceabilityLink
from app.models.solution_architect_models import SolutionDriver, SolutionGoal

logger = logging.getLogger(__name__)

# Maps short prefix → entity type string
PREFIX_MAP = {
    "drv": "Driver",
    "goal": "Goal",
    "con": "Constraint",
    "cap": "BusinessCapability",
    "elem": "ArchimateElement",
}

# Reverse map: entity type → short prefix
_REVERSE_PREFIX_MAP = {v: k for k, v in PREFIX_MAP.items()}
# SolutionCapability is a special case not in PREFIX_MAP
_REVERSE_PREFIX_MAP["SolutionCapability"] = "sol_cap"


def parse_prefixed_id(prefixed_id) -> tuple:
    """
    Parse a type-prefixed ID string into (entity_type, entity_id).

    Examples:
        "drv_42"      → ("Driver", 42)
        "goal_67"     → ("Goal", 67)
        "con_89"      → ("Constraint", 89)
        "cap_5"       → ("BusinessCapability", 5)
        "sol_cap_12"  → ("SolutionCapability", 12)
        "elem_101"    → ("ArchimateElement", 101)
        anything else → (None, None)
    """
    if not isinstance(prefixed_id, str):
        return (None, None)

    prefixed_id = prefixed_id.strip()
    if not prefixed_id:
        return (None, None)

    # Special case: sol_cap_ must be checked before the generic split
    if prefixed_id.startswith("sol_cap_"):
        raw_id = prefixed_id[len("sol_cap_"):]
        try:
            return ("SolutionCapability", int(raw_id))
        except (ValueError, TypeError):
            return (None, None)

    # Generic case: split on first underscore only
    if "_" not in prefixed_id:
        return (None, None)

    prefix, _, raw_id = prefixed_id.partition("_")
    entity_type = PREFIX_MAP.get(prefix)
    if entity_type is None:
        return (None, None)

    try:
        return (entity_type, int(raw_id))
    except (ValueError, TypeError):
        return (None, None)


def build_prefixed_id(entity_type: str, entity_id: int) -> str:
    """
    Build a type-prefixed ID string from entity type and ID.

    Examples:
        ("Driver", 42)              → "drv_42"
        ("SolutionCapability", 12)  → "sol_cap_12"

    Returns empty string for unknown entity types.
    """
    prefix = _REVERSE_PREFIX_MAP.get(entity_type)
    if prefix is None:
        return ""
    return f"{prefix}_{entity_id}"


def persist_traceability_links(
    solution_id: int,
    items: list,
    ref_field: str,
    item_id_field: str,
    item_type_field: str,
    traceability_layer: str,
    valid_source_ids: set,
) -> tuple:
    """
    Persist TraceabilityLink rows derived from an LLM response.

    For each item in `items`, reads item[ref_field] (a list of prefixed IDs),
    validates each ref against valid_source_ids, parses it, and creates a
    TraceabilityLink row pointing from the source element to the item.

    Returns:
        (links_created, hallucinations_skipped)
    """
    links_created = 0
    hallucinations_skipped = 0

    for item in items:
        target_id = item.get(item_id_field)
        target_type = item.get(item_type_field)

        if target_id is None or target_type is None:
            continue

        refs = item.get(ref_field)

        # Normalise: None → skip; non-list → try wrapping
        if refs is None:
            continue
        if not isinstance(refs, list):
            refs = [refs]

        for ref in refs:
            if not isinstance(ref, str):
                hallucinations_skipped += 1
                continue

            ref = ref.strip()

            # Validate against the set of known source IDs
            if ref not in valid_source_ids:
                hallucinations_skipped += 1
                logger.debug(
                    "Traceability hallucination skipped: %s not in valid_source_ids",
                    ref,
                )
                continue

            source_type, source_id = parse_prefixed_id(ref)
            if source_type is None:
                hallucinations_skipped += 1
                continue

            link = TraceabilityLink(
                source_element_type=source_type,
                source_element_id=source_id,
                target_element_type=target_type,
                target_element_id=target_id,
                traceability_type="derivation",
                traceability_layer=traceability_layer,
                confidence_score=0.8,
                validated=False,
                validation_method="ai_derived",
                solution_id=solution_id,
            )
            db.session.add(link)
            links_created += 1

    if links_created > 0:
        db.session.commit()

    return (links_created, hallucinations_skipped)


def _load_name_maps(solution_id: int) -> dict:
    """Load entity name lookup maps for a solution. Returns dict of dicts keyed by (type, id)."""
    names = {}

    # Capabilities (BusinessCapability + SolutionCapability)
    # Load id/name only — avoids loading all columns for large catalogs.
    _NAME_LIMIT = 5_000  # safety cap; log a warning if hit
    try:
        from app import db as _db
        from app.models.business_capabilities import BusinessCapability
        rows = _db.session.query(BusinessCapability.id, BusinessCapability.name).limit(_NAME_LIMIT).all()
        if len(rows) == _NAME_LIMIT:
            logger.warning("BusinessCapability name lookup hit safety cap (%d). Some names may be unresolved.", _NAME_LIMIT)
        for c_id, c_name in rows:
            names[("BusinessCapability", c_id)] = c_name
    except Exception as exc:
        logger.debug("Failed to load BusinessCapability names: %s", exc)
    try:
        from app.models.solution_capability import SolutionCapability
        for c in SolutionCapability.query.filter_by(solution_id=solution_id).all():
            names[("SolutionCapability", c.id)] = c.name
    except Exception as exc:
        logger.debug("Failed to load SolutionCapability names: %s", exc)

    # ArchiMate elements — load id/name only to avoid loading all columns for 2,763+ elements.
    try:
        from app import db as _db
        from app.models.archimate import ArchiMateElement
        rows = _db.session.query(ArchiMateElement.id, ArchiMateElement.name).limit(_NAME_LIMIT).all()
        if len(rows) == _NAME_LIMIT:
            logger.warning("ArchiMateElement name lookup hit safety cap (%d). Some names may be unresolved.", _NAME_LIMIT)
        for e_id, e_name in rows:
            names[("ArchimateElement", e_id)] = e_name
    except Exception as exc:
        logger.debug("Failed to load ArchiMateElement names: %s", exc)

    # Implementation elements (WorkPackage, Gap, Plateau, Deliverable) — also ArchiMateElement
    # Already covered above since they're stored as ArchiMateElements

    return names


def build_traceability(solution_id: int) -> dict:
    """
    Build the full traceability chain for a solution.

    Queries all derivation TraceabilityLink rows for the solution, groups them
    by layer, and walks the chain:
        drivers/goals → capabilities → elements → work packages

    Returns:
        {
            "chains": [...],       # list of chain dicts, one per motivation element
            "orphans": {...},      # elements with no upstream link, keyed by layer
            "completeness": {...}, # coverage percentages per layer
        }
    """
    links = (
        TraceabilityLink.query.filter_by(
            solution_id=solution_id,
            traceability_type="derivation",
        ).all()
    )

    # Group links by traceability_layer
    by_layer = {
        "motivation_to_capability": [],
        "capability_to_element": [],
        "element_to_implementation": [],
    }
    for link in links:
        layer = link.traceability_layer
        if layer in by_layer:
            by_layer[layer].append(link)

    # Load motivation elements for display names
    drivers = SolutionDriver.query.filter_by(solution_id=solution_id).all()
    goals = SolutionGoal.query.filter_by(solution_id=solution_id).all()

    # Load entity names for all types
    name_map = _load_name_maps(solution_id)

    def _resolve_name(entity_type, entity_id):
        return name_map.get((entity_type, entity_id), f"{entity_type} #{entity_id}")

    # Build lookup: (source_type, source_id) → list of target links
    def _build_source_index(layer_links):
        index = {}
        for lnk in layer_links:
            key = (lnk.source_element_type, lnk.source_element_id)
            index.setdefault(key, []).append(lnk)
        return index

    m2c_index = _build_source_index(by_layer["motivation_to_capability"])
    c2e_index = _build_source_index(by_layer["capability_to_element"])
    e2i_index = _build_source_index(by_layer["element_to_implementation"])

    chains = []

    # Walk from each driver
    for driver in drivers:
        name = driver.name or f"Driver {driver.id}"
        chain = _walk_chain(
            source_type="Driver",
            source_id=driver.id,
            display_name=name,
            prefixed_id=f"drv_{driver.id}",
            m2c_index=m2c_index,
            c2e_index=c2e_index,
            e2i_index=e2i_index,
            resolve_name=_resolve_name,
        )
        chains.append(chain)

    # Walk from each goal
    for goal in goals:
        name = goal.name or f"Goal {goal.id}"
        chain = _walk_chain(
            source_type="Goal",
            source_id=goal.id,
            display_name=name,
            prefixed_id=f"goal_{goal.id}",
            m2c_index=m2c_index,
            c2e_index=c2e_index,
            e2i_index=e2i_index,
            resolve_name=_resolve_name,
        )
        chains.append(chain)

    # Detect orphans
    def _collect_targets(layer_links):
        return {(lnk.target_element_type, lnk.target_element_id) for lnk in layer_links}

    def _collect_sources(layer_links):
        return {(lnk.source_element_type, lnk.source_element_id) for lnk in layer_links}

    cap_targets = _collect_targets(by_layer["motivation_to_capability"])
    elem_sources = _collect_sources(by_layer["capability_to_element"])
    elem_targets = _collect_targets(by_layer["capability_to_element"])
    impl_sources = _collect_sources(by_layer["element_to_implementation"])

    # Drivers/goals without any capability link
    motivation_ids = {("Driver", d.id) for d in drivers} | {("Goal", g.id) for g in goals}
    linked_motivations = _collect_sources(by_layer["motivation_to_capability"])
    drivers_without = [
        {"type": t, "id": i, "name": _resolve_name(t, i) if t not in ("Driver", "Goal") else (
            (driver.name or f"Driver {driver.id}") if t == "Driver" else (goal.name or f"Goal {goal.id}")
            for driver in drivers if driver.id == i for _ in [None]
        ) if False else next(
            (d.name or f"Driver {d.id}" for d in drivers if d.id == i and t == "Driver"),
            next((g.name or f"Goal {g.id}" for g in goals if g.id == i and t == "Goal"), f"{t} #{i}")
        )}
        for t, i in motivation_ids - linked_motivations
    ]

    orphans = {
        "drivers_without_capabilities": drivers_without,
        "elements_without_capabilities": [
            {"type": t, "id": i, "name": _resolve_name(t, i)}
            for t, i in elem_sources - cap_targets
        ],
        "work_packages_without_elements": [
            {"type": t, "id": i, "name": _resolve_name(t, i)}
            for t, i in impl_sources - elem_targets
        ],
    }

    # Completeness per layer — use frontend-expected keys
    def _completeness(covered_set, total_set):
        total = len(total_set)
        covered = len(covered_set & total_set)
        percentage = round(covered / total * 100) if total > 0 else 0
        return {"covered": covered, "total": total, "percentage": percentage}

    completeness = {
        "drivers_to_capabilities": _completeness(
            linked_motivations, motivation_ids,
        ),
        "capabilities_to_elements": _completeness(
            elem_sources, cap_targets,
        ),
        "elements_to_work_packages": _completeness(
            impl_sources, elem_targets,
        ),
    }

    return {
        "chains": chains,
        "orphans": orphans,
        "completeness": completeness,
    }


def match_capability_names_to_prefixed_ids(
    items: list,
    name_field: str,
    capabilities: list,
) -> list:
    """Inject 'driven_by' prefixed IDs into LLM-generated items by matching capability_name.

    The orchestrator prompts use capability_name (string) for traceability.
    This function converts those names to prefixed IDs so persist_traceability_links() can use them.

    Args:
        items: List of dicts from orchestrator (each has a name_field like 'capability_name')
        name_field: Key containing the capability name (e.g., 'capability_name')
        capabilities: List of dicts with 'name' and 'prefixed_id' from the frontend

    Returns:
        Same items list with 'driven_by' field added to each item.
    """
    # Build name → prefixed_id lookup (case-insensitive)
    name_to_pid = {}
    for cap in capabilities:
        if cap.get("name") and cap.get("prefixed_id"):
            name_to_pid[cap["name"].lower().strip()] = cap["prefixed_id"]

    for item in items:
        cap_name = item.get(name_field, "")
        if isinstance(cap_name, str) and cap_name.strip():
            pid = name_to_pid.get(cap_name.lower().strip())
            if pid:
                item.setdefault("driven_by", []).append(pid)

    return items


def _walk_chain(
    source_type: str,
    source_id: int,
    display_name: str,
    prefixed_id: str,
    m2c_index: dict,
    c2e_index: dict,
    e2i_index: dict,
    resolve_name=None,
) -> dict:
    """Walk the derivation chain from a single motivation element."""
    cap_links = m2c_index.get((source_type, source_id), [])
    capabilities = []
    for cap_link in cap_links:
        cap_key = (cap_link.target_element_type, cap_link.target_element_id)
        cap_name = resolve_name(cap_link.target_element_type, cap_link.target_element_id) if resolve_name else f"{cap_link.target_element_type} #{cap_link.target_element_id}"

        elem_links = c2e_index.get(cap_key, [])
        elements = []
        for elem_link in elem_links:
            elem_key = (elem_link.target_element_type, elem_link.target_element_id)
            elem_name = resolve_name(elem_link.target_element_type, elem_link.target_element_id) if resolve_name else f"{elem_link.target_element_type} #{elem_link.target_element_id}"

            impl_links = e2i_index.get(elem_key, [])
            work_packages = []
            for il in impl_links:
                wp_name = resolve_name(il.target_element_type, il.target_element_id) if resolve_name else f"{il.target_element_type} #{il.target_element_id}"
                work_packages.append({
                    "type": il.target_element_type,
                    "id": il.target_element_id,
                    "name": wp_name,
                })

            elements.append({
                "type": elem_link.target_element_type,
                "id": elem_link.target_element_id,
                "name": elem_name,
                "work_packages": work_packages,
            })

        capabilities.append({
            "type": cap_link.target_element_type,
            "id": cap_link.target_element_id,
            "name": cap_name,
            "elements": elements,
        })

    return {
        "motivation": {
            "type": source_type,
            "id": source_id,
            "name": display_name,
            "prefixed_id": prefixed_id,
        },
        "capabilities": capabilities,
    }
