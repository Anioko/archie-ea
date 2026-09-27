"""Artefact builders for public share links (BA-B1).

Every function here takes an ``organization_id`` **explicitly** and is the only
code path that reads artefact data for an unauthenticated request. That is
deliberate: on a public request ``g.current_org_id`` is None, so the automatic
tenant filter in ``app/middleware/tenant_isolation.py`` is a documented no-op
and nothing is scoped for us.

Two independent mechanisms scope every query, and both must agree:

1. ``scoped_to(org_id)`` sets ``g.current_org_id`` for the duration of the data
   load only (never across template rendering), so the automatic filter fires
   on exactly the organisation the share row names.
2. Every query *also* carries a hand-written ``organization_id ==`` predicate.

Belt and braces is the right trade here — a bug in either one alone would be a
cross-tenant read on a route with no login in front of it. And because both
predicates name the same organisation they can only ever AND to the same rows,
so the defence costs nothing in correctness.

Only tenant-scoped models are readable through a share link. ``UnifiedCapability``,
``BusinessDomain`` and ``UnifiedWorkPackage`` — which the *logged-in* capability
map and roadmap pages read from — have no ``organization_id`` column at all, so
there is no predicate that could scope them and publishing them would expose
every tenant's capabilities to anyone holding one token. The public roadmap
therefore reads ``CapabilityRoadmap`` and the public map reads
``BusinessCapability``, both of which are ``TenantMixin`` models.
"""

from __future__ import annotations

import contextlib

from flask import g

from app.models.artefact_share import SHAREABLE_ARTEFACTS

#: The 1-5 maturity scale, named. Labels only — never a default level.
MATURITY_SCALE = [
    (1, "Initial"),
    (2, "Developing"),
    (3, "Defined"),
    (4, "Managed"),
    (5, "Optimising"),
]


@contextlib.contextmanager
def scoped_to(organization_id: int):
    """Pin the ORM tenant filter to *organization_id* for this block only.

    Restores whatever was there before on exit, including "nothing", so a public
    request leaves the context exactly as unauthenticated as it arrived.
    """
    had = hasattr(g, "current_org_id")
    previous = getattr(g, "current_org_id", None)
    g.current_org_id = organization_id
    try:
        yield
    finally:
        if had:
            g.current_org_id = previous
        else:
            with contextlib.suppress(AttributeError):
                delattr(g, "current_org_id")


def _capabilities_for(organization_id: int):
    from app.models.business_capabilities import BusinessCapability

    return (
        BusinessCapability.query.filter(
            BusinessCapability.organization_id == organization_id
        )
        .order_by(BusinessCapability.name)
        .all()
    )


def build_maturity_heatmap(organization_id: int) -> dict:
    """Current-vs-target capability maturity, grouped by category.

    A capability counts as assessed only when ``maturity_assessment_date`` is
    set. Unassessed levels stay ``None`` so the page renders an em dash: a
    fabricated Level 1 would tell a chief executive the estate was assessed and
    found immature, which is the single worst thing this page could say.
    """
    rows = _capabilities_for(organization_id)

    grouped: dict[str, list] = {}
    assessed_current: list[int] = []
    assessed_target: list[int] = []

    for cap in rows:
        assessed = cap.maturity_assessment_date is not None
        current = cap.current_maturity_level if assessed else None
        target = cap.target_maturity_level if assessed else None
        gap = (target - current) if (current is not None and target is not None) else None

        if current is not None:
            assessed_current.append(current)
        if target is not None:
            assessed_target.append(target)

        group = (cap.category or cap.business_domain or "Uncategorised").strip() or "Uncategorised"
        grouped.setdefault(group, []).append(
            {
                "name": cap.name,
                "assessed": assessed,
                "current": current,
                "target": target,
                "gap": gap,
                "assessed_on": cap.maturity_assessment_date,
                "strategic_importance": cap.strategic_importance,
            }
        )

    assessed_count = sum(1 for c in rows if c.maturity_assessment_date is not None)
    return {
        "scale": MATURITY_SCALE,
        "groups": [
            {"name": name, "capabilities": caps}
            for name, caps in sorted(grouped.items(), key=lambda kv: kv[0].lower())
        ],
        "total_count": len(rows),
        "assessed_count": assessed_count,
        "unassessed_count": len(rows) - assessed_count,
        "avg_current": (sum(assessed_current) / len(assessed_current)) if assessed_current else None,
        "avg_target": (sum(assessed_target) / len(assessed_target)) if assessed_target else None,
    }


