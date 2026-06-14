"""
ArchiMate Viewpoint Builder Service
PRD - 010.2: Build and render viewpoints from model elements

Provides:
- Build viewpoint from element selection
- Filter elements by viewpoint rules
- Generate viewpoint data for visualization
- Export viewpoint to SVG/PNG
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from app.config.archimate_viewpoints import (
    VIEWPOINT_CATEGORIES,
    VIEWPOINTS,
    ViewpointDefinition,
    get_viewpoint,
    get_viewpoint_summary,
    get_viewpoints_allowing_element,
    get_viewpoints_for_layer,
    get_viewpoints_for_stakeholder,
    is_element_allowed_in_viewpoint,
    is_relationship_allowed_in_viewpoint,
    validate_view_against_viewpoint,
)

logger = logging.getLogger(__name__)


@dataclass
class ViewpointElement:
    """Element in a viewpoint"""

    id: int
    name: str
    element_type: str
    description: Optional[str]
    layer: str
    x: float = 0
    y: float = 0
    width: float = 150
    height: float = 60
    properties: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.element_type,
            "description": self.description,
            "layer": self.layer,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "properties": self.properties or {},
        }


@dataclass
class ViewpointRelationship:
    """Relationship in a viewpoint"""

    id: int
    source_id: int
    target_id: int
    relationship_type: str
    name: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "source": self.source_id,
            "target": self.target_id,
            "type": self.relationship_type,
            "name": self.name,
            "properties": self.properties or {},
        }


@dataclass
class Viewpoint:
    """Built viewpoint ready for rendering"""

    code: str
    name: str
    purpose: str
    elements: List[ViewpointElement]
    relationships: List[ViewpointRelationship]
    metadata: Dict[str, Any]
    warnings: List[str]
    generated_at: str = None

    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "code": self.code,
            "name": self.name,
            "purpose": self.purpose,
            "elements": [e.to_dict() for e in self.elements],
            "relationships": [r.to_dict() for r in self.relationships],
            "metadata": self.metadata,
            "warnings": self.warnings,
            "generated_at": self.generated_at,
        }


@dataclass
class ViewpointValidationResult:
    """Result of viewpoint validation"""

    valid: bool
    invalid_elements: List[Dict[str, Any]]
    invalid_relationships: List[Dict[str, Any]]
    warnings: List[str]
    suggestions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "valid": self.valid,
            "invalid_elements": self.invalid_elements,
            "invalid_relationships": self.invalid_relationships,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
        }


class ViewpointBuilder:
    """
    Builds viewpoints from ArchiMate model elements.

    Usage:
        builder = ViewpointBuilder()
        viewpoint = builder.build_viewpoint(
            viewpoint_code='APC',  # Application Cooperation
            element_ids=[1, 2, 3, 4, 5]
        )
    """

    # Layer colors for visualization
    LAYER_COLORS = {
        "motivation": "#CCCCFF",
        "strategy": "#F5DEAA",
        "business": "#FFFFB5",
        "application": "#B5FFFF",
        "technology": "#C9E7B7",
        "physical": "#C9E7B7",
        "implementation": "#FFE0E0",
        "composite": "#FFFFFF",
    }

    # Layer Y positions for layered layout
    LAYER_ORDER = [
        "motivation",
        "strategy",
        "business",
        "application",
        "technology",
        "physical",
        "implementation",
    ]

    def __init__(self):
        self._element_cache = {}

    def build_viewpoint(
        self,
        viewpoint_code: str,
        element_ids: List[int] = None,
        architecture_id: int = None,
        include_relationships: bool = True,
        auto_layout: bool = True,
        max_elements: int = 100,
    ) -> Viewpoint:
        """
        Build a viewpoint from selected elements.

        Args:
            viewpoint_code: ArchiMate viewpoint code (e.g., 'APC', 'ORG')
            element_ids: List of element IDs to include (if None, auto-select)
            architecture_id: Filter by architecture model ID
            include_relationships: Include relationships between elements
            auto_layout: Automatically position elements
            max_elements: Maximum number of elements to include

        Returns:
            Built viewpoint ready for rendering
        """
        viewpoint_def = get_viewpoint(viewpoint_code)
        if not viewpoint_def:
            raise ValueError(f"Unknown viewpoint code: {viewpoint_code}")

        # Get elements from database
        from app import db
        from app.models.archimate_core import ArchiMateElement

        if element_ids:
            query = ArchiMateElement.query.filter(ArchiMateElement.id.in_(element_ids))
            if architecture_id:
                query = query.filter(ArchiMateElement.architecture_id == architecture_id)
            elements = query.all()
        else:
            # Auto-select elements based on viewpoint
            elements = self._auto_select_elements(viewpoint_def, architecture_id, max_elements)

        # Filter elements by viewpoint rules
        filtered_elements, warnings = self._filter_elements(elements, viewpoint_def)

        # Get relationships between filtered elements
        relationships = []
        if include_relationships and filtered_elements:
            element_id_set = {e.id for e in filtered_elements}
            relationships = self._get_relationships(element_id_set, viewpoint_def)

        # Convert to viewpoint elements
        viewpoint_elements = [self._convert_element(e) for e in filtered_elements]

        viewpoint_relationships = [self._convert_relationship(r) for r in relationships]

        # Auto-layout if requested
        if auto_layout:
            viewpoint_elements = self._auto_layout(viewpoint_elements, viewpoint_def)

        return Viewpoint(
            code=viewpoint_code,
            name=viewpoint_def.name,
            purpose=viewpoint_def.purpose,
            elements=viewpoint_elements,
            relationships=viewpoint_relationships,
            metadata={
                "stakeholders": viewpoint_def.typical_stakeholders,
                "concerns": viewpoint_def.concerns,
                "layer": viewpoint_def.layer,
                "total_elements": len(viewpoint_elements),
                "total_relationships": len(viewpoint_relationships),
                "architecture_id": architecture_id,
                "allowed_elements": viewpoint_def.allowed_elements,
                "allowed_relationships": viewpoint_def.allowed_relationships,
            },
            warnings=warnings,
        )

    def _filter_elements(
        self, elements: List[Any], viewpoint_def: ViewpointDefinition
    ) -> Tuple[List[Any], List[str]]:
        """Filter elements by viewpoint allowed types"""
        filtered = []
        warnings = []

        for element in elements:
            # Get element type - handle both 'type' and 'element_type' attributes
            element_type = getattr(element, "element_type", None) or getattr(element, "type", None)

            if is_element_allowed_in_viewpoint(element_type, viewpoint_def.code):
                filtered.append(element)
            else:
                warnings.append(
                    f"Element '{element.name}' ({element_type}) "
                    f"excluded - not allowed in {viewpoint_def.name}"
                )

        return filtered, warnings

    def _get_relationships(
        self, element_ids: Set[int], viewpoint_def: ViewpointDefinition
    ) -> List[Any]:
        """Get relationships between elements"""
        from app.models.archimate_core import ArchiMateRelationship

        relationships = ArchiMateRelationship.query.filter(
            ArchiMateRelationship.source_id.in_(element_ids),
            ArchiMateRelationship.target_id.in_(element_ids),
        ).all()

        # Filter by allowed relationship types
        filtered = []
        for rel in relationships:
            rel_type = getattr(rel, "relationship_type", None) or getattr(rel, "type", None)
            if is_relationship_allowed_in_viewpoint(rel_type, viewpoint_def.code):
                filtered.append(rel)

        return filtered

    def _auto_select_elements(
        self,
        viewpoint_def: ViewpointDefinition,
        architecture_id: int = None,
        max_elements: int = 100,
    ) -> List[Any]:
        """Auto-select elements based on viewpoint rules"""
        from app.models.archimate_core import ArchiMateElement

        query = ArchiMateElement.query

        if architecture_id:
            query = query.filter(ArchiMateElement.architecture_id == architecture_id)

        if "*" in viewpoint_def.allowed_elements:
            # Layered viewpoint - get elements from primary layer
            return query.limit(max_elements).all()
        else:
            return (
                query.filter(ArchiMateElement.type.in_(viewpoint_def.allowed_elements))
                .limit(max_elements)
                .all()
            )

    def _convert_element(self, element: Any) -> ViewpointElement:
        """Convert database element to viewpoint element"""
        element_type = getattr(element, "element_type", None) or getattr(element, "type", None)

        return ViewpointElement(
            id=element.id,
            name=element.name,
            element_type=element_type,
            description=getattr(element, "description", None),
            layer=getattr(element, "layer", "unknown"),
            properties={
                "scope": getattr(element, "scope", None),
                "status": getattr(element, "status", None),
                "priority": getattr(element, "priority", None),
            },
        )

    def _convert_relationship(self, rel: Any) -> ViewpointRelationship:
        """Convert database relationship to viewpoint relationship"""
        rel_type = getattr(rel, "relationship_type", None) or getattr(rel, "type", None)
        source_id = getattr(rel, "source_element_id", None) or getattr(rel, "source_id", None)
        target_id = getattr(rel, "target_element_id", None) or getattr(rel, "target_id", None)

        return ViewpointRelationship(
            id=rel.id,
            source_id=source_id,
            target_id=target_id,
            relationship_type=rel_type,
            name=getattr(rel, "name", None),
        )

    def _auto_layout(
        self, elements: List[ViewpointElement], viewpoint_def: ViewpointDefinition
    ) -> List[ViewpointElement]:
        """Auto-layout elements in a grid based on layer"""
        # Group elements by layer
        by_layer = {}
        for elem in elements:
            layer = elem.layer.lower() if elem.layer else "unknown"
            if layer not in by_layer:
                by_layer[layer] = []
            by_layer[layer].append(elem)

        # Layout layer by layer
        y_offset = 50
        layer_height = 120
        element_spacing = 30

        for layer in self.LAYER_ORDER:
            if layer in by_layer:
                x_offset = 50
                row_count = 0
                max_per_row = 5

                for elem in by_layer[layer]:
                    elem.x = x_offset
                    elem.y = y_offset
                    x_offset += elem.width + element_spacing
                    row_count += 1

                    # Wrap to next row
                    if row_count >= max_per_row:
                        row_count = 0
                        x_offset = 50
                        y_offset += elem.height + element_spacing

                y_offset += layer_height

        # Handle unknown layer
        if "unknown" in by_layer:
            x_offset = 50
            for elem in by_layer["unknown"]:
                elem.x = x_offset
                elem.y = y_offset
                x_offset += elem.width + element_spacing

        return elements

    def validate_viewpoint(
        self, viewpoint_code: str, element_ids: List[int], relationship_ids: List[int] = None
    ) -> ViewpointValidationResult:
        """
        Validate elements and relationships against viewpoint rules.

        Args:
            viewpoint_code: ArchiMate viewpoint code
            element_ids: List of element IDs to validate
            relationship_ids: Optional list of relationship IDs to validate

        Returns:
            ViewpointValidationResult with validation details
        """
        viewpoint_def = get_viewpoint(viewpoint_code)
        if not viewpoint_def:
            return ViewpointValidationResult(
                valid=False,
                invalid_elements=[],
                invalid_relationships=[],
                warnings=[f"Unknown viewpoint code: {viewpoint_code}"],
                suggestions=[],
            )

        from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship

        invalid_elements = []
        invalid_relationships = []
        warnings = []
        suggestions = []

        # Validate elements
        elements = ArchiMateElement.query.filter(ArchiMateElement.id.in_(element_ids)).all()

        for element in elements:
            element_type = getattr(element, "element_type", None) or getattr(element, "type", None)
            if not is_element_allowed_in_viewpoint(element_type, viewpoint_code):
                invalid_elements.append(
                    {
                        "id": element.id,
                        "name": element.name,
                        "type": element_type,
                        "reason": f"Element type '{element_type}' not allowed in {viewpoint_def.name}",
                    }
                )

                # Suggest alternative viewpoints
                alt_viewpoints = get_viewpoints_allowing_element(element_type)
                if alt_viewpoints:
                    suggestions.append(
                        f"Consider using {', '.join([vp.code for vp in alt_viewpoints[:3]])} "
                        f"viewpoint for element '{element.name}'"
                    )

        # Validate relationships
        if relationship_ids:
            relationships = ArchiMateRelationship.query.filter(
                ArchiMateRelationship.id.in_(relationship_ids)
            ).all()

            for rel in relationships:
                rel_type = getattr(rel, "relationship_type", None) or getattr(rel, "type", None)
                if not is_relationship_allowed_in_viewpoint(rel_type, viewpoint_code):
                    invalid_relationships.append(
                        {
                            "id": rel.id,
                            "type": rel_type,
                            "reason": f"Relationship type '{rel_type}' not allowed in {viewpoint_def.name}",
                        }
                    )

        valid = len(invalid_elements) == 0 and len(invalid_relationships) == 0

        return ViewpointValidationResult(
            valid=valid,
            invalid_elements=invalid_elements,
            invalid_relationships=invalid_relationships,
            warnings=warnings,
            suggestions=suggestions,
        )

    def get_available_viewpoints(self) -> List[Dict[str, Any]]:
        """Get list of all available viewpoints"""
        return [
            {
                "code": vp.code,
                "name": vp.name,
                "purpose": vp.purpose,
                "layer": vp.layer,
                "stakeholders": vp.typical_stakeholders,
                "concerns": vp.concerns,
                "element_count": len(vp.allowed_elements)
                if "*" not in vp.allowed_elements
                else "all",
                "relationship_count": len(vp.allowed_relationships)
                if "*" not in vp.allowed_relationships
                else "all",
            }
            for vp in VIEWPOINTS.values()
        ]

    def get_viewpoints_by_category(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get viewpoints organized by category"""
        result = {}
        for category, viewpoint_keys in VIEWPOINT_CATEGORIES.items():
            result[category] = []
            for key in viewpoint_keys:
                if key in VIEWPOINTS:
                    vp = VIEWPOINTS[key]
                    result[category].append(
                        {"code": vp.code, "name": vp.name, "purpose": vp.purpose, "layer": vp.layer}
                    )
        return result

    def suggest_viewpoints(
        self,
        element_ids: List[int] = None,
        stakeholder_role: str = None,
        concerns: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Suggest appropriate viewpoints based on elements or stakeholder.

        Args:
            element_ids: Optional list of element IDs to analyze
            stakeholder_role: Optional stakeholder role (e.g., 'Enterprise Architect')
            concerns: Optional list of concerns to address

        Returns:
            List of suggested viewpoints with relevance scores
        """
        suggestions = []

        # Suggest based on stakeholder role
        if stakeholder_role:
            stakeholder_viewpoints = get_viewpoints_for_stakeholder(stakeholder_role)
            for vp in stakeholder_viewpoints:
                suggestions.append(
                    {
                        "code": vp.code,
                        "name": vp.name,
                        "purpose": vp.purpose,
                        "relevance_score": 10,
                        "reason": f"Recommended for {stakeholder_role} stakeholders",
                    }
                )

        # Suggest based on elements
        if element_ids:
            from app.models.archimate_core import ArchiMateElement

            elements = ArchiMateElement.query.filter(ArchiMateElement.id.in_(element_ids)).all()

            element_types = set()
            layers = set()

            for element in elements:
                element_type = getattr(element, "element_type", None) or getattr(
                    element, "type", None
                )
                if element_type:
                    element_types.add(element_type)
                layer = getattr(element, "layer", None)
                if layer:
                    layers.add(layer.lower())

            # Score viewpoints based on element coverage
            for vp in VIEWPOINTS.values():
                if "*" in vp.allowed_elements:
                    # Layered viewpoint - good for mixed elements
                    score = len(element_types) * 2 if len(layers) > 1 else 3
                else:
                    # Score based on overlap
                    overlap = len(element_types.intersection(set(vp.allowed_elements)))
                    score = (overlap / len(element_types)) * 10 if element_types else 0

                if score > 0:
                    # Check if already suggested
                    existing = next((s for s in suggestions if s["code"] == vp.code), None)
                    if existing:
                        existing["relevance_score"] += score
                    else:
                        suggestions.append(
                            {
                                "code": vp.code,
                                "name": vp.name,
                                "purpose": vp.purpose,
                                "relevance_score": score,
                                "reason": f"Covers {overlap if '*' not in vp.allowed_elements else 'all'} element types",
                            }
                        )

        # Sort by relevance score
        suggestions.sort(key=lambda x: x["relevance_score"], reverse=True)

        return suggestions[:10]  # Return top 10

    def export_to_svg(self, viewpoint: Viewpoint) -> str:
        """
        Export viewpoint to SVG format.

        Args:
            viewpoint: Built viewpoint

        Returns:
            SVG string
        """
        # Calculate canvas size
        max_x = max((e.x + e.width for e in viewpoint.elements), default=800)
        max_y = max((e.y + e.height for e in viewpoint.elements), default=600)

        width = max_x + 100
        height = max_y + 100

        svg_parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">']

        # Add defs for markers (arrowheads)
        svg_parts.append(
            """
            <defs>
                <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                    <polygon points="0 0, 10 3.5, 0 7" fill="#666"/>
                </marker>
            </defs>
        """
        )

        # Draw relationships first (so they appear behind elements)
        element_map = {e.id: e for e in viewpoint.elements}
        for rel in viewpoint.relationships:
            source = element_map.get(rel.source_id)
            target = element_map.get(rel.target_id)

            if source and target:
                # Calculate line endpoints
                x1 = source.x + source.width / 2
                y1 = source.y + source.height / 2
                x2 = target.x + target.width / 2
                y2 = target.y + target.height / 2

                svg_parts.append(
                    f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                    f'stroke="#666" stroke-width="1" marker-end="url(#arrowhead)"/>'
                )

        # Draw elements
        for elem in viewpoint.elements:
            color = self.LAYER_COLORS.get(elem.layer.lower(), "#FFFFFF")

            svg_parts.append(
                f'<rect x="{elem.x}" y="{elem.y}" width="{elem.width}" height="{elem.height}" '
                f'fill="{color}" stroke="#333" stroke-width="1" rx="5"/>'
            )

            # Add element name (truncate if too long)
            name = elem.name[:20] + "..." if len(elem.name) > 20 else elem.name
            text_x = elem.x + elem.width / 2
            text_y = elem.y + elem.height / 2 + 5

            svg_parts.append(
                f'<text x="{text_x}" y="{text_y}" text-anchor="middle" '
                f'font-family="Arial" font-size="12">{name}</text>'
            )

            # Add element type
            type_y = text_y + 15
            svg_parts.append(
                f'<text x="{text_x}" y="{type_y}" text-anchor="middle" '
                f'font-family="Arial" font-size="10" fill="#666">&lt;&lt;{elem.element_type}&gt;&gt;</text>'
            )

        svg_parts.append("</svg>")

        return "\n".join(svg_parts)

    def to_dict(self, viewpoint: Viewpoint) -> Dict[str, Any]:
        """Convert viewpoint to dictionary for JSON serialization"""
        return viewpoint.to_dict()


# Singleton
_builder: Optional[ViewpointBuilder] = None


def get_viewpoint_builder() -> ViewpointBuilder:
    """Get singleton instance of ViewpointBuilder"""
    global _builder
    if _builder is None:
        _builder = ViewpointBuilder()
    return _builder
