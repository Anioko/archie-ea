"""Traceability Graph Service — builds cross-layer adjacency map.

Returns a dict with:
    edges: list of {source_id, target_id, type} for all traceability relationships
    element_index: dict mapping element_id → {layer, type, name}

Used by the traceability chain page to highlight connected elements
across all 8 layers when a user clicks any chip.
"""

import logging
from app import db
from app.utils.tenant_sql import org_scope
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ArchiMate element types grouped by traceability layer
LAYER_TYPE_MAP = {
    "stakeholders": ["Stakeholder"],
    "drivers": ["Driver"],
    "goals": ["Goal", "Outcome"],
    "requirements": ["Requirement", "Constraint"],
    "capabilities": ["Capability", "CourseOfAction"],
    "processes": ["BusinessProcess", "BusinessService", "BusinessObject"],
    "applications": ["ApplicationComponent", "ApplicationService", "ApplicationInterface", "DataObject"],
    "technology": ["Node", "Device", "SystemSoftware", "TechnologyService", "Artifact", "CommunicationNetwork"],
}

# Reverse: type → layer key
TYPE_TO_LAYER = {}
for layer_key, types in LAYER_TYPE_MAP.items():
    for t in types:
        TYPE_TO_LAYER[t] = layer_key

TRACEABILITY_REL_TYPES = (
    # Full ArchiMate names
    "RealizationRelationship",
    "ServingRelationship",
    "AssignmentRelationship",
    "CompositionRelationship",
    "AggregationRelationship",
    "AssociationRelationship",
    "FlowRelationship",
    "TriggeringRelationship",
    "AccessRelationship",
    "InfluenceRelationship",
    # Short forms (as stored in DB)
    "Realization", "Realizes",
    "Serving", "Serves",
    "Assignment",
    "Composition", "composition",
    "Aggregation",
    "Association",
    "Flow",
    "Triggering",
    "Access",
    "Influence",
)


def build_traceability_graph(organization_id=None):
    """Build the full cross-layer adjacency graph from ArchiMate relationships.

    Args:
        organization_id: scope the graph to this organisation. Defaults to the
            request's tenant. There is no id-keyed narrowing anywhere in this
            function — both statements are whole-table reads — so a caller
            outside a request context (CLI, scheduler) MUST pass this or the
            graph spans every tenant.

    Returns:
        {
            "edges": [[source_id, target_id], ...],
            "elements": {id: {"name": str, "layer": str, "type": str}, ...}
        }
    """
    try:
        rel_types = ", ".join(f"'{t}'" for t in TRACEABILITY_REL_TYPES)

        # Both tables carry organization_id and both queries are unbounded, so
        # without these predicates the traceability page drew one graph over
        # every organisation's ArchiMate model.
        _org_clause, _org_params = org_scope(prefix="r.", org_id=organization_id)
        edge_sql = text(f"""
            SELECT r.source_id, r.target_id
            FROM archimate_relationships r
            WHERE r.type IN ({rel_types})
              AND r.source_id IS NOT NULL
              AND r.target_id IS NOT NULL
              {_org_clause}
        """)
        rows = db.session.execute(edge_sql, _org_params).fetchall()
        edges = [[r[0], r[1]] for r in rows]

        # Collect all element IDs referenced in edges
        ids = set()
        for s, t in edges:
            ids.add(s)
            ids.add(t)

        elements = {}
        if ids:
            _org_el_clause, _org_el_params = org_scope(org_id=organization_id)
            el_sql = text(f"""
                SELECT id, name, type, layer
                FROM archimate_elements
                WHERE id = ANY(:ids)
                {_org_el_clause}
            """)
            try:
                el_rows = db.session.execute(
                    el_sql, {"ids": list(ids), **_org_el_params}
                ).fetchall()
            except Exception:
                # Fallback for databases that don't support ANY()
                id_list = ", ".join(str(i) for i in ids)
                el_sql = text(
                    f"SELECT id, name, type, layer FROM archimate_elements "
                    f"WHERE id IN ({id_list}){_org_el_clause}"
                )
                el_rows = db.session.execute(el_sql, _org_el_params).fetchall()

            for r in el_rows:
                el_type = r[2] or ""
                elements[r[0]] = {
                    "name": r[1],
                    "type": el_type,
                    "layer": TYPE_TO_LAYER.get(el_type, ""),
                }

        logger.info("Traceability graph: %d edges, %d elements", len(edges), len(elements))
        return {"edges": edges, "elements": elements}

    except Exception as exc:
        # Do not fabricate an empty graph on failure -- that reads as "no
        # relationships exist". Roll back for session hygiene, then re-raise so
        # the page surfaces the error instead of an invented empty graph.
        logger.warning("build_traceability_graph failed: %s", exc)
        try:
            db.session.rollback()
        except Exception:
            pass
        raise
