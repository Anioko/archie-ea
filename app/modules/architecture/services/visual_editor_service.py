"""
Visual Editor Service - Plan C + Plan B Hybrid
Provides real-time AI assistance during architecture editing
"""
import json
import logging
from typing import Any, Dict, List, Optional

from app import db
from app.models import ArchiMateElement, ArchiMateRelationship, ArchitectureModel, LLMInteraction
from app.services.archimate.archimate_validator import ArchiMateValidator
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class VisualEditorService:
    """
    Real-time AI assistance for interactive architecture editing
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.validator = ArchiMateValidator()

    async def suggest_complementary_elements(
        self, architecture_id: int, new_element: Dict[str, Any], provider: str = "claude"
    ) -> Dict[str, Any]:
        """
        When user adds an element, suggest complementary elements

        Args:
            architecture_id: Architecture model ID
            new_element: Newly added element data
            provider: LLM provider ('claude' or 'openai')

        Returns:
            {
                'suggestions': List[{
                    'element_type': str,
                    'name': str,
                    'layer': str,
                    'description': str,
                    'relationship_to_new': str,
                    'rationale': str,
                    'confidence': float
                }],
                'total_tokens': int,
                'cost': float
            }
        """
        model = ArchitectureModel.query.get(architecture_id)
        if not model:
            raise ValueError(f"Architecture model {architecture_id} not found")

        # Get existing elements for context
        existing_elements = ArchiMateElement.query.filter_by(architecture_id=architecture_id).all()

        context = {
            "new_element": new_element,
            "existing_count": len(existing_elements),
            "layers": {},
        }

        # Group by layer
        for elem in existing_elements:
            layer = elem.layer or "unknown"
            if layer not in context["layers"]:
                context["layers"][layer] = []
            context["layers"][layer].append({"name": elem.name, "type": elem.element_type})

        prompt = f"""You are an ArchiMate 3.2 expert helping a user build an enterprise architecture.

USER JUST ADDED:
Element Type: {new_element.get('element_type')}
Name: {new_element.get('name')}
Layer: {new_element.get('layer')}
Description: {new_element.get('description', 'N/A')}

EXISTING ARCHITECTURE:
Total Elements: {context['existing_count']}
Layers Present: {list(context['layers'].keys())}

EXISTING ELEMENTS BY LAYER:
{json.dumps(context['layers'], indent=2)}

TASK:
Suggest 3 - 5 complementary ArchiMate elements that would logically complete this architecture based on the newly added element. For each suggestion:

1. Element type (from ArchiMate 3.2 metamodel)
2. Suggested name
3. Layer (motivation, strategy, business, application, technology, physical, implementation, migration)
4. Brief description
5. Relationship type to the new element (e.g., Realization, Serving, Flow, Aggregation)
6. Rationale for why this element is needed
7. Confidence score (0.0 - 1.0)

Focus on:
- Elements that are commonly associated with this type of element
- Filling gaps in the architecture
- Maintaining ArchiMate best practices
- Practical, implementable suggestions