def build_capability_map(organization_id: int) -> dict:
    """The capability estate, grouped by domain and ordered by level."""
    rows = _capabilities_for(organization_id)

    grouped: dict[str, list] = {}
    for cap in rows:
        group = (cap.business_domain or cap.category or "Uncategorised").strip() or "Uncategorised"
        grouped.setdefault(group, []).append(
            {
                "name": cap.name,
                "description": cap.description or "",
                "level": cap.level,
                "category": cap.category or "",
                "strategic_importance": cap.strategic_importance,
            }
        )

    return {
        "groups": [
            {"name": name, "capabilities": sorted(caps, key=lambda c: (c["level"] or 0, c["name"]))}
            for name, caps in sorted(grouped.items(), key=lambda kv: kv[0].lower())
        ],
        "total_count": len(rows),
        "domain_count": len(grouped),
    }


def build_capability_roadmap(organization_id: int) -> dict:
    """Planned capability change over time.

    Reads ``CapabilityRoadmap`` (tenant-scoped) rather than the unified work
    packages the logged-in roadmap renders — see this module's docstring.
    """
    from app.models.business_capabilities import BusinessCapability
    from app.models.capability_models import CapabilityRoadmap

    rows = (
        CapabilityRoadmap.query.filter(
            CapabilityRoadmap.organization_id == organization_id
        )
        .order_by(CapabilityRoadmap.start_date, CapabilityRoadmap.roadmap_name)
        .all()
    )

    names = {}
    if rows:
        cap_ids = {r.business_capability_id for r in rows if r.business_capability_id}
        if cap_ids:
            names = {
                c.id: c.name
                for c in BusinessCapability.query.filter(
                    BusinessCapability.organization_id == organization_id,
                    BusinessCapability.id.in_(cap_ids),
                ).all()
            }

    items = []
    by_year: dict[object, list] = {}
    for r in rows:
        item = {
            "name": r.roadmap_name,
            "capability": names.get(r.business_capability_id),
            "roadmap_type": r.roadmap_type,
            "start_date": r.start_date,
            "target_completion_date": r.target_completion_date,
            "current_phase": r.current_phase,
            "status": r.status,
            "progress": r.phase_completion_percentage,
            "current_maturity_level": r.current_maturity_level,
            "target_maturity_level": r.target_maturity_level,
        }
        items.append(item)
        by_year.setdefault(r.start_date.year if r.start_date else None, []).append(item)

    horizons = [
        {"year": year, "items": entries}
        for year, entries in sorted(by_year.items(), key=lambda kv: (kv[0] is None, kv[0]))
    ]

    return {
        "horizons": horizons,
        "total_count": len(items),
        "capability_count": len(names),
    }


#: artefact_type -> builder. A type outside this map is a 404 on the public
#: route, so the allow-list is what bounds what a token can ever read.
ARTEFACT_BUILDERS = {
    "maturity_heatmap": build_maturity_heatmap,
    "capability_map": build_capability_map,
    "capability_roadmap": build_capability_roadmap,
}

if set(ARTEFACT_BUILDERS) != set(SHAREABLE_ARTEFACTS):  # pragma: no cover - wiring guard
    raise RuntimeError(
        "ARTEFACT_BUILDERS and SHAREABLE_ARTEFACTS disagree; a shareable artefact "
        "with no builder would 500 the public page."
    )


def build_artefact(artefact_type: str, organization_id: int):
    """Build one artefact, or return None when the type is not shareable."""
    builder = ARTEFACT_BUILDERS.get(artefact_type)
    if builder is None:
        return None
    with scoped_to(organization_id):
        return builder(organization_id)
