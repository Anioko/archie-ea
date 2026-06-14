"""
-> app.modules.architecture.services.modeling_service

ArchiMate 3.2 Viewpoint Builder Service

Generates ArchiMate 3.2 compliant viewpoints for application components.
Supports the following viewpoints:
- Application Cooperation: App-to-app integration and collaboration
- Application Usage: Business process support and service usage
- Implementation & Migration: Vendor products and technology stack
- Motivation & Compliance: Goals, requirements, drivers, constraints

Design Pattern:
- Each viewpoint returns structured data suitable for diagram generation
- Validates ArchiMate 3.2 metamodel rules
- Supports configurable depth traversal
"""

from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.models.business_capabilities import BusinessCapability

from app import db
from app.models.application_layer import ApplicationEvent, ApplicationInterface
from app.models.application_portfolio import ApplicationComponent
from app.models.models import ArchiMateElement, ArchiMateRelationship
from app.models.vendor.vendor_organization import VendorProduct, application_vendor_products


class ArchiMateViewpointBuilder:
    """Service for building ArchiMate 3.2 viewpoints from application data."""

    # ArchiMate 3.2 metamodel: allowed relationship types per layer
    ALLOWED_RELATIONSHIPS = {
        "application": [
            "serving",
            "access",
            "assignment",
            "realization",
            "composition",
            "aggregation",
            "flow",
            "triggering",
        ],
        "business": [
            "serving",
            "access",
            "assignment",
            "realization",
            "composition",
            "aggregation",
            "flow",
            "triggering",
        ],
        "technology": [
            "serving",
            "access",
            "assignment",
            "realization",
            "composition",
            "aggregation",
        ],
        "motivation": ["realization", "influence", "association"],
        "strategy": ["realization", "influence", "association", "aggregation"],
    }

    def __init__(self, application_id: int):
        """
        Initialize viewpoint builder for a specific application.

        Args:
            application_id: ID of the ApplicationComponent
        """
        self.application_id = application_id
        self.app = ApplicationComponent.query.get(application_id)
        if not self.app:
            raise ValueError(f"Application {application_id} not found")

        self.archimate_element = None
        if self.app.archimate_element_id:
            self.archimate_element = db.session.get(ArchiMateElement, self.app.archimate_element_id)

    def build_cooperation_viewpoint(self, depth: int = 2) -> Dict:
        """
        Build Application Cooperation Viewpoint (ArchiMate 3.2).

        Shows:
        - Application components and their relationships
        - Application interfaces (APIs, services)
        - Application events (pub/sub, messaging)
        - Data flows between applications

        Args:
            depth: Relationship traversal depth (1 - 3)

        Returns:
            Dict with nodes, edges, and metadata for diagram generation
        """
        if not self.archimate_element:
            return self._empty_viewpoint(
                "Application Cooperation",
                "Link this application to an ArchiMate element to view cooperation diagram",
            )

        nodes = []
        edges = []
        visited_elements = set()

        # Add central application node
        central_node = self._create_node(
            self.archimate_element, is_central=True, metadata={"app_id": self.application_id}
        )
        nodes.append(central_node)
        visited_elements.add(self.archimate_element.id)

        # Traverse relationships to find cooperating applications
        self._traverse_cooperation_relationships(
            self.archimate_element, nodes, edges, visited_elements, current_depth=0, max_depth=depth
        )

        # Add interfaces as connection points
        interfaces = ApplicationInterface.query.filter(
            or_(
                ApplicationInterface.provider_application_id == self.archimate_element.id,
                ApplicationInterface.archimate_element_id == self.archimate_element.id,
            )
        ).all()

        for interface in interfaces:
            if interface.archimate_element_id:
                interface_element = db.session.get(ArchiMateElement, interface.archimate_element_id)
                if interface_element and interface_element.id not in visited_elements:
                    nodes.append(self._create_node(interface_element, node_type="interface"))
                    visited_elements.add(interface_element.id)

                    # Link interface to application
                    edges.append(
                        {
                            "source": self.archimate_element.id,
                            "target": interface_element.id,
                            "type": "composition",
                            "label": "exposes",
                        }
                    )

        return {
            "viewpoint_type": "application_cooperation",
            "title": f"Application Cooperation: {self.app.name}",
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "central_app_id": self.application_id,
                "node_count": len(nodes),
                "relationship_count": len(edges),
                "depth": depth,
            },
        }

    def build_usage_viewpoint(self, depth: int = 2) -> Dict:
        """
        Build Application Usage Viewpoint (ArchiMate 3.2).

        Shows:
        - Business processes using this application
        - Business services realized by application services
        - Business capabilities supported
        - Application services provided

        Args:
            depth: Relationship traversal depth (1 - 3)

        Returns:
            Dict with nodes, edges, and metadata for diagram generation
        """
        if not self.archimate_element:
            return self._empty_viewpoint(
                "Application Usage",
                "Link this application to an ArchiMate element to view usage diagram",
            )

        nodes = []
        edges = []
        visited_elements = set()

        # Add central application node
        nodes.append(self._create_node(self.archimate_element, is_central=True))
        visited_elements.add(self.archimate_element.id)

        # Find business capabilities supported by this application
        from app.models.application_capability import ApplicationCapabilityMapping

        capability_mappings = (
            db.session.query(ApplicationCapabilityMapping, BusinessCapability)
            .join(
                BusinessCapability,
                ApplicationCapabilityMapping.business_capability_id == BusinessCapability.id,
            )
            .filter(ApplicationCapabilityMapping.application_component_id == self.application_id)
            .all()
        )

        for mapping, capability in capability_mappings:
            if capability.archimate_element_id:
                cap_element = db.session.get(ArchiMateElement, capability.archimate_element_id)
                if cap_element and cap_element.id not in visited_elements:
                    nodes.append(self._create_node(cap_element, node_type="capability"))
                    visited_elements.add(cap_element.id)

                    # Application realizes capability
                    edges.append(
                        {
                            "source": self.archimate_element.id,
                            "target": cap_element.id,
                            "type": "realization",
                            "label": f"{mapping.support_level or 'supports'}",
                        }
                    )

        # Find business layer elements that use this application
        relationships = (
            ArchiMateRelationship.query.options(
                joinedload(ArchiMateRelationship.source), joinedload(ArchiMateRelationship.target)
            )
            .filter(
                or_(
                    ArchiMateRelationship.source_id == self.archimate_element.id,
                    ArchiMateRelationship.target_id == self.archimate_element.id,
                )
            )
            .all()
        )

        for rel in relationships:
            # Find business layer elements
            if (
                rel.source
                and rel.source.layer == "business"
                and rel.source.id not in visited_elements
            ):
                nodes.append(self._create_node(rel.source, node_type="business"))
                visited_elements.add(rel.source.id)
                edges.append(
                    {
                        "source": rel.source.id,
                        "target": rel.target.id,
                        "type": rel.type,
                        "label": rel.type.replace("_", " "),
                    }
                )
            elif (
                rel.target
                and rel.target.layer == "business"
                and rel.target.id not in visited_elements
            ):
                nodes.append(self._create_node(rel.target, node_type="business"))
                visited_elements.add(rel.target.id)
                edges.append(
                    {
                        "source": rel.source.id,
                        "target": rel.target.id,
                        "type": rel.type,
                        "label": rel.type.replace("_", " "),
                    }
                )

        return {
            "viewpoint_type": "application_usage",
            "title": f"Application Usage: {self.app.name}",
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "central_app_id": self.application_id,
                "capabilities_count": len(capability_mappings),
                "node_count": len(nodes),
                "relationship_count": len(edges),
            },
        }

    def build_implementation_viewpoint(self) -> Dict:
        """
        Build Implementation & Migration Viewpoint (ArchiMate 3.2).

        Shows:
        - Vendor products implementing this application
        - Technology services and infrastructure
        - Deployment nodes
        - Migration paths (if replacement planned)

        Returns:
            Dict with nodes, edges, and metadata for diagram generation
        """
        if not self.archimate_element:
            return self._empty_viewpoint(
                "Implementation & Migration",
                "Link this application to an ArchiMate element to view implementation diagram",
            )

        nodes = []
        edges = []
        visited_elements = set()

        # Add central application node
        nodes.append(self._create_node(self.archimate_element, is_central=True))
        visited_elements.add(self.archimate_element.id)

        # Find vendor products
        vendor_links = (
            db.session.query(VendorProduct)
            .join(
                application_vendor_products,
                VendorProduct.id == application_vendor_products.c.vendor_product_id,
            )
            .filter(application_vendor_products.c.archimate_element_id == self.archimate_element.id)
            .all()
        )

        for product in vendor_links:
            if product.archimate_product_element_id:
                product_element = db.session.get(
                    ArchiMateElement, product.archimate_product_element_id
                )
                if product_element and product_element.id not in visited_elements:
                    nodes.append(self._create_node(product_element, node_type="product"))
                    visited_elements.add(product_element.id)

                    # Product realizes application
                    edges.append(
                        {
                            "source": product_element.id,
                            "target": self.archimate_element.id,
                            "type": "realization",
                            "label": "implements",
                        }
                    )

        # Find technology layer elements
        tech_relationships = (
            ArchiMateRelationship.query.options(
                joinedload(ArchiMateRelationship.source), joinedload(ArchiMateRelationship.target)
            )
            .filter(
                or_(
                    ArchiMateRelationship.source_id == self.archimate_element.id,
                    ArchiMateRelationship.target_id == self.archimate_element.id,
                )
            )
            .all()
        )

        for rel in tech_relationships:
            if (
                rel.source
                and rel.source.layer == "technology"
                and rel.source.id not in visited_elements
            ):
                nodes.append(self._create_node(rel.source, node_type="technology"))
                visited_elements.add(rel.source.id)
                edges.append(
                    {
                        "source": rel.source.id,
                        "target": rel.target.id,
                        "type": rel.type,
                        "label": rel.type.replace("_", " "),
                    }
                )
            elif (
                rel.target
                and rel.target.layer == "technology"
                and rel.target.id not in visited_elements
            ):
                nodes.append(self._create_node(rel.target, node_type="technology"))
                visited_elements.add(rel.target.id)
                edges.append(
                    {
                        "source": rel.source.id,
                        "target": rel.target.id,
                        "type": rel.type,
                        "label": rel.type.replace("_", " "),
                    }
                )

        # Check for replacement application (migration path)
        if self.app.replacement_application:
            # This would require looking up the replacement app
            # For now, just add metadata
            pass

        return {
            "viewpoint_type": "implementation_migration",
            "title": f"Implementation & Migration: {self.app.name}",
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "central_app_id": self.application_id,
                "vendor_products_count": len(vendor_links),
                "node_count": len(nodes),
                "relationship_count": len(edges),
                "has_replacement": bool(self.app.replacement_application),
            },
        }

    def build_motivation_viewpoint(self) -> Dict:
        """
        Build Motivation & Compliance Viewpoint (ArchiMate 3.2).

        Shows:
        - Goals realized by this application
        - Requirements implemented
        - Drivers influencing the application
        - Constraints limiting the application
        - Stakeholders interested in the application

        Returns:
            Dict with nodes, edges, and metadata for diagram generation
        """
        if not self.archimate_element:
            return self._empty_viewpoint(
                "Motivation & Compliance",
                "Link this application to an ArchiMate element to view motivation diagram",
            )

        nodes = []
        edges = []
        visited_elements = set()

        # Add central application node
        nodes.append(self._create_node(self.archimate_element, is_central=True))
        visited_elements.add(self.archimate_element.id)

        # Find requirements linked to this application
        from app.models.models import Requirement
        from app.models.relationship_tables import ApplicationRequirementMapping

        requirements = (
            db.session.query(Requirement)
            .join(
                ApplicationRequirementMapping,
                Requirement.id == ApplicationRequirementMapping.requirement_id,
            )
            .filter(ApplicationRequirementMapping.application_component_id == self.application_id)
            .all()
        )

        for req in requirements:
            if req.archimate_element_id:
                req_element = db.session.get(ArchiMateElement, req.archimate_element_id)
                if req_element and req_element.id not in visited_elements:
                    nodes.append(self._create_node(req_element, node_type="requirement"))
                    visited_elements.add(req_element.id)

                    # Application realizes requirement
                    edges.append(
                        {
                            "source": self.archimate_element.id,
                            "target": req_element.id,
                            "type": "realization",
                            "label": "implements",
                        }
                    )

                    # Find goals, drivers, stakeholders linked to requirement
                    if req.goal_id:
                        goal_element = db.session.get(ArchiMateElement, req.goal_id)
                        if goal_element and goal_element.id not in visited_elements:
                            nodes.append(self._create_node(goal_element, node_type="goal"))
                            visited_elements.add(goal_element.id)
                            edges.append(
                                {
                                    "source": req_element.id,
                                    "target": goal_element.id,
                                    "type": "realization",
                                    "label": "realizes",
                                }
                            )

                    if req.driver_id:
                        driver_element = db.session.get(ArchiMateElement, req.driver_id)
                        if driver_element and driver_element.id not in visited_elements:
                            nodes.append(self._create_node(driver_element, node_type="driver"))
                            visited_elements.add(driver_element.id)
                            edges.append(
                                {
                                    "source": driver_element.id,
                                    "target": req_element.id,
                                    "type": "influence",
                                    "label": "drives",
                                }
                            )

        return {
            "viewpoint_type": "motivation_compliance",
            "title": f"Motivation & Compliance: {self.app.name}",
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "central_app_id": self.application_id,
                "requirements_count": len(requirements),
                "node_count": len(nodes),
                "relationship_count": len(edges),
            },
        }

    def calculate_impact_score(self, change_type: str = "modification") -> Dict:
        """
        Calculate impact score for changes to this application.

        Args:
            change_type: Type of change (modification, retirement, replacement)

        Returns:
            Dict with impact score (0 - 100) and breakdown by category
        """
        if not self.archimate_element:
            return {"total_score": 0, "breakdown": {}, "risk_level": "unknown"}

        impact_breakdown = {
            "downstream_dependencies": 0,
            "upstream_dependencies": 0,
            "business_criticality": 0,
            "integration_complexity": 0,
            "vendor_lock_in": 0,
        }

        # Count downstream dependencies (what consumes this app)
        downstream = ArchiMateRelationship.query.filter(
            ArchiMateRelationship.source_id == self.archimate_element.id
        ).count()
        impact_breakdown["downstream_dependencies"] = min(downstream * 5, 30)

        # Count upstream dependencies (what this app consumes)
        upstream = ArchiMateRelationship.query.filter(
            ArchiMateRelationship.target_id == self.archimate_element.id
        ).count()
        impact_breakdown["upstream_dependencies"] = min(upstream * 3, 20)

        # Business criticality
        criticality_scores = {
            "mission_critical": 30,
            "business_critical": 20,
            "important": 10,
            "supporting": 5,
        }
        impact_breakdown["business_criticality"] = criticality_scores.get(
            self.app.business_criticality, 0
        )

        # Integration complexity (number of interfaces)
        interface_count = ApplicationInterface.query.filter(
            ApplicationInterface.provider_application_id == self.archimate_element.id
        ).count()
        impact_breakdown["integration_complexity"] = min(interface_count * 4, 15)

        # Vendor lock-in (proprietary vendor products)
        vendor_count = (
            db.session.query(VendorProduct)
            .join(
                application_vendor_products,
                VendorProduct.id == application_vendor_products.c.vendor_product_id,
            )
            .filter(application_vendor_products.c.archimate_element_id == self.archimate_element.id)
            .count()
        )
        impact_breakdown["vendor_lock_in"] = min(vendor_count * 3, 15)

        total_score = sum(impact_breakdown.values())

        # Determine risk level
        if total_score >= 70:
            risk_level = "critical"
        elif total_score >= 50:
            risk_level = "high"
        elif total_score >= 30:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "total_score": total_score,
            "breakdown": impact_breakdown,
            "risk_level": risk_level,
            "change_type": change_type,
            "recommendations": self._get_impact_recommendations(total_score, change_type),
        }

    # Private helper methods

    def _traverse_cooperation_relationships(
        self,
        element: ArchiMateElement,
        nodes: List,
        edges: List,
        visited: Set,
        current_depth: int,
        max_depth: int,
    ):
        """Recursively traverse application cooperation relationships."""
        if current_depth >= max_depth:
            return

        relationships = (
            ArchiMateRelationship.query.options(
                joinedload(ArchiMateRelationship.source), joinedload(ArchiMateRelationship.target)
            )
            .filter(
                or_(
                    ArchiMateRelationship.source_id == element.id,
                    ArchiMateRelationship.target_id == element.id,
                )
            )
            .all()
        )

        for rel in relationships:
            # Only include application layer elements
            related_element = None
            is_outbound = rel.source_id == element.id

            if is_outbound and rel.target and rel.target.layer == "application":
                related_element = rel.target
            elif not is_outbound and rel.source and rel.source.layer == "application":
                related_element = rel.source

            if related_element and related_element.id not in visited:
                nodes.append(self._create_node(related_element))
                visited.add(related_element.id)

                edges.append(
                    {
                        "source": rel.source.id,
                        "target": rel.target.id,
                        "type": rel.type,
                        "label": rel.type.replace("_", " "),
                        "direction": "outbound" if is_outbound else "inbound",
                    }
                )

                # Recurse
                self._traverse_cooperation_relationships(
                    related_element, nodes, edges, visited, current_depth + 1, max_depth
                )

    def _create_node(
        self,
        element: ArchiMateElement,
        is_central: bool = False,
        node_type: str = None,
        metadata: Dict = None,
    ) -> Dict:
        """Create a node dictionary for diagram rendering."""
        return {
            "id": element.id,
            "label": element.name,
            "type": node_type or element.type,
            "layer": element.layer,
            "is_central": is_central,
            "description": element.description,
            "metadata": metadata or {},
        }

    def _empty_viewpoint(self, viewpoint_name: str, message: str) -> Dict:
        """Return empty viewpoint structure with message."""
        return {
            "viewpoint_type": viewpoint_name.lower().replace(" ", "_"),
            "title": viewpoint_name,
            "nodes": [],
            "edges": [],
            "metadata": {"message": message, "empty": True},
        }

    def _get_impact_recommendations(self, score: int, change_type: str) -> List[str]:
        """Generate recommendations based on impact score."""
        recommendations = []

        if score >= 70:
            recommendations.append(
                "⚠️ Critical impact - Requires executive approval and detailed migration plan"
            )
            recommendations.append(
                "Conduct comprehensive impact analysis across all dependent systems"
            )
            recommendations.append("Plan for extended testing and rollback procedures")
        elif score >= 50:
            recommendations.append("⚠️ High impact - Requires architecture review board approval")
            recommendations.append("Identify and notify all stakeholders of dependent systems")
            recommendations.append("Create detailed integration testing plan")
        elif score >= 30:
            recommendations.append("Medium impact - Standard change management process applies")
            recommendations.append("Review integration points and update documentation")
        else:
            recommendations.append("Low impact - Proceed with standard deployment process")

        if change_type == "retirement":
            recommendations.append("Ensure all dependent applications have migration paths")

        return recommendations


def validate_relationship(
    source_element: ArchiMateElement, target_element: ArchiMateElement, relationship_type: str
) -> Tuple[bool, Optional[str]]:
    """
    Validate if a relationship is allowed per ArchiMate 3.2 metamodel.

    Args:
        source_element: Source ArchiMate element
        target_element: Target ArchiMate element
        relationship_type: Proposed relationship type

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Basic validation
    if not source_element or not target_element:
        return False, "Source and target elements are required"

    if not relationship_type:
        return False, "Relationship type is required"

    # Check if relationship type is valid for source layer
    source_layer = source_element.layer or "unknown"
    allowed_types = ArchiMateViewpointBuilder.ALLOWED_RELATIONSHIPS.get(source_layer, [])

    if relationship_type not in allowed_types:
        return False, f"Relationship '{relationship_type}' not allowed for {source_layer} layer"

    # Additional metamodel rules can be added here
    # For example: composition relationships must be within same layer
    if relationship_type == "composition" and source_element.layer != target_element.layer:
        return False, "Composition relationships must be within the same layer"

    return True, None
