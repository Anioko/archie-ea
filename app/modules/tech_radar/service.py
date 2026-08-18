"""Tech Radar service (ARCH-124).

A tech radar classifies technology that is already modelled — it is not a
new inventory. The candidate set is every Technology-layer ArchiMateElement
that already exists (created automatically from a real Node, Device,
SystemSoftware or TechnologyService record — see
app/models/technology_layer.py's before_insert listeners). This module only
adds the adopt/trial/assess/hold classification on top.

Nothing here invents a ring. An element with no TechRadarEntry is
"not yet classified" and is rendered as such, never defaulted onto a ring.
"""

from __future__ import annotations

from typing import Dict, List

from app import db
from app.models.archimate_core import ArchiMateElement
from app.models.tech_radar import RADAR_RINGS, TechRadarEntry


def technology_candidates() -> List[ArchiMateElement]:
    """Every Technology-layer ArchiMateElement in the current tenant —
    the real, already-modelled estate a radar classifies."""
    return (
        ArchiMateElement.query.filter(ArchiMateElement.layer == "Technology")
        .order_by(ArchiMateElement.type, ArchiMateElement.name)
        .all()
    )


def radar_state() -> Dict:
    """Build the radar: classified entries grouped by ring, plus the
    unclassified remainder. Returns real data only — an empty candidate
    set or an empty classification set renders as an explicit empty state,
    not a fabricated demo radar."""
    candidates = technology_candidates()
    entries = {
        e.archimate_element_id: e
        for e in TechRadarEntry.query.filter(
            TechRadarEntry.archimate_element_id.in_([c.id for c in candidates])
        ).all()
    } if candidates else {}

    rings: Dict[str, List[Dict]] = {r: [] for r in RADAR_RINGS}
    unclassified: List[ArchiMateElement] = []
    for element in candidates:
        entry = entries.get(element.id)
        if entry is None:
            unclassified.append(element)
        else:
            rings[entry.ring].append({"element": element, "entry": entry})

    return {
        "total_candidates": len(candidates),
        "rings": rings,
        "unclassified": unclassified,
        "classified_count": len(entries),
    }


def classify(archimate_element_id: int, ring: str, rationale: str, user_id: int) -> TechRadarEntry:
    if ring not in RADAR_RINGS:
        raise ValueError(f"ring must be one of {RADAR_RINGS}")

    element = ArchiMateElement.query.get(archimate_element_id)
    if element is None or element.layer != "Technology":
        raise ValueError("not a technology-layer element in this tenant")

    entry = TechRadarEntry.query.filter_by(archimate_element_id=archimate_element_id).first()
    if entry is None:
        entry = TechRadarEntry(archimate_element_id=archimate_element_id)
        db.session.add(entry)
    entry.ring = ring
    entry.rationale = (rationale or "").strip() or None
    entry.set_by_user_id = user_id
    db.session.commit()
    return entry
