"""ArchiMate Impact Analysis Service — change propagation (ARCH-016)."""

from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
from app import db

# Relationship types that propagate impact
IMPACT_RELATIONSHIPS = [
    'CompositionRelationship', 'AggregationRelationship', 'RealizationRelationship',
    'ServingRelationship', 'AssignmentRelationship', 'TriggeringRelationship',
    'FlowRelationship', 'InfluenceRelationship', 'AssociationRelationship',
    # short-form variants stored in DB
    'Composition', 'Aggregation', 'Realization',
    'Serving', 'Assignment', 'Triggering',
    'Flow', 'Influence', 'Association',
]


class ArchiMateImpactService:

    def get_impact_summary(self, element_id: int, max_hops: int = 2) -> dict:
        """Return a compact impact summary for lightweight detail-page previews."""
        analysis = self.analyze_impact(element_id, max_hops=max_hops)
        if analysis.get('error'):
            return analysis

        return {
            'total_affected': analysis.get('total_impacted', 0),
            'by_layer': analysis.get('by_layer', {}),
        }

    def analyze_impact(self, element_id: int, max_hops: int = 3) -> dict:
        """
        Given an element, find all elements impacted if this element changes/is removed.
        Returns: direct_impacts (hop=1), indirect_impacts (hop=2-3), summary by layer.
        """
        root = ArchiMateElement.query.get(element_id)
        if not root:
            return {'error': 'Element not found'}

        visited = {element_id}
        all_impacts = []

        self._propagate(element_id, all_impacts, visited, max_hops, 1)

        direct = [i for i in all_impacts if i['hop'] == 1]
        indirect = [i for i in all_impacts if i['hop'] > 1]

        by_layer: dict = {}
        for imp in all_impacts:
            layer = imp['layer'] or 'Unknown'
            by_layer.setdefault(layer, []).append(imp)

        return {
            'root': {
                'id': root.id,
                'name': root.name,
                'layer': root.layer,
                'type': root.type,
            },
            'total_impacted': len(all_impacts),
            'direct_impacts': direct,
            'indirect_impacts': indirect,
            'by_layer': {layer: len(els) for layer, els in by_layer.items()},
            'impact_details': by_layer,
        }

    def _propagate(self, element_id, impacts, visited, max_hops, hop):
        if hop > max_hops:
            return

        rels = ArchiMateRelationship.query.filter(
            db.or_(
                ArchiMateRelationship.source_id == element_id,
                ArchiMateRelationship.target_id == element_id,
            ),
            ArchiMateRelationship.type.in_(IMPACT_RELATIONSHIPS),
        ).all()

        for rel in rels:
            other_id = rel.target_id if rel.source_id == element_id else rel.source_id
            if other_id and other_id not in visited:
                other = ArchiMateElement.query.get(other_id)
                if other:
                    visited.add(other_id)
                    impacts.append({
                        'id': other.id,
                        'name': other.name,
                        'layer': other.layer or 'Unknown',
                        'type': other.type or '',
                        'hop': hop,
                        'via_relationship': rel.type,
                        'direction': 'outgoing' if rel.source_id == element_id else 'incoming',
                    })
                    self._propagate(other_id, impacts, visited, max_hops, hop + 1)

    def get_capability_gaps(self, element_id: int) -> list:
        """Find Strategy/Capability elements at risk if this element is removed."""
        impact = self.analyze_impact(element_id, max_hops=3)
        return [e for e in impact.get('impact_details', {}).get('Strategy', [])]
