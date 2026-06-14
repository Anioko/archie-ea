"""
Relationship Derivation Service (Phase 1.2)

Auto-generates ArchiMate relationships from APQC process context using
rule-based inference combined with semantic analysis.

Derivation Rules:
- Structural rules: BusinessFunction contains BusinessProcess
- Behavioral rules: BusinessProcess triggers BusinessEvent
- Cross-layer rules: ApplicationComponent serves BusinessProcess
- Realization rules: ApplicationFunction realizes ApplicationService

Confidence Scoring:
- Rule type (structural = high, inferred = lower)
- Semantic similarity of element names
- APQC category alignment
"""

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple

from app import db
from app.models.apqc_process import APQCProcess
from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class DerivedRelationship:
    """
    Represents a derived ArchiMate relationship with metadata.

    Attributes:
        source_element_id: ID of the source ArchiMate element
        target_element_id: ID of the target ArchiMate element
        relationship_type: ArchiMate relationship type (e.g., 'Composition', 'Serving')
        confidence: Confidence score from 0.0 to 1.0
        derivation_rule: Name of the rule that generated this relationship
        apqc_context: APQC process code that prompted this derivation
        requires_review: True if confidence is below threshold
    """

    source_element_id: int
    target_element_id: int
    relationship_type: str
    confidence: float
    derivation_rule: str
    apqc_context: str
    requires_review: bool = field(default=True)

    # Optional metadata
    source_element_name: str = field(default="")
    target_element_name: str = field(default="")
    rationale: str = field(default="")

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "source_element_id": self.source_element_id,
            "target_element_id": self.target_element_id,
            "relationship_type": self.relationship_type,
            "confidence": round(self.confidence, 3),
            "derivation_rule": self.derivation_rule,
            "apqc_context": self.apqc_context,
            "requires_review": self.requires_review,
            "source_element_name": self.source_element_name,
            "target_element_name": self.target_element_name,
            "rationale": self.rationale,
        }


# =============================================================================
# Derivation Rule Definitions
# =============================================================================


@dataclass
class DerivationRule:
    """Definition of a relationship derivation rule."""

    name: str
    source_types: List[str]
    target_types: List[str]
    relationship_type: str
    base_confidence: float
    category: str  # structural, behavioral, cross_layer, realization
    description: str
    apqc_categories: List[str] = field(default_factory=list)  # APQC categories this rule applies to


# =============================================================================
# Relationship Derivation Service
# =============================================================================


