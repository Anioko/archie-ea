"""
ArchiMate Mapping Agent

Intelligent agent for mapping business concepts to ArchiMate elements
and validating against ArchiMate 3.2 metamodel.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import db
from app.models.archimate_core import ArchiMateElement
from app.models.archimate_element_types import ArchiMateElementTypes
from app.models.constants import ArchiMateLayer, ArchiMateRelationshipType
from app.services.llm_service import LLMService
from app.services.vector_embedding_service import VectorEmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class ArchiMateMapping:
    """Represents a mapping to ArchiMate element."""

    element_type: str
    layer: str
    name: str
    description: str
    confidence_score: float
    reasoning: str


@dataclass
class RelationshipSuggestion:
    """Suggested relationship between ArchiMate elements."""

    source_id: int
    target_id: int
    relationship_type: str
    confidence_score: float
    reasoning: str


@dataclass
class ValidationResult:
    """Result of ArchiMate validation."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]


class ArchiMateMappingAgent:
    """
    Intelligent agent for ArchiMate element mapping.

    Uses semantic search and LLM to:
    1. Map business concepts to ArchiMate elements
    2. Suggest relationships between elements
    3. Validate against ArchiMate 3.2 metamodel
    4. Generate ArchiMate viewpoints
    """

    AGENT_NAME = "archimate_mapping"
    AGENT_DEPENDENCIES = ["capability_discovery"]

    def __init__(self, user_id: Optional[int] = None):
        self.llm_service = LLMService()
        self.embedding_service = VectorEmbeddingService()
        self.user_id = user_id

    async def map_to_archimate(self, entity: Any, entity_type: str) -> ArchiMateMapping:
        """Map any entity to appropriate ArchiMate element."""
        # Build context based on entity type
        if entity_type == "capability":
            context = f"Capability: {entity.name} - {entity.description or ''}"
        elif entity_type == "application":
            context = f"Application: {entity.name} - {entity.description or ''}"
        elif entity_type == "process":
            context = f"Process: {entity.process_name} - Code: {entity.process_code}"
        else:
            context = str(entity)

        # Get valid element types for context
        all_types = list(ArchiMateElementTypes.get_all_elements().keys())

        prompt = f"""Map this entity to the most appropriate ArchiMate 3.2 element.

ENTITY ({entity_type}):
{context}

AVAILABLE ARCHIMATE ELEMENT TYPES:
{', '.join(all_types)}

ARCHIMATE LAYERS:
{', '.join(ArchiMateLayer.ALL)}

Determine the best ArchiMate element mapping.

RESPOND WITH JSON:
{{
    "element_type": "ApplicationComponent",
    "layer": "application",
    "name": "...",
    "description": "...",
    "confidence_score": 0.85,
    "reasoning": "..."
}}"""

        try:
            response = self.llm_service.generate_from_prompt(prompt=prompt)
            cleaned = response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0]

            parsed = json.loads(cleaned)

            return ArchiMateMapping(
                element_type=parsed.get("element_type", "BusinessObject"),
                layer=parsed.get("layer", "business"),
                name=parsed.get("name", ""),
                description=parsed.get("description", ""),
                confidence_score=parsed.get("confidence_score", 0.7),
                reasoning=parsed.get("reasoning", ""),
            )

        except Exception as e:
            logger.error(f"Error mapping to ArchiMate: {e}")
            return ArchiMateMapping(
                element_type="BusinessObject",
                layer="business",
                name=str(entity),
                description="",
                confidence_score=0.5,
                reasoning="Default mapping due to error",
            )

    async def suggest_relationships(
        self, source_element: ArchiMateElement, target_element: ArchiMateElement
    ) -> List[RelationshipSuggestion]:
        """Suggest valid ArchiMate relationships between elements."""
        prompt = f"""Suggest valid ArchiMate 3.2 relationships between these elements.

SOURCE:
Type: {source_element.type}
Layer: {source_element.layer}
Name: {source_element.name}

TARGET:
Type: {target_element.type}
Layer: {target_element.layer}
Name: {target_element.name}

VALID RELATIONSHIP TYPES:
{', '.join(ArchiMateRelationshipType.ALL)}

RESPOND WITH JSON:
{{
    "relationships": [
        {{
            "relationship_type": "serving",
            "confidence_score": 0.85,
            "reasoning": "..."
        }}
    ]
}}"""

        try:
            response = self.llm_service.generate_from_prompt(prompt=prompt)
            cleaned = response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0]

            parsed = json.loads(cleaned)
            suggestions = []

            for rel in parsed.get("relationships", []):
                suggestions.append(
                    RelationshipSuggestion(
                        source_id=source_element.id,
                        target_id=target_element.id,
                        relationship_type=rel.get("relationship_type", "association"),
                        confidence_score=rel.get("confidence_score", 0.7),
                        reasoning=rel.get("reasoning", ""),
                    )
                )

            return suggestions

        except Exception as e:
            logger.error(f"Error suggesting relationships: {e}")
            return []

    async def validate_mapping(self, mapping: ArchiMateMapping) -> ValidationResult:
        """Validate mapping against ArchiMate 3.2 metamodel."""
        errors = []
        warnings = []
        suggestions = []

        # Check if element type is valid
        if not ArchiMateElementTypes.is_valid_element_type(mapping.element_type):
            errors.append(f"Invalid element type: {mapping.element_type}")

        # Check if layer is valid
        if mapping.layer not in ArchiMateLayer.ALL:
            errors.append(f"Invalid layer: {mapping.layer}")

        # Check element type matches layer
        element_def = ArchiMateElementTypes.get_element_type(mapping.element_type)
        if element_def and element_def.layer != mapping.layer:
            warnings.append(
                f"Element type '{mapping.element_type}' typically belongs to "
                f"'{element_def.layer}' layer, not '{mapping.layer}'"
            )

        # Provide suggestions for low confidence
        if mapping.confidence_score < 0.7:
            suggestions.append("Consider reviewing this mapping - confidence is below 70%")

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, suggestions=suggestions
        )

    async def generate_viewpoint(
        self, viewpoint_type: str, element_ids: List[int]
    ) -> Dict[str, Any]:
        """Generate ArchiMate viewpoint from elements."""
        elements = ArchiMateElement.query.filter(ArchiMateElement.id.in_(element_ids)).all()

        if not elements:
            return {"error": "No elements found"}

        element_data = [
            {"id": e.id, "type": e.type, "layer": e.layer, "name": e.name} for e in elements
        ]

        prompt = f"""Create an ArchiMate {viewpoint_type} viewpoint from these elements.

ELEMENTS:
{json.dumps(element_data, indent=2)}

Suggest:
1. Which elements to include
2. How to arrange them visually
3. Key relationships to highlight

RESPOND WITH JSON:
{{
    "viewpoint_name": "...",
    "viewpoint_type": "{viewpoint_type}",
    "included_elements": [list of element IDs],
    "layout_suggestions": "...",
    "key_relationships": ["relationship descriptions"]
}}"""

        try:
            response = self.llm_service.generate_from_prompt(prompt=prompt)
            cleaned = response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0]

            return json.loads(cleaned)

        except Exception as e:
            logger.error(f"Error generating viewpoint: {e}")
            return {
                "viewpoint_name": f"{viewpoint_type} Viewpoint",
                "viewpoint_type": viewpoint_type,
                "included_elements": element_ids,
                "error": str(e),
            }

    def run_sync(self, entity: Any, entity_type: str) -> Dict[str, Any]:
        """Synchronous wrapper for map_to_archimate."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        mapping = loop.run_until_complete(self.map_to_archimate(entity, entity_type))
        return {
            "element_type": mapping.element_type,
            "layer": mapping.layer,
            "name": mapping.name,
            "description": mapping.description,
            "confidence_score": mapping.confidence_score,
            "reasoning": mapping.reasoning,
        }
