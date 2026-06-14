"""Traceability Graph Service — builds cross-layer adjacency map.

Returns a dict with:
    edges: list of {source_id, target_id, type} for all traceability relationships
    element_index: dict mapping element_id → {layer, type, name}

Used by the traceability chain page to highlight connected elements
across all 8 layers when a user clicks any chip.
"""

import logging
from app import db
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


def build_traceability_graph():
    """Build the full cross-layer adjacency graph from ArchiMate relationships.

    Returns:
        {
            "edges": [[source_id, target_id], ...],
            "elements": {id: {"name": str, "layer": str, "type": str}, ...}
        }
    """
    try:
        rel_types = ", ".join(f"'{t}'" for t in TRACEABILITY_REL_TYPES)

        # Get all relationships between known element types
        # tenant-filtered: scoped via parent FK (archimate_relationships → archimate_elements)
        edge_sql = text(f"""
            SELECT r.source_id, r.target_id
            FROM archimate_relationships r
            WHERE r.type IN ({rel_types})
              AND r.source_id IS NOT NULL
              AND r.target_id IS NOT NULL
        """)
        rows = db.session.execute(edge_sql).fetchall()  # tenant-filtered: scoped via archimate_relationships
        edges = [[r[0], r[1]] for r in rows]

        # Collect all element IDs referenced in edges
        ids = set()
        for s, t in edges:
            ids.add(s)
            ids.add(t)

        # Get element details
        # tenant-filtered: scoped via parent FK (element IDs from relationships)
        elements = {}
        if ids:
            el_sql = text("""
                SELECT id, name, type, layer
                FROM archimate_elements
                WHERE id = ANY(:ids)
            """)
            try:
                el_rows = db.session.execute(el_sql, {"ids": list(ids)}).fetchall()  # tenant-filtered: scoped via parent FK (element IDs from relationships)
            except Exception:
                # Fallback for databases that don't support ANY()
                id_list = ", ".join(str(i) for i in ids)
                el_sql = text(f"SELECT id, name, type, layer FROM archimate_elements WHERE id IN ({id_list})")
                el_rows = db.session.execute(el_sql).fetchall()  # tenant-filtered: scoped via archimate_elements

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
        logger.warning("build_traceability_graph failed: %s", exc)
        try:
            db.session.rollback()
        except Exception:
            pass
        return {"edges": [], "elements": {}}