class RelationshipDerivationService:
    """
    Service to derive ArchiMate relationships from APQC process context.
    Uses rule-based inference combined with semantic analysis.

    Features:
    - Process-context aware relationship derivation
    - Cross-layer relationship inference
    - APQC-specific relationship templates
    - Confidence scoring with multiple factors
    - Review flagging for low-confidence relationships
    """

    # Confidence threshold for requiring review
    REVIEW_THRESHOLD = 0.7

    # Confidence weights for scoring
    CONFIDENCE_WEIGHTS = {
        "rule_base": 0.35,  # Base confidence from rule type
        "semantic_similarity": 0.25,  # Name/description similarity
        "apqc_alignment": 0.20,  # APQC category match
        "layer_consistency": 0.20,  # Layer transition validity
    }

    def __init__(self):
        """Initialize the service with derivation rules."""
        self.derivation_rules = self._initialize_rules()
        self.apqc_category_mappings = self._initialize_apqc_mappings()
        logger.info(
            "RelationshipDerivationService initialized with %d rules", len(self.derivation_rules)
        )

    # =========================================================================
    # Main Derivation Methods
    # =========================================================================

    def derive_relationships_for_process(
        self, apqc_process_id: int, existing_elements: List[ArchiMateElement]
    ) -> List[DerivedRelationship]:
        """
        Derive relationships for a single APQC process.

        Analyzes the APQC process context and generates appropriate ArchiMate
        relationships between the provided elements based on derivation rules.

        Args:
            apqc_process_id: ID of the APQC process providing context
            existing_elements: List of ArchiMate elements to connect

        Returns:
            List of derived relationships with confidence scores
        """
        # Fetch APQC process
        apqc_process = db.session.get(APQCProcess, apqc_process_id)
        if not apqc_process:
            logger.warning("APQC process %d not found", apqc_process_id)
            return []

        apqc_context = apqc_process.process_code
        apqc_category = self._determine_apqc_category(apqc_process)

        logger.info("Deriving relationships for APQC process %s (%s)", apqc_context, apqc_category)

        derived_relationships = []

        # Group elements by type for efficient lookup
        elements_by_type = self._group_elements_by_type(existing_elements)

        # Apply applicable rules based on APQC category
        applicable_rules = self._get_rules_for_category(apqc_category)

        for rule in applicable_rules:
            # Find source and target candidates
            source_candidates = self._find_candidates(elements_by_type, rule.source_types)
            target_candidates = self._find_candidates(elements_by_type, rule.target_types)

            # Generate relationships for each valid pair
            for source in source_candidates:
                for target in target_candidates:
                    if source.id == target.id:
                        continue

                    # Check if relationship already exists
                    if self._relationship_exists(source.id, target.id, rule.relationship_type):
                        continue

                    # Create derived relationship with confidence scoring
                    relationship = self._create_derived_relationship(
                        source=source,
                        target=target,
                        rule=rule,
                        apqc_context=apqc_context,
                        apqc_category=apqc_category,
                    )

                    if relationship:
                        derived_relationships.append(relationship)

        # Sort by confidence (highest first)
        derived_relationships.sort(key=lambda r: r.confidence, reverse=True)

        logger.info(
            "Derived %d relationships for APQC process %s", len(derived_relationships), apqc_context
        )

        return derived_relationships

    def derive_cross_layer_relationships(
        self,
        business_elements: List[ArchiMateElement],
        application_elements: List[ArchiMateElement],
        technology_elements: List[ArchiMateElement],
    ) -> List[DerivedRelationship]:
        """
        Derive relationships across ArchiMate layers.

        Analyzes elements from Business, Application, and Technology layers
        to infer cross-layer relationships like serving, realization, etc.

        Args:
            business_elements: Elements from the Business layer
            application_elements: Elements from the Application layer
            technology_elements: Elements from the Technology layer

        Returns:
            List of derived cross-layer relationships
        """
        logger.info(
            "Deriving cross-layer relationships: %d business, %d application, %d technology",
            len(business_elements),
            len(application_elements),
            len(technology_elements),
        )

        derived_relationships = []

        # Get cross-layer rules
        cross_layer_rules = [r for r in self.derivation_rules if r.category == "cross_layer"]

        # Business <-> Application layer connections
        for rule in cross_layer_rules:
            source_layer, target_layer = self._determine_layer_pair(rule)

            if source_layer == "application" and target_layer == "business":
                sources = application_elements
                targets = business_elements
            elif source_layer == "technology" and target_layer == "application":
                sources = technology_elements
                targets = application_elements
            elif source_layer == "business" and target_layer == "business":
                sources = targets = business_elements
            else:
                continue

            # Filter by element types
            source_candidates = [e for e in sources if e.type in rule.source_types]
            target_candidates = [e for e in targets if e.type in rule.target_types]

            for source in source_candidates:
                for target in target_candidates:
                    if source.id == target.id:
                        continue

                    if self._relationship_exists(source.id, target.id, rule.relationship_type):
                        continue

                    # Calculate semantic similarity for cross-layer
                    similarity = self._calculate_semantic_similarity(source, target)

                    # Only create relationship if there's meaningful similarity
                    if similarity >= 0.3:
                        confidence = self._calculate_cross_layer_confidence(
                            rule=rule, source=source, target=target, semantic_similarity=similarity
                        )

                        relationship = DerivedRelationship(
                            source_element_id=source.id,
                            target_element_id=target.id,
                            relationship_type=rule.relationship_type,
                            confidence=confidence,
                            derivation_rule=rule.name,
                            apqc_context="cross_layer",
                            requires_review=confidence < self.REVIEW_THRESHOLD,
                            source_element_name=source.name,
                            target_element_name=target.name,
                            rationale=f"Cross-layer relationship: {source.type} -> {target.type}",
                        )
                        derived_relationships.append(relationship)

        # Sort by confidence
        derived_relationships.sort(key=lambda r: r.confidence, reverse=True)

        logger.info("Derived %d cross-layer relationships", len(derived_relationships))

        return derived_relationships

    def apply_relationship_templates(
        self,
        apqc_category: str,
        source_element: ArchiMateElement,
        candidate_targets: List[ArchiMateElement],
    ) -> List[DerivedRelationship]:
        """
        Apply APQC-specific relationship templates.

        Uses pre-defined templates for specific APQC categories to generate
        relationships that are commonly found in those process areas.

        Args:
            apqc_category: APQC category (e.g., "1.0 Develop Vision and Strategy")
            source_element: The source element to create relationships from
            candidate_targets: Potential target elements

        Returns:
            List of derived relationships based on templates
        """
        logger.info(
            "Applying templates for APQC category '%s' from source '%s'",
            apqc_category,
            source_element.name,
        )

        derived_relationships = []

        # Get templates for this category
        templates = self._get_templates_for_category(apqc_category)

        for template in templates:
            # Check if source element matches template source type
            if source_element.type not in template["source_types"]:
                continue

            # Find matching targets
            matching_targets = [
                t
                for t in candidate_targets
                if t.type in template["target_types"] and t.id != source_element.id
            ]

            for target in matching_targets:
                # Check if relationship exists
                if self._relationship_exists(
                    source_element.id, target.id, template["relationship_type"]
                ):
                    continue

                # Calculate confidence using template-specific scoring
                confidence = self._calculate_template_confidence(
                    template=template,
                    source=source_element,
                    target=target,
                    apqc_category=apqc_category,
                )

                relationship = DerivedRelationship(
                    source_element_id=source_element.id,
                    target_element_id=target.id,
                    relationship_type=template["relationship_type"],
                    confidence=confidence,
                    derivation_rule=f"template:{template['name']}",
                    apqc_context=apqc_category,
                    requires_review=confidence < self.REVIEW_THRESHOLD,
                    source_element_name=source_element.name,
                    target_element_name=target.name,
                    rationale=template.get("description", ""),
                )
                derived_relationships.append(relationship)

        # Sort by confidence
        derived_relationships.sort(key=lambda r: r.confidence, reverse=True)

        logger.info("Applied %d template relationships", len(derived_relationships))

        return derived_relationships

    def calculate_relationship_confidence(self, relationship: DerivedRelationship) -> float:
        """
        Calculate confidence score (0.0 - 1.0) for derived relationship.

        Uses multiple factors:
        - Rule type (structural = high, inferred = lower)
        - Semantic similarity of element names
        - APQC category alignment
        - Layer transition validity

        Args:
            relationship: The derived relationship to score

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Get source and target elements
        source = db.session.get(ArchiMateElement, relationship.source_element_id)
        target = db.session.get(ArchiMateElement, relationship.target_element_id)

        if not source or not target:
            return 0.0

        # Find the derivation rule
        rule = self._find_rule_by_name(relationship.derivation_rule)

        # Calculate individual factors
        factors = {}

        # Factor 1: Rule base confidence
        if rule:
            factors["rule_base"] = rule.base_confidence
        else:
            factors["rule_base"] = 0.5  # Default for unknown rules

        # Factor 2: Semantic similarity
        factors["semantic_similarity"] = self._calculate_semantic_similarity(source, target)

        # Factor 3: APQC alignment
        factors["apqc_alignment"] = self._calculate_apqc_alignment(
            relationship.apqc_context, source, target
        )

        # Factor 4: Layer consistency
        factors["layer_consistency"] = self._calculate_layer_consistency(
            source, target, relationship.relationship_type
        )

        # Calculate weighted score
        confidence = sum(
            factors[factor] * weight
            for factor, weight in self.CONFIDENCE_WEIGHTS.items()
            if factor in factors
        )

        # Ensure in valid range
        confidence = max(0.0, min(1.0, confidence))

        logger.debug(
            "Confidence for %s->%s (%s): %.3f (factors: %s)",
            source.name,
            target.name,
            relationship.relationship_type,
            confidence,
            factors,
        )

        return confidence

    # =========================================================================
    # Rule Initialization
    # =========================================================================

    def _initialize_rules(self) -> List[DerivationRule]:
        """Initialize the derivation rules for relationship inference."""
        return [
            # Structural Rules (High confidence)
            DerivationRule(
                name="business_function_contains_process",
                source_types=["BusinessFunction"],
                target_types=["BusinessProcess"],
                relationship_type="Composition",
                base_confidence=0.9,
                category="structural",
                description="BusinessFunction contains BusinessProcess",
                apqc_categories=["all"],
            ),
            DerivationRule(
                name="application_component_contains_function",
                source_types=["ApplicationComponent"],
                target_types=["ApplicationFunction"],
                relationship_type="Composition",
                base_confidence=0.9,
                category="structural",
                description="ApplicationComponent contains ApplicationFunction",
                apqc_categories=["all"],
            ),
            DerivationRule(
                name="application_component_contains_service",
                source_types=["ApplicationComponent"],
                target_types=["ApplicationService"],
                relationship_type="Composition",
                base_confidence=0.85,
                category="structural",
                description="ApplicationComponent contains ApplicationService",
                apqc_categories=["all"],
            ),
            DerivationRule(
                name="node_contains_device",
                source_types=["Node"],
                target_types=["Device"],
                relationship_type="Composition",
                base_confidence=0.9,
                category="structural",
                description="Node contains Device",
                apqc_categories=["all"],
            ),
            # Behavioral Rules (Medium-High confidence)
            DerivationRule(
                name="process_triggers_event",
                source_types=["BusinessProcess"],
                target_types=["BusinessEvent"],
                relationship_type="Triggering",
                base_confidence=0.75,
                category="behavioral",
                description="BusinessProcess triggers BusinessEvent",
                apqc_categories=["all"],
            ),
            DerivationRule(
                name="event_triggers_process",
                source_types=["BusinessEvent"],
                target_types=["BusinessProcess"],
                relationship_type="Triggering",
                base_confidence=0.75,
                category="behavioral",
                description="BusinessEvent triggers BusinessProcess",
                apqc_categories=["all"],
            ),
            DerivationRule(
                name="process_flow",
                source_types=["BusinessProcess"],
                target_types=["BusinessProcess"],
                relationship_type="Flow",
                base_confidence=0.7,
                category="behavioral",
                description="BusinessProcess flows to BusinessProcess",
                apqc_categories=["all"],
            ),
            # Cross-Layer Rules (Medium confidence)
            DerivationRule(
                name="app_component_serves_business_process",
                source_types=["ApplicationComponent"],
                target_types=["BusinessProcess"],
                relationship_type="Serving",
                base_confidence=0.8,
                category="cross_layer",
                description="ApplicationComponent serves BusinessProcess",
                apqc_categories=["all"],
            ),
            DerivationRule(
                name="app_service_serves_business_service",
                source_types=["ApplicationService"],
                target_types=["BusinessService"],
                relationship_type="Serving",
                base_confidence=0.8,
                category="cross_layer",
                description="ApplicationService serves BusinessService",
                apqc_categories=["all"],
            ),
            DerivationRule(
                name="technology_service_serves_app_component",
                source_types=["TechnologyService"],
                target_types=["ApplicationComponent"],
                relationship_type="Serving",
                base_confidence=0.75,
                category="cross_layer",
                description="TechnologyService serves ApplicationComponent",
                apqc_categories=["all"],
            ),
            DerivationRule(
                name="node_assigned_to_app_component",
                source_types=["Node"],
                target_types=["ApplicationComponent"],
                relationship_type="Assignment",
                base_confidence=0.8,
                category="cross_layer",
                description="Node is assigned to ApplicationComponent",
                apqc_categories=["all"],
            ),
            # Realization Rules (Medium-High confidence)
            DerivationRule(
                name="app_function_realizes_service",
                source_types=["ApplicationFunction"],
                target_types=["ApplicationService"],
                relationship_type="Realization",
                base_confidence=0.85,
                category="realization",
                description="ApplicationFunction realizes ApplicationService",
                apqc_categories=["all"],
            ),
            DerivationRule(
                name="app_component_realizes_business_process",
                source_types=["ApplicationComponent"],
                target_types=["BusinessProcess"],
                relationship_type="Realization",
                base_confidence=0.75,
                category="realization",
                description="ApplicationComponent realizes BusinessProcess",
                apqc_categories=["all"],
            ),
            DerivationRule(
                name="tech_service_realizes_app_service",
                source_types=["TechnologyService"],
                target_types=["ApplicationService"],
                relationship_type="Realization",
                base_confidence=0.75,
                category="realization",
                description="TechnologyService realizes ApplicationService",
                apqc_categories=["all"],
            ),
            DerivationRule(
                name="business_process_realizes_capability",
                source_types=["BusinessProcess"],
                target_types=["BusinessCapability", "Capability"],
                relationship_type="Realization",
                base_confidence=0.8,
                category="realization",
                description="BusinessProcess realizes BusinessCapability",
                apqc_categories=["all"],
            ),
            # Data Access Rules
            DerivationRule(
                name="app_component_accesses_data",
                source_types=["ApplicationComponent"],
                target_types=["DataObject"],
                relationship_type="Access",
                base_confidence=0.7,
                category="structural",
                description="ApplicationComponent accesses DataObject",
                apqc_categories=["all"],
            ),
            DerivationRule(
                name="app_function_accesses_data",
                source_types=["ApplicationFunction"],
                target_types=["DataObject"],
                relationship_type="Access",
                base_confidence=0.7,
                category="structural",
                description="ApplicationFunction accesses DataObject",
                apqc_categories=["all"],
            ),
        ]

    def _initialize_apqc_mappings(self) -> Dict[str, List[str]]:
        """Initialize APQC category to ArchiMate element type mappings."""
        return {
            # Category 1: Develop Vision and Strategy
            "1": {
                "primary_types": ["BusinessCapability", "BusinessProcess", "Goal", "Driver"],
                "common_relationships": ["Realization", "Influence", "Association"],
            },
            # Category 2: Develop and Manage Products and Services
            "2": {
                "primary_types": ["BusinessProcess", "Product", "BusinessService"],
                "common_relationships": ["Composition", "Realization", "Serving"],
            },
            # Category 3: Market and Sell Products and Services
            "3": {
                "primary_types": ["BusinessProcess", "BusinessService", "BusinessActor"],
                "common_relationships": ["Serving", "Flow", "Triggering"],
            },
            # Category 4: Deliver Products and Services
            "4": {
                "primary_types": ["BusinessProcess", "ApplicationComponent", "DataObject"],
                "common_relationships": ["Serving", "Realization", "Access"],
            },
            # Category 5: Manage Customer Service
            "5": {
                "primary_types": ["BusinessProcess", "BusinessService", "ApplicationService"],
                "common_relationships": ["Serving", "Triggering", "Realization"],
            },
            # Category 6 - 8: Enterprise Management
            "6": {
                "primary_types": ["BusinessCapability", "BusinessProcess", "BusinessActor"],
                "common_relationships": ["Assignment", "Realization", "Composition"],
            },
            "7": {
                "primary_types": ["ApplicationComponent", "TechnologyService", "Node"],
                "common_relationships": ["Serving", "Assignment", "Realization"],
            },
            "8": {
                "primary_types": ["BusinessCapability", "BusinessProcess", "BusinessActor"],
                "common_relationships": ["Assignment", "Realization", "Serving"],
            },
        }

    def _get_templates_for_category(self, apqc_category: str) -> List[Dict]:
        """Get relationship templates for a specific APQC category."""
        # Extract category number from the full category string
        category_num = self._extract_category_number(apqc_category)

        # Base templates applicable to all categories
        base_templates = [
            {
                "name": "capability_process_realization",
                "source_types": ["BusinessProcess"],
                "target_types": ["BusinessCapability", "Capability"],
                "relationship_type": "Realization",
                "description": "Process realizes capability",
                "base_confidence": 0.8,
            },
            {
                "name": "application_process_serving",
                "source_types": ["ApplicationComponent"],
                "target_types": ["BusinessProcess"],
                "relationship_type": "Serving",
                "description": "Application serves process",
                "base_confidence": 0.75,
            },
        ]

        # Category-specific templates
        category_templates = {
            "1": [  # Vision and Strategy
                {
                    "name": "goal_driver_association",
                    "source_types": ["Goal"],
                    "target_types": ["Driver"],
                    "relationship_type": "Association",
                    "description": "Goal associated with Driver",
                    "base_confidence": 0.85,
                },
                {
                    "name": "capability_goal_realization",
                    "source_types": ["BusinessCapability"],
                    "target_types": ["Goal"],
                    "relationship_type": "Realization",
                    "description": "Capability realizes Goal",
                    "base_confidence": 0.8,
                },
            ],
            "4": [  # Deliver Products and Services
                {
                    "name": "process_data_access",
                    "source_types": ["BusinessProcess"],
                    "target_types": ["DataObject"],
                    "relationship_type": "Access",
                    "description": "Process accesses data",
                    "base_confidence": 0.75,
                }
            ],
            "7": [  # IT Management
                {
                    "name": "node_tech_service_assignment",
                    "source_types": ["Node"],
                    "target_types": ["TechnologyService"],
                    "relationship_type": "Assignment",
                    "description": "Node assigned to technology service",
                    "base_confidence": 0.85,
                }
            ],
        }

        templates = base_templates.copy()
        if category_num in category_templates:
            templates.extend(category_templates[category_num])

        return templates

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _group_elements_by_type(
        self, elements: List[ArchiMateElement]
    ) -> Dict[str, List[ArchiMateElement]]:
        """Group elements by their ArchiMate type."""
        grouped = {}
        for element in elements:
            element_type = element.type or "Unknown"
            if element_type not in grouped:
                grouped[element_type] = []
            grouped[element_type].append(element)
        return grouped

    def _find_candidates(
        self, elements_by_type: Dict[str, List[ArchiMateElement]], types: List[str]
    ) -> List[ArchiMateElement]:
        """Find candidate elements matching any of the specified types."""
        candidates = []
        for element_type in types:
            if element_type in elements_by_type:
                candidates.extend(elements_by_type[element_type])
        return candidates

    def _get_rules_for_category(self, apqc_category: str) -> List[DerivationRule]:
        """Get derivation rules applicable to an APQC category."""
        applicable = []
        for rule in self.derivation_rules:
            if "all" in rule.apqc_categories or apqc_category in rule.apqc_categories:
                applicable.append(rule)
        return applicable

    def _determine_apqc_category(self, apqc_process: APQCProcess) -> str:
        """Determine the APQC category from a process."""
        if apqc_process.category_level_1:
            return apqc_process.category_level_1
        if apqc_process.process_code:
            # Extract first segment as category
            return apqc_process.process_code.split(".")[0]
        return "unknown"

    def _extract_category_number(self, apqc_category: str) -> str:
        """Extract category number from APQC category string."""
        if not apqc_category:
            return ""
        # Extract leading digits
        match = re.match(r"^(\d+)", apqc_category)
        if match:
            return match.group(1)
        return ""

    def _relationship_exists(self, source_id: int, target_id: int, rel_type: str) -> bool:
        """Check if a relationship already exists."""
        existing = ArchiMateRelationship.query.filter_by(
            source_id=source_id, target_id=target_id, type=rel_type
        ).first()
        return existing is not None

    def _create_derived_relationship(
        self,
        source: ArchiMateElement,
        target: ArchiMateElement,
        rule: DerivationRule,
        apqc_context: str,
        apqc_category: str,
    ) -> Optional[DerivedRelationship]:
        """Create a derived relationship with confidence scoring."""
        # Calculate confidence
        confidence = self._calculate_full_confidence(
            rule=rule, source=source, target=target, apqc_category=apqc_category
        )

        return DerivedRelationship(
            source_element_id=source.id,
            target_element_id=target.id,
            relationship_type=rule.relationship_type,
            confidence=confidence,
            derivation_rule=rule.name,
            apqc_context=apqc_context,
            requires_review=confidence < self.REVIEW_THRESHOLD,
            source_element_name=source.name,
            target_element_name=target.name,
            rationale=rule.description,
        )

    def _find_rule_by_name(self, rule_name: str) -> Optional[DerivationRule]:
        """Find a derivation rule by its name."""
        # Handle template rules
        if rule_name.startswith("template:"):
            return None

        for rule in self.derivation_rules:
            if rule.name == rule_name:
                return rule
        return None

    def _determine_layer_pair(self, rule: DerivationRule) -> Tuple[str, str]:
        """Determine source and target layers for a rule."""
        type_to_layer = {
            "BusinessProcess": "business",
            "BusinessFunction": "business",
            "BusinessService": "business",
            "BusinessEvent": "business",
            "BusinessCapability": "business",
            "BusinessActor": "business",
            "ApplicationComponent": "application",
            "ApplicationService": "application",
            "ApplicationFunction": "application",
            "ApplicationInterface": "application",
            "DataObject": "application",
            "TechnologyService": "technology",
            "Node": "technology",
            "Device": "technology",
        }

        source_layer = (
            type_to_layer.get(rule.source_types[0], "unknown") if rule.source_types else "unknown"
        )
        target_layer = (
            type_to_layer.get(rule.target_types[0], "unknown") if rule.target_types else "unknown"
        )

        return source_layer, target_layer

    # =========================================================================
    # Confidence Calculation Methods
    # =========================================================================

    def _calculate_full_confidence(
        self,
        rule: DerivationRule,
        source: ArchiMateElement,
        target: ArchiMateElement,
        apqc_category: str,
    ) -> float:
        """Calculate full confidence score using all factors."""
        factors = {}

        # Factor 1: Rule base confidence
        factors["rule_base"] = rule.base_confidence

        # Factor 2: Semantic similarity
        factors["semantic_similarity"] = self._calculate_semantic_similarity(source, target)

        # Factor 3: APQC alignment
        factors["apqc_alignment"] = self._calculate_apqc_alignment_from_category(
            apqc_category, source, target
        )

        # Factor 4: Layer consistency
        factors["layer_consistency"] = self._calculate_layer_consistency(
            source, target, rule.relationship_type
        )

        # Calculate weighted score
        confidence = sum(
            factors[factor] * weight
            for factor, weight in self.CONFIDENCE_WEIGHTS.items()
            if factor in factors
        )

        return max(0.0, min(1.0, confidence))

    def _calculate_cross_layer_confidence(
        self,
        rule: DerivationRule,
        source: ArchiMateElement,
        target: ArchiMateElement,
        semantic_similarity: float,
    ) -> float:
        """Calculate confidence for cross-layer relationships."""
        # Base from rule
        confidence = rule.base_confidence * 0.4

        # Boost from semantic similarity
        confidence += semantic_similarity * 0.35

        # Layer transition validity
        layer_validity = self._calculate_layer_consistency(source, target, rule.relationship_type)
        confidence += layer_validity * 0.25

        return max(0.0, min(1.0, confidence))

    def _calculate_template_confidence(
        self, template: Dict, source: ArchiMateElement, target: ArchiMateElement, apqc_category: str
    ) -> float:
        """Calculate confidence for template-based relationships."""
        base_conf = template.get("base_confidence", 0.7)

        # Semantic similarity boost
        similarity = self._calculate_semantic_similarity(source, target)

        # APQC alignment
        category_num = self._extract_category_number(apqc_category)
        apqc_boost = 0.1 if category_num else 0.0

        confidence = base_conf * 0.5 + similarity * 0.35 + apqc_boost

        return max(0.0, min(1.0, confidence))

    def _calculate_semantic_similarity(
        self, source: ArchiMateElement, target: ArchiMateElement
    ) -> float:
        """Calculate semantic similarity between two elements."""
        # Name similarity
        source_name = (source.name or "").lower()
        target_name = (target.name or "").lower()
        name_similarity = SequenceMatcher(None, source_name, target_name).ratio()

        # Description similarity (if available)
        source_desc = (source.description or "").lower()
        target_desc = (target.description or "").lower()

        if source_desc and target_desc:
            desc_similarity = self._calculate_text_similarity(source_desc, target_desc)
            return name_similarity * 0.6 + desc_similarity * 0.4

        return name_similarity

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using word overlap."""
        if not text1 or not text2:
            return 0.0

        words1 = set(re.findall(r"\b\w+\b", text1.lower()))
        words2 = set(re.findall(r"\b\w+\b", text2.lower()))

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _calculate_apqc_alignment(
        self, apqc_context: str, source: ArchiMateElement, target: ArchiMateElement
    ) -> float:
        """Calculate APQC alignment score."""
        if not apqc_context or apqc_context == "cross_layer":
            return 0.5  # Neutral for cross-layer

        return self._calculate_apqc_alignment_from_category(apqc_context, source, target)

    def _calculate_apqc_alignment_from_category(
        self, apqc_category: str, source: ArchiMateElement, target: ArchiMateElement
    ) -> float:
        """Calculate alignment with APQC category expectations."""
        category_num = self._extract_category_number(apqc_category)

        if category_num not in self.apqc_category_mappings:
            return 0.5  # Neutral for unknown categories

        mapping = self.apqc_category_mappings[category_num]
        primary_types = mapping.get("primary_types", [])

        # Check if elements match expected types for this category
        source_match = source.type in primary_types
        target_match = target.type in primary_types

        if source_match and target_match:
            return 0.9
        elif source_match or target_match:
            return 0.7
        else:
            return 0.4

    def _calculate_layer_consistency(
        self, source: ArchiMateElement, target: ArchiMateElement, relationship_type: str
    ) -> float:
        """Calculate layer transition consistency."""
        source_layer = (source.layer or "").lower()
        target_layer = (target.layer or "").lower()

        # Valid layer transitions for different relationship types
        valid_transitions = {
            "Composition": [("same", "same")],  # Same layer
            "Aggregation": [("same", "same")],
            "Serving": [
                ("application", "business"),
                ("technology", "application"),
                ("same", "same"),
            ],
            "Realization": [
                ("application", "business"),
                ("technology", "application"),
                ("business", "motivation"),
                ("same", "same"),
            ],
            "Assignment": [("technology", "application"), ("business", "business")],
            "Triggering": [("same", "same")],
            "Flow": [("same", "same")],
            "Access": [("application", "application"), ("business", "application")],
        }

        transitions = valid_transitions.get(relationship_type, [])

        # Check if transition is valid
        for valid_source, valid_target in transitions:
            if valid_source == "same" and valid_target == "same":
                if source_layer == target_layer:
                    return 1.0
            elif source_layer == valid_source and target_layer == valid_target:
                return 1.0

        # Partially valid - same general direction
        if source_layer and target_layer:
            return 0.5

        # Unknown layers
        return 0.6

    # =========================================================================
    # Persistence Methods
    # =========================================================================

    def persist_derived_relationships(
        self,
        relationships: List[DerivedRelationship],
        architecture_id: int,
        auto_approve_threshold: float = 0.85,
    ) -> Dict[str, int]:
        """
        Persist derived relationships to the database.

        Args:
            relationships: List of derived relationships to persist
            architecture_id: ID of the architecture model
            auto_approve_threshold: Auto-approve relationships above this confidence

        Returns:
            Dict with counts of created and pending relationships
        """
        created = 0
        pending = 0

        for rel in relationships:
            if rel.confidence >= auto_approve_threshold:
                # Create actual ArchiMate relationship
                archimate_rel = ArchiMateRelationship(
                    type=rel.relationship_type,
                    source_id=rel.source_element_id,
                    target_id=rel.target_element_id,
                    architecture_id=architecture_id,
                )
                db.session.add(archimate_rel)
                created += 1
            else:
                pending += 1

        try:
            db.session.commit()
            logger.info("Persisted %d relationships, %d pending review", created, pending)
        except Exception as e:
            db.session.rollback()
            logger.error("Failed to persist relationships: %s", str(e))
            raise

        return {"created": created, "pending": pending}
