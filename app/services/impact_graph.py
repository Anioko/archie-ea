"""Impact / dependency graph — the blast-radius lens for one ArchiMate element.

An architect's hardest recurring question is "if I change or retire this, what
breaks?". The data to answer it is already in the ArchiMate relationship graph;
what was missing was a way to *see* it. This service walks that graph outward
from a chosen element — both directions, a bounded number of hops — and returns
the nodes and edges a node-link view renders, so the blast radius is something
you click through rather than infer.

Reads only. Tenant scoping comes from the ORM (ArchiMateRelationship /
ArchiMateElement carry TenantMixin, so queries inside a request are already
constrained to the caller's organisation).
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set

from app import db

# Guardrail: a hub element can reach thousands of others. Past this the picture
# stops being legible and starts being a hairball, so we cap and say so.
_MAX_NODES = 160


def _layer_of(el) -> str:
    return (getattr(el, "layer", None) or "other").lower()


def build_impact_graph(element_id: int, depth: int = 2) -> Optional[Dict[str, Any]]:
    """Breadth-first blast radius around ``element_id`` to ``depth`` hops.

    Returns ``{center, nodes, edges, truncated, counts}`` or None if the element
    does not exist / is not visible to this tenant.

    Each node carries its shortest ``distance`` from the centre and a
    ``direction`` — 'downstream' (this element depends on it), 'upstream'
    (it depends on this element), or 'both'. Edges keep the ArchiMate
    relationship ``type`` and their real source→target orientation.
    """
    from app.models.archimate_core import (  # noqa: PLC0415
        ArchiMateElement, ArchiMateRelationship,
    )

    depth = max(1, min(int(depth or 2), 4))
    center = db.session.get(ArchiMateElement, element_id)
    if center is None:
        return None

    nodes: Dict[int, Dict[str, Any]] = {}
    edges: Dict[tuple, Dict[str, Any]] = {}
    truncated = False

    def _add_node(el, distance: int, direction: str):
        n = nodes.get(el.id)
        if n is None:
            nodes[el.id] = {
                "id": el.id,
                "name": getattr(el, "name", None) or f"Element {el.id}",
                "type": getattr(el, "type", None),
                "layer": _layer_of(el),
                "distance": distance,
                "direction": direction,
                "is_center": el.id == element_id,
            }
        else:
            n["distance"] = min(n["distance"], distance)
            if not n["is_center"] and n["direction"] != direction:
                n["direction"] = "both"

    _add_node(center, 0, "center")

    # BFS frontier of (element_id, distance)
    frontier: deque = deque([(element_id, 0)])
    seen: Set[int] = {element_id}

    while frontier:
        cur_id, dist = frontier.popleft()
        if dist >= depth:
            continue

        # Outgoing (cur depends on target) and incoming (source depends on cur).
        out_rels = ArchiMateRelationship.query.filter_by(source_id=cur_id).all()
        in_rels = ArchiMateRelationship.query.filter_by(target_id=cur_id).all()

        for r in out_rels:
            other = db.session.get(ArchiMateElement, r.target_id)
            if other is None:
                continue
            _add_node(other, dist + 1, "downstream")
            edges.setdefault((r.source_id, r.target_id, r.type),
                             {"source": r.source_id, "target": r.target_id,
                              "type": r.type})
            if other.id not in seen:
                if len(nodes) >= _MAX_NODES:
                    truncated = True
                    continue
                seen.add(other.id)
                frontier.append((other.id, dist + 1))

        for r in in_rels:
            other = db.session.get(ArchiMateElement, r.source_id)
            if other is None:
                continue
            _add_node(other, dist + 1, "upstream")
            edges.setdefault((r.source_id, r.target_id, r.type),
                             {"source": r.source_id, "target": r.target_id,
                              "type": r.type})
            if other.id not in seen:
                if len(nodes) >= _MAX_NODES:
                    truncated = True
                    continue
                seen.add(other.id)
                frontier.append((other.id, dist + 1))

    node_list: List[Dict[str, Any]] = list(nodes.values())
    upstream = sum(1 for n in node_list if n["direction"] in ("upstream", "both"))
    downstream = sum(1 for n in node_list if n["direction"] in ("downstream", "both"))

    return {
        "center": nodes[element_id],
        "nodes": node_list,
        "edges": list(edges.values()),
        "truncated": truncated,
        "depth": depth,
        "counts": {
            "total": len(node_list) - 1,
            "upstream": upstream,
            "downstream": downstream,
        },
    }
