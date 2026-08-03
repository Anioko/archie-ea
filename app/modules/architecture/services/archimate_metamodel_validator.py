"""
-> app.modules.architecture.services.archimate_service

ArchiMate Metamodel Validator
Validates ArchiMate models against 3.2 metamodel rules
"""

import logging
from typing import Any, Dict, List, Tuple

from app.config.archimate_relationship_matrix import (
    RELATIONSHIP_TYPES,
    VALID_RELATIONSHIPS,
    get_valid_relationships,
    is_valid_relationship,
)

logger = logging.getLogger(__name__)

# Element types the matrix can actually adjudicate. Types outside this set
# (Junction, Grouping, Location) are reported as unvalidatable rather than
# invalid — absence of a rule is not evidence of a violation.
_MATRIX_ELEMENT_TYPES = {t for pair in VALID_RELATIONSHIPS for t in pair}


class ArchiMateMetamodelValidator:
    """Validate ArchiMate models against 3.2 metamodel specification."""

    # ArchiMate 3.2 layer constraints
    LAYER_CONSTRAINTS = {
        "motivation": [
            "Stakeholder",
            "Driver",
            "Assessment",
            "Goal",
            "Outcome",
            "Principle",
            "Requirement",
            "Constraint",
            "Meaning",
            "Value",
        ],
        "strategy": ["Resource", "Capability", "ValueStream", "CourseOfAction"],
        "business": [
            "BusinessActor",
            "BusinessRole",
            "BusinessCollaboration",
            "BusinessInterface",
            "BusinessProcess",
            "BusinessFunction",
            "BusinessInteraction",
            "BusinessEvent",
            "BusinessService",
            "BusinessObject",
            "Contract",
            "Representation",
            "Product",
        ],
        "application": [
            "ApplicationComponent",
            "ApplicationCollaboration",
            "ApplicationInterface",
            "ApplicationFunction",
            "ApplicationInteraction",
            "ApplicationProcess",
            "ApplicationEvent",
            "ApplicationService",
            "DataObject",
        ],
        "technology": [
            "Node",
            "Device",
            "SystemSoftware",
            "TechnologyCollaboration",
            "TechnologyInterface",
            "Path",
            "CommunicationNetwork",
            "TechnologyFunction",
            "TechnologyProcess",
            "TechnologyInteraction",
            "TechnologyEvent",
            "TechnologyService",
            "Artifact",
        ],
        "physical": ["Equipment", "Facility", "DistributionNetwork", "Material"],
        "implementation": ["WorkPackage", "Deliverable", "ImplementationEvent", "Plateau", "Gap"],
    }

    def validate_model(self, elements: List[Dict], relationships: List[Dict]) -> Dict[str, Any]:
        """Comprehensive model validation."""
        try:
            errors = []
            warnings = []

            # Validate elements
            element_errors, element_warnings = self._validate_elements(elements)
            errors.extend(element_errors)
            warnings.extend(element_warnings)

            # Validate relationships
            rel_errors, rel_warnings = self._validate_relationships(relationships, elements)
            errors.extend(rel_errors)
            warnings.extend(rel_warnings)

            # Validate semantic consistency
            semantic_warnings = self._validate_semantic_consistency(elements, relationships)
            warnings.extend(semantic_warnings)

            # Calculate quality score
            score = self._calculate_quality_score(elements, relationships, errors, warnings)

            return {
                "valid": len(errors) == 0,
                "score": score,
                "errors": errors,
                "warnings": warnings,
                "element_count": len(elements),
                "relationship_count": len(relationships),
                "compliance_level": self._get_compliance_level(score),
            }

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {
                "valid": False,
                "score": 0,
                "errors": [f"Validation failed: {str(e)}"],
                "warnings": [],
                "element_count": 0,
                "relationship_count": 0,
                "compliance_level": "error",
            }

    def _validate_elements(self, elements: List[Dict]) -> Tuple[List[str], List[str]]:
        """Validate element layer constraints."""
        errors = []
        warnings = []

        for elem in elements:
            elem_type = elem.get("type")
            elem_layer = elem.get("layer", "").lower()
            elem_name = elem.get("name", "Unknown")

            if not elem_type:
                errors.append(f"Element '{elem_name}' missing type")
                continue

            if not elem_layer:
                warnings.append(f"Element '{elem_name}' missing layer")
                continue

            # Check if element type is valid for its layer
            if elem_layer in self.LAYER_CONSTRAINTS:
                valid_types = self.LAYER_CONSTRAINTS[elem_layer]
                if elem_type not in valid_types:
                    errors.append(
                        f"Element '{elem_name}' type '{elem_type}' not allowed in layer '{elem_layer}'"
                    )
            else:
                warnings.append(f"Element '{elem_name}' has unknown layer '{elem_layer}'")

        return errors, warnings

    def _validate_relationships(
        self, relationships: List[Dict], elements: List[Dict]
    ) -> Tuple[List[str], List[str]]:
        """Validate relationship type constraints."""
        errors = []
        warnings = []

        # Build element lookup
        element_map = {elem.get("name"): elem for elem in elements if elem.get("name")}

        for rel in relationships:
            rel_type = rel.get("type")
            source_name = rel.get("source")
            target_name = rel.get("target")

            if not rel_type:
                errors.append(f"Relationship missing type: {source_name} -> {target_name}")
                continue

            if not source_name or not target_name:
                errors.append(f"Relationship missing source or target")
                continue

            # Check if source and target elements exist
            source_elem = element_map.get(source_name)
            target_elem = element_map.get(target_name)

            if not source_elem:
                warnings.append(f"Relationship source '{source_name}' not found in elements")
                continue

            if not target_elem:
                warnings.append(f"Relationship target '{target_name}' not found in elements")
                continue

            source_type = source_elem.get("type")
            target_type = target_elem.get("type")

            if rel_type.lower() not in RELATIONSHIP_TYPES:
                warnings.append(f"Unknown relationship type: {rel_type}")
                continue

            # A pair the matrix has no opinion on cannot be judged. Junction,
            # Grouping and Location are absent from it, and treating "no rule"
            # as "forbidden" would reject correct models built from them.
            if source_type not in _MATRIX_ELEMENT_TYPES:
                warnings.append(
                    f"Cannot validate {source_name} --{rel_type}--> {target_name}: "
                    f"source type '{source_type}' is not in the ArchiMate relationship matrix"
                )
                continue
            if target_type not in _MATRIX_ELEMENT_TYPES:
                warnings.append(
                    f"Cannot validate {source_name} --{rel_type}--> {target_name}: "
                    f"target type '{target_type}' is not in the ArchiMate relationship matrix"
                )
                continue

            if not is_valid_relationship(source_type, target_type, rel_type):
                permitted = get_valid_relationships(source_type, target_type)
                hint = (
                    f" permitted between these types: {', '.join(sorted(permitted))}"
                    if permitted
                    else " no relationship is permitted between these types"
                )
                errors.append(
                    f"Invalid relationship: {source_name} ({source_type}) "
                    f"--{rel_type}--> {target_name} ({target_type}).{hint}"
                )

        return errors, warnings

    def _validate_semantic_consistency(
        self, elements: List[Dict], relationships: List[Dict]
    ) -> List[str]:
        """Check for semantic issues."""
        warnings = []

        # Check for orphaned elements (no relationships)
        element_names = {elem.get("name") for elem in elements if elem.get("name")}
        connected_elements = set()

        for rel in relationships:
            connected_elements.add(rel.get("source"))
            connected_elements.add(rel.get("target"))

        orphaned = element_names - connected_elements
        if orphaned:
            warnings.append(f"Found {len(orphaned)} orphaned elements with no relationships")

        # Check for naming inconsistencies
        name_variations = {}
        for elem in elements:
            name = elem.get("name", "")
            base_name = name.lower().replace(" ", "").replace("-", "").replace("_", "")
            if base_name:
                if base_name not in name_variations:
                    name_variations[base_name] = []
                name_variations[base_name].append(name)

        for base, variants in name_variations.items():
            if len(variants) > 1:
                warnings.append(f"Naming inconsistency: {', '.join(variants)}")

        return warnings

    def _calculate_quality_score(
        self,
        elements: List[Dict],
        relationships: List[Dict],
        errors: List[str],
        warnings: List[str],
    ) -> int:
        """Calculate overall quality score (0 - 100)."""
        score = 100

        # Deduct for errors (critical)
        score -= len(errors) * 10

        # Deduct for warnings (minor)
        score -= len(warnings) * 2

        # Bonus for good element count
        if len(elements) >= 50:
            score += 5

        # Bonus for good relationship count
        if len(relationships) >= 80:
            score += 5

        # Bonus for good ratio (2 - 3 relationships per element)
        if elements:
            ratio = len(relationships) / len(elements)
            if 2.0 <= ratio <= 3.0:
                score += 5

        return max(0, min(100, score))

    def _get_compliance_level(self, score: int) -> str:
        """Get compliance level based on score."""
        if score >= 90:
            return "excellent"
        elif score >= 75:
            return "good"
        elif score >= 60:
            return "acceptable"
        elif score >= 40:
            return "needs_improvement"
        else:
            return "poor"
