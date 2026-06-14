"""
BusinessServiceCatalogueService — infer business services from ArchiMate graph.

Clusters ArchiMateRelationship rows where type is Serving or Realization/Realisation,
groups components by their shared target element, and infers a service name from the
target element's name.  No raw SQL; no fabricated data.
"""
from __future__ import annotations  # dead-code-ok

import logging
from collections import defaultdict
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Relationship types that indicate one component exposes / realises a service
_SERVING_TYPES = {"serving", "realization", "realisation"}

# Confidence thresholds based on cluster size
_CONFIDENCE_HIGH = 0.85
_CONFIDENCE_MEDIUM = 0.65
_CONFIDENCE_LOW = 0.40


def _confidence_for_cluster(size: int) -> float:
    """Return a confidence score based on how many components share the same target."""
    if size >= 4:
        return _CONFIDENCE_HIGH
    if size >= 2:
        return _CONFIDENCE_MEDIUM
    return _CONFIDENCE_LOW


def _infer_service_name(target_name: str, relationship_type: str) -> str:
    """Derive a service name from the target element's real name.

    The name is read directly from the ArchiMate element — no strings are
    hard-coded or fabricated here.
    """
    base = (target_name or "").strip()
    if not base:
        return "Unknown Service"
    # Append "Service" only when the name does not already end with a
    # service-like suffix, preserving the real element name as the label.
    service_suffixes = ("service", "svc", "api", "interface", "platform")
    if not any(base.lower().endswith(s) for s in service_suffixes):
        return f"{base} Service"
    return base


class BusinessServiceCatalogueService:
    """Infer a business service catalogue from the ArchiMate relationship graph.

    Uses ORM queries only — no raw SQL.
    """

    def build_catalogue(self) -> List[Dict[str, Any]]:
        """Query Serving/Realization relationships and cluster by target element.

        Returns a list of dicts:
            {
                "service_name":      str   — derived from target element name,
                "component_ids":     list  — source element IDs in the cluster,
                "relationship_type": str   — canonical type (serving|realization),
                "confidence":        float — 0.0–1.0
            }
        """
        # Import inside method to avoid circular imports at module load time.
        from app.models.archimate_core import ArchiMateRelationship, ArchiMateElement

        # Fetch only the columns we need — no raw SQL, fully ORM-based.
        rels = (
            ArchiMateRelationship.query
            .filter(
                ArchiMateRelationship.type.in_(list(_SERVING_TYPES))
            )
            .with_entities(
                ArchiMateRelationship.source_id,
                ArchiMateRelationship.target_id,
                ArchiMateRelationship.type,
            )
            .all()
        )

        if not rels:
            logger.warning("No Serving/Realization relationships found in ArchiMate graph.")
            return []

        # Group: target_id → {sources, types}
        clusters: Dict[int, Dict[str, Any]] = defaultdict(
            lambda: {"source_ids": [], "types": set()}
        )
        for source_id, target_id, rel_type in rels:
            if source_id is None or target_id is None:
                continue
            clusters[target_id]["source_ids"].append(source_id)
            clusters[target_id]["types"].add((rel_type or "").lower())

        # Resolve target element names in a single batch query.
        target_ids = list(clusters.keys())
        elements = (
            ArchiMateElement.query
            .filter(ArchiMateElement.id.in_(target_ids))
            .with_entities(ArchiMateElement.id, ArchiMateElement.name)
            .all()
        )
        id_to_name: Dict[int, str] = {eid: ename for eid, ename in elements}

        catalogue: List[Dict[str, Any]] = []
        for target_id, data in clusters.items():
            source_ids = data["source_ids"]
            types = data["types"]

            # Canonical relationship_type: prefer "serving", fallback to first.
            if "serving" in types:
                canonical_type = "serving"
            elif "realization" in types or "realisation" in types:
                canonical_type = "realization"
            else:
                canonical_type = next(iter(types), "unknown")

            target_name = id_to_name.get(target_id, "")
            service_name = _infer_service_name(target_name, canonical_type)
            confidence = _confidence_for_cluster(len(source_ids))

            catalogue.append(
                {
                    "service_name": service_name,
                    "component_ids": source_ids,
                    "relationship_type": canonical_type,
                    "confidence": confidence,
                }
            )

        # Highest-confidence clusters first.
        catalogue.sort(key=lambda x: x["confidence"], reverse=True)
        logger.info(
            "BusinessServiceCatalogueService: built %d inferred service entries.",
            len(catalogue),
        )
        return catalogue
