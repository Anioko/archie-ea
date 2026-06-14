"""
Dependency Visualization Service

Visualizes and analyzes dependencies across the enterprise architecture:
- Dependency graph generation and visualization
- Critical path analysis
- Change impact visualization
- Integration mapping
- Dependency health assessment
"""

from datetime import date, datetime  # dead-code-ok
from typing import Dict, List, Optional, Tuple  # dead-code-ok

from flask import g
from sqlalchemy import and_, func, or_, text  # dead-code-ok

from app import db
from app.services.decorators import transactional


class DependencyVisualizationService:
    """
    Service for dependency visualization and analysis across enterprise architecture.

    Provides comprehensive dependency analysis:
    - Dependency graph generation and visualization
    - Critical path and bottleneck identification
    - Change impact visualization
    - Integration mapping and analysis
    - Dependency health assessment
    """

    def __init__(self):
        pass

    @transactional
    def analyze_dependency_portfolio(self, include_visualization: bool = True) -> Dict:
        """
        Comprehensive dependency analysis across the entire portfolio.

        Args:
            include_visualization: Include visualization data for graphs

        Returns:
            Dict with dependency analysis results and visualizations
        """
        # Get all architecture elements
        elements = self._get_all_elements()

        # Build dependency graph
        dependency_graph = self._build_dependency_graph(elements)

        # Analyze dependency metrics
        dependency_metrics = self._analyze_dependency_metrics(dependency_graph)

        # Identify critical paths
        critical_paths = self._identify_critical_paths(dependency_graph)

        # Analyze dependency health
        health_analysis = self._analyze_dependency_health(dependency_graph)

        # Generate visualization data
        visualization_data = {}
        if include_visualization:
            visualization_data = self._generate_visualization_data(dependency_graph, critical_paths)

        # Generate dependency recommendations
        recommendations = self._generate_dependency_recommendations(
            dependency_graph, health_analysis
        )

        return {
            "total_elements": len(elements),
            "dependency_graph": dependency_graph,
            "dependency_metrics": dependency_metrics,
            "critical_paths": critical_paths,
            "health_analysis": health_analysis,
            "visualization_data": visualization_data,
            "recommendations": recommendations,
            "analysis_date": datetime.utcnow().isoformat(),
        }

    def _get_all_elements(self) -> List[Dict]:
        """Get all architecture elements from the database."""
        # This would be adapted to work with your current element models
        try:
            elements = []

            # Get business capabilities
            from app.models.business_capability import BusinessCapability

            capabilities = BusinessCapability.query.all()
            for cap in capabilities:
                elements.append(
                    {
                        "id": cap.id,
                        "name": cap.name,
                        "type": "BusinessCapability",
                        "domain": cap.business_domain or "Unknown",
                        "strategic_importance": cap.strategic_importance,
                        "layer": "Business",
                    }
                )

            # Get application components
            from app.models.application_layer import ApplicationComponent

            applications = ApplicationComponent.query.filter(
                ApplicationComponent.deployment_status.in_(
                    ["production", "Production", "Implementing"]
                )
            ).all()
            for app in applications:
                elements.append(
                    {
                        "id": app.id,
                        "name": app.name,
                        "type": "ApplicationComponent",
                        "technology": app.technology_stack,
                        "layer": "Application",
                    }
                )

            return elements
        except Exception as e:
            print(f"Error getting elements: {e}")
            return []

    def _build_dependency_graph(self, elements: List[Dict]) -> Dict:
        """Build dependency graph from elements and relationships."""

        # Initialize graph structure
        graph = {
            "nodes": [],
            "edges": [],
            "adjacency": {},
            "metrics": {
                "total_nodes": len(elements),
                "total_edges": 0,
                "avg_degree": 0,
                "max_degree": 0,
                "clustering_coefficient": 0,
            },
        }

        # Add nodes
        for element in elements:
            node = {
                "id": element["id"],
                "name": element["name"],
                "type": element["type"],
                "layer": element["layer"],
                "domain": element.get("domain", ""),
                "strategic_importance": element.get("strategic_importance", ""),
                "technology": element.get("technology", ""),
                "dependencies": [],
                "dependents": [],
            }
            graph["nodes"].append(node)
            graph["adjacency"][element["id"]] = {"in": [], "out": []}

        # Add edges based on ArchiMate relationships
        try:
            # Get ArchiMate relationships
            relationships = self._get_archimate_relationships()

            for rel in relationships:
                source_id = rel["source_element_id"]
                target_id = rel["target_element_id"]
                rel_type = rel["relationship_type"]

                # Check if both elements exist in our graph
                if source_id in graph["adjacency"] and target_id in graph["adjacency"]:
                    edge = {
                        "source": source_id,
                        "target": target_id,
                        "type": rel_type,
                        "strength": rel.get("relationship_strength", 3),
                        "impact": rel.get("impact_level", "medium"),
                    }
                    graph["edges"].append(edge)

                    # Update adjacency lists
                    graph["adjacency"][source_id]["out"].append(target_id)
                    graph["adjacency"][target_id]["in"].append(source_id)

                    # Update node dependencies
                    source_node = next(n for n in graph["nodes"] if n["id"] == source_id)
                    target_node = next(n for n in graph["nodes"] if n["id"] == target_id)
                    source_node["dependents"].append(target_id)
                    target_node["dependencies"].append(source_id)
        except Exception as e:
            print(f"Error building relationships: {e}")

        # Calculate graph metrics
        graph["metrics"]["total_edges"] = len(graph["edges"])

        # Calculate degrees
        degrees = []
        for node_id in graph["adjacency"]:
            in_degree = len(graph["adjacency"][node_id]["in"])
            out_degree = len(graph["adjacency"][node_id]["out"])
            total_degree = in_degree + out_degree
            degrees.append(total_degree)

        if degrees:
            graph["metrics"]["avg_degree"] = sum(degrees) / len(degrees)
            graph["metrics"]["max_degree"] = max(degrees)

        return graph

    def _get_archimate_relationships(self) -> List[Dict]:
        """Get ArchiMate relationships from the database."""
        try:
            # Query the archimate_relationships table
            result = db.session.execute(
                text(
                    """
                SELECT source_id, target_id, type
                FROM archimate_relationships
                WHERE source_id IS NOT NULL AND target_id IS NOT NULL
            """
                ),
            ).fetchall()

            return [
                {
                    "source_element_id": row[0],
                    "target_element_id": row[1],
                    "relationship_type": row[2],
                    "relationship_strength": 3,
                    "impact_level": "medium",
                }
                for row in result
            ]
        except Exception as e:
            print(f"Error getting relationships: {e}")
            return []

    def _analyze_dependency_metrics(self, graph: Dict) -> Dict:
        """Analyze dependency metrics for the graph."""

        metrics = {
            "dependency_density": 0,
            "central_elements": [],
            "bottleneck_elements": [],
            "isolated_elements": [],
            "layer_dependencies": {
                "business_to_application": 0,
                "application_to_technology": 0,
                "business_to_technology": 0,
            },
        }

        # Calculate dependency density
        possible_edges = len(graph["nodes"]) * (len(graph["nodes"]) - 1)
        if possible_edges > 0:
            metrics["dependency_density"] = len(graph["edges"]) / possible_edges

        # Find central elements (high degree)
        degrees = {}
        for node in graph["nodes"]:
            total_degree = len(node["dependencies"]) + len(node["dependents"])
            degrees[node["id"]] = total_degree

        if degrees:
            avg_degree = sum(degrees.values()) / len(degrees)
            central_elements = [
                node for node in graph["nodes"] if degrees[node["id"]] > avg_degree * 2
            ]
            metrics["central_elements"] = central_elements

        # Find bottleneck elements (many dependents)
        bottleneck_elements = [node for node in graph["nodes"] if len(node["dependents"]) > 5]
        metrics["bottleneck_elements"] = bottleneck_elements

        # Find isolated elements (no dependencies)
        isolated_elements = [
            node
            for node in graph["nodes"]
            if len(node["dependencies"]) == 0 and len(node["dependents"]) == 0
        ]
        metrics["isolated_elements"] = isolated_elements

        # Analyze layer dependencies
        for edge in graph["edges"]:
            source_node = next((n for n in graph["nodes"] if n["id"] == edge["source"]), None)
            target_node = next((n for n in graph["nodes"] if n["id"] == edge["target"]), None)

            if source_node and target_node:
                if source_node["layer"] == "Business" and target_node["layer"] == "Application":
                    metrics["layer_dependencies"]["business_to_application"] += 1
                elif source_node["layer"] == "Application" and target_node["layer"] == "Technology":
                    metrics["layer_dependencies"]["application_to_technology"] += 1
                elif source_node["layer"] == "Business" and target_node["layer"] == "Technology":
                    metrics["layer_dependencies"]["business_to_technology"] += 1

        return metrics

    def _identify_critical_paths(self, graph: Dict) -> List[Dict]:
        """Identify critical paths in the dependency graph."""

        critical_paths = []

        # Find paths between strategic elements
        strategic_nodes = [
            node
            for node in graph["nodes"]
            if node.get("strategic_importance") in ["critical", "high"]
        ]

        for start_node in strategic_nodes:
            for end_node in strategic_nodes:
                if start_node["id"] != end_node["id"]:
                    path = self._find_shortest_path(graph, start_node["id"], end_node["id"])
                    if path and len(path) > 2:
                        critical_paths.append(
                            {
                                "start": start_node["name"],
                                "end": end_node["name"],
                                "path": [
                                    next(n["name"] for n in graph["nodes"] if n["id"] == node_id)
                                    for node_id in path
                                ],
                                "length": len(path) - 1,
                                "criticality": "HIGH" if len(path) <= 3 else "MEDIUM",
                            }
                        )

        # Sort by criticality and length
        critical_paths.sort(key=lambda x: (x["criticality"], x["length"]))

        return critical_paths[:10]  # Return top 10 critical paths

    def _find_shortest_path(self, graph: Dict, start_id: int, end_id: int) -> List[int]:
        """Find shortest path between two nodes using BFS."""

        if start_id not in graph["adjacency"] or end_id not in graph["adjacency"]:
            return []

        from collections import deque

        queue = deque([(start_id, [start_id])])
        visited = set([start_id])

        while queue:
            current_id, path = queue.popleft()

            if current_id == end_id:
                return path

            for neighbor in graph["adjacency"][current_id]["out"]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return []

    def _analyze_dependency_health(self, graph: Dict) -> Dict:
        """Analyze the health of dependencies."""

        health_analysis = {
            "overall_health_score": 0,
            "health_issues": [],
            "recommendations": [],
            "risk_factors": {
                "high_coupling": 0,
                "circular_dependencies": 0,
                "single_points_of_failure": 0,
                "deep_dependencies": 0,
            },
        }

        # Check for circular dependencies
        circular_deps = self._detect_circular_dependencies(graph)
        health_analysis["risk_factors"]["circular_dependencies"] = len(circular_deps)

        # Check for high coupling (many dependencies)
        high_coupling_elements = [
            node
            for node in graph["nodes"]
            if len(node["dependencies"]) + len(node["dependents"]) > 10
        ]
        health_analysis["risk_factors"]["high_coupling"] = len(high_coupling_elements)

        # Check for single points of failure
        spof_elements = [
            node
            for node in graph["nodes"]
            if len(node["dependents"]) > 5 and node.get("strategic_importance") == "critical"
        ]
        health_analysis["risk_factors"]["single_points_of_failure"] = len(spof_elements)

        # Check for deep dependencies (long dependency chains)
        max_depth = self._calculate_max_dependency_depth(graph)
        health_analysis["risk_factors"]["deep_dependencies"] = max_depth

        # Calculate overall health score
        total_risk = sum(health_analysis["risk_factors"].values())
        health_analysis["overall_health_score"] = max(0, 100 - total_risk * 2)

        # Generate health issues
        if circular_deps:
            health_analysis["health_issues"].append(
                {
                    "type": "CIRCULAR_DEPENDENCIES",
                    "count": len(circular_deps),
                    "severity": "HIGH",
                    "description": "Circular dependencies detected that can cause maintenance issues",
                }
            )

        if high_coupling_elements:
            health_analysis["health_issues"].append(
                {
                    "type": "HIGH_COUPLING",
                    "count": len(high_coupling_elements),
                    "severity": "MEDIUM",
                    "description": "Elements with excessive coupling that reduce modularity",
                }
            )

        if spof_elements:
            health_analysis["health_issues"].append(
                {
                    "type": "SINGLE_POINTS_OF_FAILURE",
                    "count": len(spof_elements),
                    "severity": "HIGH",
                    "description": "Critical elements that are single points of failure",
                }
            )

        return health_analysis

    def _detect_circular_dependencies(self, graph: Dict) -> List[List[int]]:
        """Detect circular dependencies in the graph."""

        circular_deps = []
        visited = set()
        rec_stack = set()

        def dfs(node_id: int, path: List[int]) -> bool:
            if node_id in rec_stack:
                # Found cycle
                cycle_start = path.index(node_id)
                circular_deps.append(path[cycle_start:] + [node_id])
                return True

            if node_id in visited:
                return False

            visited.add(node_id)
            rec_stack.add(node_id)

            for neighbor in graph["adjacency"][node_id]["out"]:
                if dfs(neighbor, path + [neighbor]):
                    return True

            rec_stack.remove(node_id)
            return False

        for node_id in graph["adjacency"]:
            if node_id not in visited:
                dfs(node_id, [node_id])

        return circular_deps

    def _calculate_max_dependency_depth(self, graph: Dict) -> int:
        """Calculate maximum dependency depth."""

        max_depth = 0

        for node_id in graph["adjacency"]:
            depth = self._calculate_node_depth(graph, node_id, set())
            max_depth = max(max_depth, depth)

        return max_depth

    def _calculate_node_depth(self, graph: Dict, node_id: int, visited: set) -> int:
        """Calculate dependency depth for a specific node."""

        if node_id in visited:
            return 0

        visited.add(node_id)

        max_child_depth = 0
        for neighbor in graph["adjacency"][node_id]["out"]:
            child_depth = self._calculate_node_depth(graph, neighbor, visited.copy())
            max_child_depth = max(max_child_depth, child_depth)

        return max_child_depth + 1

    def _generate_visualization_data(self, graph: Dict, critical_paths: List[Dict]) -> Dict:
        """Generate data for dependency visualization."""

        viz_data = {
            "nodes": [],
            "edges": [],
            "layout": "force_directed",
            "groups": {"business": [], "application": [], "technology": []},
        }

        # Prepare nodes for visualization
        for node in graph["nodes"]:
            viz_node = {
                "id": node["id"],
                "name": node["name"],
                "type": node["type"],
                "layer": node["layer"],
                "group": node["layer"].lower(),
                "size": 10 + (len(node["dependencies"]) + len(node["dependents"])) * 2,
                "color": self._get_node_color(node),
                "x": None,
                "y": None,
            }
            viz_data["nodes"].append(viz_node)
            viz_data["groups"][node["layer"].lower()].append(node["id"])

        # Prepare edges for visualization
        for edge in graph["edges"]:
            viz_edge = {
                "source": edge["source"],
                "target": edge["target"],
                "type": edge["type"],
                "width": edge["strength"],
                "color": self._get_edge_color(edge),
                "dashes": edge["type"] in "influence,association",
            }
            viz_data["edges"].append(viz_edge)

        return viz_data

    def _get_node_color(self, node: Dict) -> str:
        """Get color for node based on its properties."""

        if node.get("strategic_importance") == "critical":
            return "#dc3545"  # Red
        elif node.get("strategic_importance") == "high":
            return "#ffc107"  # Yellow
        elif node["layer"] == "Business":
            return "#007bff"  # Blue
        elif node["layer"] == "Application":
            return "#28a745"  # Green
        else:
            return "#6c757d"  # Gray

    def _get_edge_color(self, edge: Dict) -> str:
        """Get color for edge based on its type."""

        edge_colors = {
            "serves": "#007bff",
            "realized by": "#28a745",
            "assigned to": "#ffc107",
            "flows to": "#17a2b8",
            "influence": "#6c757d",
            "association": "#6c757d",
        }

        return edge_colors.get(edge["type"], "#6c757d")

    def _generate_dependency_recommendations(
        self, graph: Dict, health_analysis: Dict
    ) -> List[Dict]:
        """Generate dependency optimization recommendations."""

        recommendations = []

        # Recommendations for circular dependencies
        if health_analysis["risk_factors"]["circular_dependencies"] > 0:
            recommendations.append(
                {
                    "type": "BREAK_CIRCULAR_DEPENDENCIES",
                    "priority": "HIGH",
                    "description": "Resolve circular dependencies to improve maintainability",
                    "affected_elements": health_analysis["risk_factors"]["circular_dependencies"],
                    "estimated_effort": "HIGH",
                    "timeframe": "3 - 6 months",
                }
            )

        # Recommendations for high coupling
        if health_analysis["risk_factors"]["high_coupling"] > 0:
            recommendations.append(
                {
                    "type": "REDUCE_COUPLING",
                    "priority": "MEDIUM",
                    "description": "Reduce excessive coupling to improve modularity",
                    "affected_elements": health_analysis["risk_factors"]["high_coupling"],
                    "estimated_effort": "MEDIUM",
                    "timeframe": "2 - 4 months",
                }
            )

        # Recommendations for single points of failure
        if health_analysis["risk_factors"]["single_points_of_failure"] > 0:
            recommendations.append(
                {
                    "type": "ELIMINATE_SINGLE_POINTS_OF_FAILURE",
                    "priority": "CRITICAL",
                    "description": "Add redundancy for critical single points of failure",
                    "affected_elements": health_analysis["risk_factors"][
                        "single_points_of_failure"
                    ],
                    "estimated_effort": "HIGH",
                    "timeframe": "6 - 12 months",
                }
            )

        # Recommendations for deep dependencies
        if health_analysis["risk_factors"]["deep_dependencies"] > 5:
            recommendations.append(
                {
                    "type": "FLATTEN_DEPENDENCIES",
                    "priority": "MEDIUM",
                    "description": "Flatten deep dependency chains to reduce complexity",
                    "affected_elements": "Multiple elements",
                    "estimated_effort": "MEDIUM",
                    "timeframe": "3 - 6 months",
                }
            )

        return recommendations
