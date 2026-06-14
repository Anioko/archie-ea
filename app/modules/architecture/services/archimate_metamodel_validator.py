"""
-> app.modules.architecture.services.archimate_service

ArchiMate Metamodel Validator
Validates ArchiMate models against 3.2 metamodel rules
"""

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


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

    # ArchiMate 3.2 relationship rules (source -> target constraints)
    RELATIONSHIP_RULES = {
        "Association": {
            "description": "Models unspecified relationship",
            "allowed_sources": ["*"],
            "allowed_targets": ["*"],
        },
        "Access": {
            "description": "Models data/object access",
            "allowed_sources": [
                "BusinessProcess",
                "BusinessFunction",
                "BusinessInteraction",
                "ApplicationComponent",
                "ApplicationFunction",
                "ApplicationProcess",
                "ApplicationInteraction",
            ],
            "allowed_targets": ["BusinessObject", "DataObject", "Representation"],
        },
        "Aggregation": {
            "description": "Groups elements of same type",
            "allowed_sources": ["*"],
            "allowed_targets": ["*"],
            "constraint": "same_type",
        },
        "Assignment": {
            "description": "Allocates responsibility or resources",
            "allowed_sources": [
                "BusinessActor",
                "BusinessRole",
                "ApplicationComponent",
                "Node",
                "Device",
            ],
            "allowed_targets": [
                "BusinessProcess",
                "BusinessFunction",
                "ApplicationFunction",
                "ApplicationService",
                "TechnologyFunction",
                "TechnologyService",
            ],
        },
        "Composition": {
            "description": "Part-of relationship",
            "allowed_sources": ["*"],
            "allowed_targets": ["*"],
            "constraint": "hierarchical",
        },
        "Flow": {
            "description": "Transfer of information or value",
            "allowed_sources": [
                "BusinessProcess",
                "BusinessFunction",
                "ApplicationFunction",
                "ApplicationProcess",
            ],
            "allowed_targets": [
                "BusinessProcess",
                "BusinessFunction",
                "ApplicationFunction",
                "ApplicationProcess",
            ],
        },
        "Influence": {
            "description": "Impact or effect relationship",
            "allowed_sources": [
                "Driver",
                "Assessment",
                "Goal",
                "Outcome",
                "Principle",
                "Requirement",
                "Constraint",
            ],
            "allowed_targets": [
                "Driver",
                "Assessment",
                "Goal",
                "Outcome",
                "Principle",
                "Requirement",
                "Constraint",
                "Capability",
                "CourseOfAction",
            ],
        },
        "Realization": {
            "description": "Implementation relationship",
            "allowed_sources": [
                "BusinessProcess",
                "BusinessFunction",
                "ApplicationComponent",
                "ApplicationService",
                "Capability",
                "CourseOfAction",
            ],
            "allowed_targets": [
                "BusinessService",
                "ApplicationService",
                "TechnologyService",
                "Goal",
                "Outcome",
                "Capability",
            ],
        },
        "Serving": {
            "description": "Provides functionality to",
            "allowed_sources": [
                "ApplicationComponent",
                "ApplicationService",
                "BusinessService",
                "TechnologyService",
                "Node",
            ],
            "allowed_targets": [
                "BusinessProcess",
                "BusinessFunction",
                "ApplicationComponent",
                "ApplicationFunction",
                "BusinessActor",
                "BusinessRole",
            ],
        },
        "Specialization": {
            "description": "Is-a relationship",
            "allowed_sources": ["*"],
            "allowed_targets": ["*"],
            "constraint": "same_type",
        },
        "Triggering": {
            "description": "Temporal or causal dependency",
            "allowed_sources": [
                "BusinessProcess",
                "BusinessFunction",
                "BusinessEvent",
                "ApplicationService",
                "ApplicationFunction",
                "ApplicationProcess",
            ],
            "allowed_targets": [
                "BusinessProcess",
                "BusinessFunction",
                "BusinessEvent",
                "ApplicationService",
                "ApplicationFunction",
                "ApplicationProcess",
            ],
        },
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

            # Validate relationship type rules
            if rel_type in self.RELATIONSHIP_RULES:
                rule = self.RELATIONSHIP_RULES[rel_type]
                source_type = source_elem.get("type")
                target_type = target_elem.get("type")

                # Check source type
                allowed_sources = rule.get("allowed_sources", [])
                if "*" not in allowed_sources and source_type not in allowed_sources:
                    errors.append(
                        f"Invalid relationship: {source_name} ({source_type}) --{rel_type}--> {target_name} (source type not allowed)"
                    )

                # Check target type
                allowed_targets = rule.get("allowed_targets", [])
                if "*" not in allowed_targets and target_type not in allowed_targets:
                    errors.append(
                        f"Invalid relationship: {source_name} --{rel_type}--> {target_name} ({target_type}) (target type not allowed)"
                    )

                # Check special constraints
                constraint = rule.get("constraint")
                if constraint == "same_type" and source_type != target_type:
                    warnings.append(
                        f"Relationship {rel_type} typically connects same types: {source_name} ({source_type}) -> {target_name} ({target_type})"
                    )
            else:
                warnings.append(f"Unknown relationship type: {rel_type}")

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
