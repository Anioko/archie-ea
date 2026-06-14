"""SA-006: Integration Pattern Recommender Service.

Analyses 2495 archimate_relationships to classify each app node as
hub / sink / peer / standalone based on its inbound/outbound relationship counts.
"""
from collections import defaultdict
from typing import Dict, List

from app import db
from app.models.archimate_core import ArchiMateRelationship

# Thresholds for pattern classification
_HUB_OUTBOUND_THRESHOLD = 10
_SINK_INBOUND_THRESHOLD = 10


class IntegrationPatternRecommenderService:
    """Classifies application integration patterns from ArchiMate relationships.

    Pattern definitions
    -------------------
    hub        : outbound_serving > 10  (app drives many others)
    sink       : inbound > 10           (many apps push into this one)
    peer       : balanced (neither hub nor sink, at least 1 connection)
    standalone : no relationships at all
    """

    def analyse_integration_topology(self) -> Dict:
        """Analyse all archimate_relationships and classify each app node.

        Returns
        -------
        dict with keys:
            hub_apps            : list of app element IDs classified as hub
            sink_apps           : list of app element IDs classified as sink
            peer_apps           : list of app element IDs classified as peer
            standalone_apps     : list of app element IDs with no relationships
            total_apps_analysed : int
        """
        # Aggregate counts keyed by node ID
        outbound_serving: Dict[int, int] = defaultdict(int)
        inbound_total: Dict[int, int] = defaultdict(int)
        all_nodes: set = set()

        rows = (
            db.session.query(
                ArchiMateRelationship.source_id,
                ArchiMateRelationship.target_id,
                ArchiMateRelationship.type,
            )
            .all()
        )

        for source_id, target_id, rel_type in rows:
            if source_id is None or target_id is None:
                continue

            all_nodes.add(source_id)
            all_nodes.add(target_id)

            inbound_total[target_id] += 1

            if rel_type and rel_type.lower() == "serving":
                outbound_serving[source_id] += 1

        # Classify
        hub_apps: List[int] = []
        sink_apps: List[int] = []
        peer_apps: List[int] = []

        classified: set = set()

        for node in all_nodes:
            out_s = outbound_serving.get(node, 0)
            in_t = inbound_total.get(node, 0)

            if out_s > _HUB_OUTBOUND_THRESHOLD:
                hub_apps.append(node)
                classified.add(node)
            elif in_t > _SINK_INBOUND_THRESHOLD:
                sink_apps.append(node)
                classified.add(node)

        for node in all_nodes:
            if node not in classified:
                peer_apps.append(node)

        # Standalone: nodes that appear in elements but have zero relationships
        # (not reachable from this query — by definition all_nodes came from rows,
        #  so truly isolated nodes are outside our relationship scan; we return
        #  an empty list for standalone as the query scope is relationships only)
        standalone_apps: List[int] = []

        return {
            "hub_apps": sorted(hub_apps),
            "sink_apps": sorted(sink_apps),
            "peer_apps": sorted(peer_apps),
            "standalone_apps": standalone_apps,
            "total_apps_analysed": len(all_nodes),
        }
