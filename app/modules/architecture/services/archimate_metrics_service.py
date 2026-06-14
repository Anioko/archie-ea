"""
ArchiMate Architecture Health Metrics Service

Calculates and tracks architecture quality metrics including:
- Complexity metrics
- Completeness metrics
- Quality scores
- Technical debt indicators
- Compliance scores
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from app.models import ArchiMateElement, ArchiMateRelationship, ArchitectureModel

logger = logging.getLogger(__name__)


class ArchiMateMetricsService:
    """
    Service for calculating architecture health and quality metrics.

    Metrics include:
    - Structure metrics (size, complexity, connectivity)
    - Quality metrics (completeness, consistency, documentation)
    - Technical debt indicators
    - Layer distribution
    - Relationship quality
    """

    def __init__(self):
        """Initialize metrics service."""
        pass

    def calculate_all_metrics(self, model: ArchitectureModel) -> Dict:
        """
        Calculate comprehensive metrics for an architecture model.

        Args:
            model: ArchitectureModel to analyze

        Returns:
            Dictionary with all calculated metrics
        """
        elements = list(model.archimate_elements.all())
        relationships = list(model.archimate_relationships.all())

        if not elements:
            return {"error": "Model has no elements", "overall_score": 0}

        return {
            "model_id": model.id,
            "model_name": model.name,
            "structure_metrics": self.calculate_structure_metrics(elements, relationships),
            "quality_metrics": self.calculate_quality_metrics(elements, relationships),
            "layer_metrics": self.calculate_layer_metrics(elements),
            "relationship_metrics": self.calculate_relationship_metrics(relationships, elements),
            "complexity_metrics": self.calculate_complexity_metrics(elements, relationships),
            "completeness_score": self.calculate_completeness_score(elements, relationships),
            "technical_debt_score": self.calculate_technical_debt(elements, relationships),
            "overall_health_score": 0,  # Will be calculated from other scores
        }

    def calculate_structure_metrics(
        self, elements: List[ArchiMateElement], relationships: List[ArchiMateRelationship]
    ) -> Dict:
        """
        Calculate structural metrics about the model.

        Returns:
            Dictionary with structural metrics
        """
        total_elements = len(elements)
        total_relationships = len(relationships)

        # Count orphaned elements (no relationships)
        element_ids = {e.id for e in elements}
        connected_elements = set()

        for rel in relationships:
            if rel.source_element_id in element_ids:
                connected_elements.add(rel.source_element_id)
            if rel.target_element_id in element_ids:
                connected_elements.add(rel.target_element_id)

        orphaned_count = total_elements - len(connected_elements)

        # Calculate average connections per element
        avg_connections = (total_relationships * 2) / total_elements if total_elements > 0 else 0

        # Find most connected elements
        element_connections = defaultdict(int)
        for rel in relationships:
            if rel.source_element_id:
                element_connections[rel.source_element_id] += 1
            if rel.target_element_id:
                element_connections[rel.target_element_id] += 1

        max_connections = max(element_connections.values()) if element_connections else 0

        return {
            "total_elements": total_elements,
            "total_relationships": total_relationships,
            "orphaned_elements": orphaned_count,
            "orphaned_percentage": (orphaned_count / total_elements * 100)
            if total_elements > 0
            else 0,
            "connected_elements": len(connected_elements),
            "connectivity_ratio": len(connected_elements) / total_elements
            if total_elements > 0
            else 0,
            "average_connections_per_element": round(avg_connections, 2),
            "max_connections": max_connections,
            "relationship_to_element_ratio": round(total_relationships / total_elements, 2)
            if total_elements > 0
            else 0,
        }

    def calculate_quality_metrics(
        self, elements: List[ArchiMateElement], relationships: List[ArchiMateRelationship]
    ) -> Dict:
        """
        Calculate quality metrics for documentation and completeness.

        Returns:
            Dictionary with quality metrics
        """
        total_elements = len(elements)

        # Documentation quality
        elements_with_description = sum(
            1 for e in elements if e.description and len(e.description.strip()) >= 20
        )
        description_quality_score = (
            (elements_with_description / total_elements * 100) if total_elements > 0 else 0
        )

        # Name quality (not generic names like "System", "Process")
        generic_names = {
            "system",
            "process",
            "service",
            "component",
            "application",
            "database",
            "server",
        }
        elements_with_specific_names = sum(
            1
            for e in elements
            if e.name and e.name.lower().strip() not in generic_names and len(e.name.split()) >= 2
        )
        name_quality_score = (
            (elements_with_specific_names / total_elements * 100) if total_elements > 0 else 0
        )

        # Relationship documentation
        rels_with_description = sum(
            1 for r in relationships if r.description and len(r.description.strip()) >= 10
        )
        relationship_doc_score = (
            (rels_with_description / len(relationships) * 100) if relationships else 0
        )

        # Properties usage
        elements_with_properties = sum(
            1 for e in elements if e.properties and len(e.properties) > 0
        )
        properties_usage_score = (
            (elements_with_properties / total_elements * 100) if total_elements > 0 else 0
        )

        # Overall quality score
        overall_quality = (
            description_quality_score * 0.4
            + name_quality_score * 0.3
            + relationship_doc_score * 0.2
            + properties_usage_score * 0.1
        )

        return {
            "description_quality_score": round(description_quality_score, 1),
            "name_quality_score": round(name_quality_score, 1),
            "relationship_documentation_score": round(relationship_doc_score, 1),
            "properties_usage_score": round(properties_usage_score, 1),
            "overall_quality_score": round(overall_quality, 1),
            "elements_with_good_descriptions": elements_with_description,
            "elements_with_specific_names": elements_with_specific_names,
            "relationships_documented": rels_with_description,
        }

    def calculate_layer_metrics(self, elements: List[ArchiMateElement]) -> Dict:
        """
        Calculate metrics about layer distribution and coverage.

        Returns:
            Dictionary with layer metrics
        """
        total_elements = len(elements)

        # Count elements by layer
        layer_counts = defaultdict(int)
        for elem in elements:
            layer_counts[elem.layer] += 1

        layer_distribution = {
            layer: {"count": count, "percentage": round(count / total_elements * 100, 1)}
            for layer, count in layer_counts.items()
        }

        # Count element types
        type_counts = defaultdict(int)
        for elem in elements:
            type_counts[elem.type] += 1

        # Layer coverage (how many layers are used)
        standard_layers = {
            "motivation",
            "strategy",
            "business",
            "application",
            "technology",
            "physical",
            "implementation",
        }
        layers_used = set(layer_counts.keys())
        layer_coverage_score = len(layers_used) / len(standard_layers) * 100

        # Balance score (how evenly distributed across layers)
        if layer_counts:
            avg_per_layer = total_elements / len(layer_counts)
            variance = sum((count - avg_per_layer) ** 2 for count in layer_counts.values()) / len(
                layer_counts
            )
            balance_score = (
                max(0, 100 - (variance / avg_per_layer * 10)) if avg_per_layer > 0 else 0
            )
        else:
            balance_score = 0

        return {
            "layer_distribution": layer_distribution,
            "layers_used": list(layers_used),
            "layer_count": len(layers_used),
            "layer_coverage_score": round(layer_coverage_score, 1),
            "layer_balance_score": round(balance_score, 1),
            "element_type_diversity": len(type_counts),
            "most_used_types": sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:5],
        }

    def calculate_relationship_metrics(
        self, relationships: List[ArchiMateRelationship], elements: List[ArchiMateElement]
    ) -> Dict:
        """
        Calculate metrics about relationships and their quality.

        Returns:
            Dictionary with relationship metrics
        """
        if not relationships:
            return {"total_relationships": 0, "relationship_quality_score": 0}

        total_relationships = len(relationships)

        # Count by type
        type_counts = defaultdict(int)
        for rel in relationships:
            type_counts[rel.type] += 1

        # Cross-layer relationships
        cross_layer_rels = sum(
            1
            for rel in relationships
            if rel.source_element
            and rel.target_element
            and rel.source_element.layer != rel.target_element.layer
        )
        cross_layer_ratio = (
            (cross_layer_rels / total_relationships * 100) if total_relationships > 0 else 0
        )

        # Bidirectional relationships (both A->B and B->A exist)
        rel_pairs = set()
        bidirectional_count = 0
        for rel in relationships:
            if rel.source_element_id and rel.target_element_id:
                pair = (
                    min(rel.source_element_id, rel.target_element_id),
                    max(rel.source_element_id, rel.target_element_id),
                )
                if pair in rel_pairs:
                    bidirectional_count += 1
                rel_pairs.add(pair)

        # Relationship type diversity
        type_diversity_score = (
            len(type_counts) / 11 * 100
        )  # 11 standard relationship types in ArchiMate

        return {
            "total_relationships": total_relationships,
            "relationship_type_distribution": dict(type_counts),
            "relationship_type_diversity": len(type_counts),
            "type_diversity_score": round(type_diversity_score, 1),
            "cross_layer_relationships": cross_layer_rels,
            "cross_layer_percentage": round(cross_layer_ratio, 1),
            "bidirectional_relationships": bidirectional_count,
            "most_used_relationship_types": sorted(
                type_counts.items(), key=lambda x: x[1], reverse=True
            )[:3],
        }

    def calculate_complexity_metrics(
        self, elements: List[ArchiMateElement], relationships: List[ArchiMateRelationship]
    ) -> Dict:
        """
        Calculate complexity metrics for the architecture.

        Returns:
            Dictionary with complexity metrics
        """
        total_elements = len(elements)
        total_relationships = len(relationships)

        # Cyclomatic complexity (simplified)
        # V = E - N + 2P (where E=edges, N=nodes, P=connected components)
        # For our purposes, we'll use a simplified version
        cyclomatic = total_relationships - total_elements + 2 if total_elements > 0 else 0

        # Calculate depth of element hierarchies
        parent_counts = defaultdict(int)
        max_depth = 0

        def calculate_depth(element_id, elements_dict, visited=None):
            if visited is None:
                visited = set()
            if element_id in visited:
                return 0
            visited.add(element_id)

            elem = elements_dict.get(element_id)
            if not elem or not elem.parent_id:
                return 1

            return 1 + calculate_depth(elem.parent_id, elements_dict, visited)

        elements_dict = {e.id: e for e in elements}
        for elem in elements:
            if elem.parent_id:
                parent_counts[elem.parent_id] += 1
            depth = calculate_depth(elem.id, elements_dict)
            max_depth = max(max_depth, depth)

        # Complexity score (0 - 100, higher = more complex)
        # Based on: size, connectivity, depth, cyclomatic complexity
        size_complexity = min(total_elements / 100 * 100, 100)  # 100+ elements = max
        connectivity_complexity = (
            min(total_relationships / total_elements * 10, 100) if total_elements > 0 else 0
        )
        depth_complexity = min(max_depth * 20, 100)

        overall_complexity = (
            size_complexity * 0.3 + connectivity_complexity * 0.4 + depth_complexity * 0.3
        )

        return {
            "cyclomatic_complexity": cyclomatic,
            "max_hierarchy_depth": max_depth,
            "elements_with_children": len(parent_counts),
            "max_children": max(parent_counts.values()) if parent_counts else 0,
            "size_complexity_score": round(size_complexity, 1),
            "connectivity_complexity_score": round(connectivity_complexity, 1),
            "depth_complexity_score": round(depth_complexity, 1),
            "overall_complexity_score": round(overall_complexity, 1),
            "complexity_rating": self._get_complexity_rating(overall_complexity),
        }

    def _get_complexity_rating(self, score: float) -> str:
        """Get human-readable complexity rating."""
        if score < 30:
            return "Low"
        elif score < 60:
            return "Medium"
        elif score < 80:
            return "High"
        else:
            return "Very High"

    def calculate_completeness_score(
        self, elements: List[ArchiMateElement], relationships: List[ArchiMateRelationship]
    ) -> Dict:
        """
        Calculate how complete the architecture model is.

        Returns:
            Dictionary with completeness metrics
        """
        scores = []

        # Layer completeness (should have multiple layers)
        layers = set(e.layer for e in elements)
        layer_score = min(len(layers) / 4 * 100, 100)  # 4+ layers = complete
        scores.append(layer_score)

        # Connectivity completeness (elements should have relationships)
        if elements:
            connected_ratio = len(
                set(
                    [r.source_element_id for r in relationships if r.source_element_id]
                    + [r.target_element_id for r in relationships if r.target_element_id]
                )
            ) / len(elements)
            connectivity_score = connected_ratio * 100
            scores.append(connectivity_score)
        else:
            connectivity_score = 0

        # Documentation completeness
        documented_elements = sum(1 for e in elements if e.description and len(e.description) >= 20)
        doc_score = (documented_elements / len(elements) * 100) if elements else 0
        scores.append(doc_score)

        # Motivation layer presence (goals, requirements, stakeholders)
        motivation_elements = [e for e in elements if e.layer == "motivation"]
        has_stakeholders = any(e.type == "Stakeholder" for e in motivation_elements)
        has_goals = any(e.type == "Goal" for e in motivation_elements)
        has_requirements = any(e.type == "Requirement" for e in motivation_elements)
        motivation_score = sum([has_stakeholders, has_goals, has_requirements]) / 3 * 100
        scores.append(motivation_score)

        # Cross-layer linkage (motivation should link to realization)
        cross_layer_rels = [
            r
            for r in relationships
            if r.source_element
            and r.target_element
            and r.source_element.layer != r.target_element.layer
        ]
        cross_layer_score = min(len(cross_layer_rels) / 5 * 100, 100)  # 5+ cross-layer = complete
        scores.append(cross_layer_score)

        overall_completeness = sum(scores) / len(scores) if scores else 0

        return {
            "layer_completeness": round(layer_score, 1),
            "connectivity_completeness": round(connectivity_score, 1),
            "documentation_completeness": round(doc_score, 1),
            "motivation_completeness": round(motivation_score, 1),
            "cross_layer_linkage_completeness": round(cross_layer_score, 1),
            "overall_completeness_score": round(overall_completeness, 1),
            "completeness_rating": self._get_completeness_rating(overall_completeness),
        }

    def _get_completeness_rating(self, score: float) -> str:
        """Get human-readable completeness rating."""
        if score < 40:
            return "Incomplete"
        elif score < 70:
            return "Partial"
        elif score < 90:
            return "Good"
        else:
            return "Complete"

    def calculate_technical_debt(
        self, elements: List[ArchiMateElement], relationships: List[ArchiMateRelationship]
    ) -> Dict:
        """
        Calculate technical debt indicators.

        Returns:
            Dictionary with technical debt metrics
        """
        debt_indicators = []

        # Missing descriptions
        missing_descriptions = sum(
            1 for e in elements if not e.description or len(e.description.strip()) < 20
        )
        if missing_descriptions > len(elements) * 0.3:
            debt_indicators.append(
                {
                    "type": "documentation_debt",
                    "severity": "medium",
                    "description": f"{missing_descriptions} elements lack adequate descriptions",
                    "impact_score": 30,
                }
            )

        # Orphaned elements
        connected_ids = set()
        for rel in relationships:
            if rel.source_element_id:
                connected_ids.add(rel.source_element_id)
            if rel.target_element_id:
                connected_ids.add(rel.target_element_id)

        orphaned = len(elements) - len(connected_ids)
        if orphaned > 0:
            debt_indicators.append(
                {
                    "type": "architectural_debt",
                    "severity": "high" if orphaned > 5 else "medium",
                    "description": f"{orphaned} orphaned elements with no relationships",
                    "impact_score": min(orphaned * 10, 50),
                }
            )

        # Generic naming
        generic_names = {"system", "process", "service", "component", "application"}
        generic_named = sum(
            1 for e in elements if e.name and e.name.lower().strip() in generic_names
        )
        if generic_named > 0:
            debt_indicators.append(
                {
                    "type": "naming_debt",
                    "severity": "low",
                    "description": f"{generic_named} elements have generic names",
                    "impact_score": generic_named * 5,
                }
            )

        # Missing motivation layer
        has_motivation = any(e.layer == "motivation" for e in elements)
        if not has_motivation:
            debt_indicators.append(
                {
                    "type": "strategic_debt",
                    "severity": "high",
                    "description": "No motivation layer elements (goals, requirements, stakeholders)",
                    "impact_score": 40,
                }
            )

        # Calculate total debt score
        total_impact = sum(ind["impact_score"] for ind in debt_indicators)
        debt_score = min(total_impact, 100)

        return {
            "debt_indicators": debt_indicators,
            "total_debt_score": round(debt_score, 1),
            "debt_rating": self._get_debt_rating(debt_score),
            "indicator_count": len(debt_indicators),
            "high_severity_count": sum(1 for ind in debt_indicators if ind["severity"] == "high"),
            "medium_severity_count": sum(
                1 for ind in debt_indicators if ind["severity"] == "medium"
            ),
            "low_severity_count": sum(1 for ind in debt_indicators if ind["severity"] == "low"),
        }

    def _get_debt_rating(self, score: float) -> str:
        """Get human-readable debt rating."""
        if score < 20:
            return "Low"
        elif score < 50:
            return "Medium"
        elif score < 80:
            return "High"
        else:
            return "Critical"

    def calculate_overall_health_score(self, metrics: Dict) -> float:
        """
        Calculate overall architecture health score from individual metrics.

        Args:
            metrics: Dictionary with all calculated metrics

        Returns:
            Overall health score (0 - 100)
        """
        # Weight different aspects
        quality_weight = 0.25
        completeness_weight = 0.25
        complexity_weight = 0.20  # Lower complexity = better
        debt_weight = 0.30  # Lower debt = better

        quality_score = metrics.get("quality_metrics", {}).get("overall_quality_score", 50)
        completeness_score = metrics.get("completeness_score", {}).get(
            "overall_completeness_score", 50
        )
        complexity_score = 100 - metrics.get("complexity_metrics", {}).get(
            "overall_complexity_score", 50
        )  # Invert
        debt_score = 100 - metrics.get("technical_debt_score", {}).get(
            "total_debt_score", 50
        )  # Invert

        overall = (
            quality_score * quality_weight
            + completeness_score * completeness_weight
            + complexity_score * complexity_weight
            + debt_score * debt_weight
        )

        return round(overall, 1)