Return JSON array of suggestions.
"""

        try:
            response, interaction = await self.llm_service.generate_completion(
                prompt=prompt, provider=provider, temperature=0.4, max_tokens=2000
            )

            # Parse JSON response
            try:
                # Try to extract JSON from response
                import re

                json_match = re.search(r"\[.*\]", response, re.DOTALL)
                if json_match:
                    suggestions = json.loads(json_match.group())
                else:
                    suggestions = json.loads(response)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON from LLM response: {response[:200]}")
                suggestions = []

            return {
                "suggestions": suggestions,
                "total_tokens": interaction.total_tokens if interaction else 0,
                "cost": interaction.cost if interaction else 0.0,
            }

        except Exception as e:
            logger.error(f"Error generating element suggestions: {str(e)}")
            return {"suggestions": [], "total_tokens": 0, "cost": 0.0, "error": str(e)}

    async def validate_element_realtime(
        self, element_data: Dict[str, Any], architecture_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Real-time validation of element being created/edited

        Returns:
            {
                'is_valid': bool,
                'errors': List[str],
                'warnings': List[str],
                'suggestions': List[str]
            }
        """
        validation_result = {"is_valid": True, "errors": [], "warnings": [], "suggestions": []}

        # Validate element type
        element_type = element_data.get("element_type")
        layer = element_data.get("layer")
        name = element_data.get("name", "").strip()

        if not element_type:
            validation_result["errors"].append("Element type is required")
            validation_result["is_valid"] = False

        if not name:
            validation_result["errors"].append("Element name is required")
            validation_result["is_valid"] = False

        # Validate layer matches element type
        if element_type and layer:
            valid = self.validator.validate_element_layer(element_type, layer)
            if not valid:
                validation_result["errors"].append(
                    f"Element type '{element_type}' cannot belong to layer '{layer}'"
                )
                validation_result["is_valid"] = False

        # Check for duplicate names in same architecture
        if architecture_id and name:
            existing = ArchiMateElement.query.filter_by(
                architecture_id=architecture_id, name=name
            ).first()
            if existing and existing.id != element_data.get("id"):
                validation_result["warnings"].append(
                    f"An element with name '{name}' already exists in this architecture"
                )

        # Suggestions
        if not element_data.get("description"):
            validation_result["suggestions"].append(
                "Adding a description will help others understand this element's purpose"
            )

        return validation_result

    async def validate_relationship_realtime(
        self, source_id: int, target_id: int, relationship_type: str
    ) -> Dict[str, Any]:
        """
        Real-time validation of relationship being created

        Returns:
            {
                'is_valid': bool,
                'errors': List[str],
                'warnings': List[str],
                'alternative_types': List[str]
            }
        """
        source = ArchiMateElement.query.get(source_id)
        target = ArchiMateElement.query.get(target_id)

        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "alternative_types": [],
        }

        if not source:
            validation_result["errors"].append(f"Source element {source_id} not found")
            validation_result["is_valid"] = False
            return validation_result

        if not target:
            validation_result["errors"].append(f"Target element {target_id} not found")
            validation_result["is_valid"] = False
            return validation_result

        # Validate relationship is allowed
        is_allowed = self.validator.validate_relationship(
            source.element_type, target.element_type, relationship_type
        )

        if not is_allowed:
            validation_result["errors"].append(
                f"Relationship '{relationship_type}' is not allowed between "
                f"{source.element_type} and {target.element_type}"
            )
            validation_result["is_valid"] = False

            # Suggest alternatives
            alternatives = self.validator.get_allowed_relationships(
                source.element_type, target.element_type
            )
            validation_result["alternative_types"] = alternatives

        return validation_result

    async def auto_complete_layer(
        self, architecture_id: int, layer: str, provider: str = "claude"
    ) -> Dict[str, Any]:
        """
        AI generates missing elements for a specific layer

        Example: User has Business layer complete, clicks "Auto-complete Application Layer"
        → AI generates all necessary application components, services, interfaces

        Args:
            architecture_id: Architecture model ID
            layer: Layer to complete ('application', 'technology', etc.)
            provider: LLM provider

        Returns:
            {
                'generated_elements': List[Dict],
                'generated_relationships': List[Dict],
                'rationale': str,
                'total_tokens': int,
                'cost': float
            }
        """
        model = ArchitectureModel.query.get(architecture_id)
        if not model:
            raise ValueError(f"Architecture model {architecture_id} not found")

        # Get existing elements
        existing_elements = ArchiMateElement.query.filter_by(architecture_id=architecture_id).all()

        # Get existing relationships
        existing_relationships = ArchiMateRelationship.query.filter_by(
            architecture_id=architecture_id
        ).all()

        # Group elements by layer
        elements_by_layer = {}
        for elem in existing_elements:
            elem_layer = elem.layer or "unknown"
            if elem_layer not in elements_by_layer:
                elements_by_layer[elem_layer] = []
            elements_by_layer[elem_layer].append(
                {
                    "id": elem.id,
                    "name": elem.name,
                    "type": elem.element_type,
                    "description": elem.description,
                }
            )

        # Build relationship context
        relationship_context = []
        for rel in existing_relationships:
            source = ArchiMateElement.query.get(rel.source_id)
            target = ArchiMateElement.query.get(rel.target_id)
            if source and target:
                relationship_context.append(
                    {"source": source.name, "target": target.name, "type": rel.relationship_type}
                )

        prompt = f"""You are an ArchiMate 3.2 expert. The user wants to auto-complete the {layer.upper()} layer of their architecture.

EXISTING ARCHITECTURE:
Model Name: {model.name}
Total Elements: {len(existing_elements)}

ELEMENTS BY LAYER:
{json.dumps(elements_by_layer, indent=2)}

EXISTING RELATIONSHIPS:
{json.dumps(relationship_context, indent=2)}

TASK:
Generate ArchiMate elements and relationships to complete the {layer.upper()} layer.

Consider:
1. What {layer} elements are typically needed to support the existing elements in other layers?
2. What elements are missing to make this a complete, implementable architecture?
3. Follow ArchiMate 3.2 best practices
4. Create realistic, practical elements

Return JSON with:
{{
    "generated_elements": [
        {{
            "element_type": "ApplicationComponent",
            "name": "Customer Portal",
            "layer": "application",
            "description": "Web-based customer self-service portal",
            "properties": {{}}
        }}
    ],
    "generated_relationships": [
        {{
            "source_ref": "element_name_or_id",
            "target_ref": "element_name_or_id",
            "relationship_type": "Realization"
        }}
    ],
    "rationale": "Explanation of why these elements were generated"
}}
"""

        try:
            response, interaction = await self.llm_service.generate_completion(
                prompt=prompt, provider=provider, temperature=0.3, max_tokens=4000
            )

            # Parse JSON response
            try:
                import re

                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = json.loads(response)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON from LLM response")
                result = {
                    "generated_elements": [],
                    "generated_relationships": [],
                    "rationale": "Failed to parse AI response",
                }

            result["total_tokens"] = interaction.total_tokens if interaction else 0
            result["cost"] = interaction.cost if interaction else 0.0

            return result

        except Exception as e:
            logger.error(f"Error auto-completing layer: {str(e)}")
            return {
                "generated_elements": [],
                "generated_relationships": [],
                "rationale": f"Error: {str(e)}",
                "total_tokens": 0,
                "cost": 0.0,
            }

    async def analyze_edit_impact(
        self, architecture_id: int, edit_action: Dict[str, Any], provider: str = "claude"
    ) -> Dict[str, Any]:
        """
        When user deletes or modifies an element, analyze impact on implementation plan

        Args:
            architecture_id: Architecture model ID
            edit_action: {
                'type': 'delete' | 'modify',
                'element_id': int,
                'changes': Dict (for modify)
            }

        Returns:
            {
                'affected_elements': List[Dict],
                'affected_relationships': List[Dict],
                'affected_work_packages': List[Dict],
                'recommendation': str,
                'severity': 'low' | 'medium' | 'high'
            }
        """
        element = ArchiMateElement.query.get(edit_action["element_id"])
        if not element:
            return {
                "affected_elements": [],
                "affected_relationships": [],
                "affected_work_packages": [],
                "recommendation": "Element not found",
                "severity": "low",
            }

        # Find relationships involving this element
        incoming_rels = ArchiMateRelationship.query.filter_by(
            architecture_id=architecture_id, target_id=element.id
        ).all()

        outgoing_rels = ArchiMateRelationship.query.filter_by(
            architecture_id=architecture_id, source_id=element.id
        ).all()

        # Find implementation layer elements that realize this element
        implementation_elements = ArchiMateElement.query.filter(
            ArchiMateElement.architecture_id == architecture_id,
            ArchiMateElement.layer.in_(["implementation", "migration"]),
        ).all()

        impact = {
            "affected_elements": [],
            "affected_relationships": [],
            "affected_work_packages": [],
            "recommendation": "",
            "severity": "low",
        }

        # Add affected relationships
        for rel in incoming_rels + outgoing_rels:
            impact["affected_relationships"].append(
                {"id": rel.id, "type": rel.relationship_type, "will_be_deleted": True}
            )

        # Check implementation impact
        for impl_elem in implementation_elements:
            if impl_elem.element_type == "WorkPackage":
                # Check if this work package realizes the deleted element
                realization_rels = ArchiMateRelationship.query.filter_by(
                    source_id=impl_elem.id, target_id=element.id, relationship_type="Realization"
                ).all()

                if realization_rels:
                    impact["affected_work_packages"].append(
                        {
                            "id": impl_elem.id,
                            "name": impl_elem.name,
                            "impact": "Work package will no longer have a target to realize",
                        }
                    )

        # Determine severity
        if len(impact["affected_work_packages"]) > 0:
            impact["severity"] = "high"
            impact[
                "recommendation"
            ] = f"Deleting '{element.name}' will affect {len(impact['affected_work_packages'])} work package(s). Consider updating or removing the affected work packages."
        elif len(impact["affected_relationships"]) > 5:
            impact["severity"] = "medium"
            impact[
                "recommendation"
            ] = f"Deleting '{element.name}' will remove {len(impact['affected_relationships'])} relationships. This may disconnect parts of your architecture."
        else:
            impact["severity"] = "low"
            impact[
                "recommendation"
            ] = f"Deleting '{element.name}' has minimal impact on the architecture."

        return impact
