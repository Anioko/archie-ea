"""
Document Entity Matching Service

Provides intelligent matching of extracted document entities to existing database records,
gap analysis, duplicate detection, and relationship auto-discovery.

Features:
- Fuzzy name matching using similarity algorithms
- Technology stack and domain matching
- Gap analysis comparing extracted vs existing entities
- Duplicate detection with warnings
- Auto-link suggestions for relationships
- Persona-aware extraction priorities
"""

import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_

from app import db
from app.models.application_layer import ApplicationInterface
from app.models.application_portfolio import ApplicationComponent
from app.models.archimate_core import ArchiMateElement
from app.models.business_capabilities import BusinessCapability
from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct

logger = logging.getLogger(__name__)


class DocumentEntityMatchingService:
    """
    Service for matching extracted document entities to existing database records
    with fuzzy matching, gap analysis, and duplicate detection.
    """

    # Similarity thresholds
    HIGH_MATCH_THRESHOLD = 0.85
    MEDIUM_MATCH_THRESHOLD = 0.65
    LOW_MATCH_THRESHOLD = 0.45

    # Persona extraction priorities
    PERSONA_EXTRACTION_PRIORITIES = {
        "enterprise_architect": {
            "focus": ["strategic", "governance", "portfolio"],
            "element_types": ["ApplicationComponent", "BusinessCapability", "TechnologyService"],
            "extract_priorities": ["capabilities", "applications", "strategic_elements"],
            "relationship_focus": ["Realization", "Composition", "Aggregation"],
        },
        "solutions_architect": {
            "focus": ["integration", "patterns", "nfr"],
            "element_types": ["ApplicationInterface", "ApplicationService", "DataObject"],
            "extract_priorities": ["interfaces", "services", "data_objects"],
            "relationship_focus": ["Serving", "Flow", "Access"],
        },
        "application_architect": {
            "focus": ["components", "apis", "modernization"],
            "element_types": [
                "ApplicationComponent",
                "ApplicationFunction",
                "ApplicationInterface",
            ],
            "extract_priorities": ["components", "functions", "apis"],
            "relationship_focus": ["Composition", "Serving", "Realization"],
        },
        "integration_architect": {
            "focus": ["interfaces", "data_flows", "events"],
            "element_types": ["ApplicationInterface", "ApplicationEvent", "DataObject"],
            "extract_priorities": ["interfaces", "events", "data_flows"],
            "relationship_focus": ["Flow", "Triggering", "Access"],
        },
        "systems_architect": {
            "focus": ["infrastructure", "deployment", "security"],
            "element_types": ["Node", "Device", "SystemSoftware", "TechnologyService"],
            "extract_priorities": ["infrastructure", "nodes", "technology"],
            "relationship_focus": ["Assignment", "Realization", "Serving"],
        },
        "business_architect": {
            "focus": ["capabilities", "processes", "value_streams"],
            "element_types": ["BusinessCapability", "BusinessProcess", "BusinessService"],
            "extract_priorities": ["capabilities", "processes", "services"],
            "relationship_focus": ["Realization", "Serving", "Composition"],
        },
        "business_analyst": {
            "focus": ["requirements", "processes", "stakeholders"],
            "element_types": ["BusinessProcess", "BusinessActor", "Requirement"],
            "extract_priorities": ["processes", "actors", "requirements"],
            "relationship_focus": ["Association", "Realization", "Influence"],
        },
        "product_analyst": {
            "focus": ["features", "journeys", "products"],
            "element_types": ["Product", "BusinessService", "ApplicationService"],
            "extract_priorities": ["products", "services", "features"],
            "relationship_focus": ["Composition", "Serving", "Association"],
        },
        "cio": {
            "focus": ["strategic", "risks", "investments"],
            "element_types": ["ApplicationComponent", "BusinessCapability", "Risk"],
            "extract_priorities": ["applications", "capabilities", "risks"],
            "relationship_focus": ["Realization", "Influence", "Association"],
        },
    }

    def __init__(self):
        """Initialize the entity matching service."""
        pass

    def match_extracted_entities(
        self,
        extracted_entities: Dict[str, Any],
        entity_type: str = "application",
        persona: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Match extracted entities against existing database records.

        Args:
            extracted_entities: Entities extracted from document analysis
            entity_type: Type of entity ('application', 'vendor', 'capability', 'archimate')
            persona: Optional persona for prioritized matching

        Returns:
            Matching results with confidence scores
        """
        try:
            results = {
                "matches": [],
                "potential_duplicates": [],
                "new_entities": [],
                "relationship_suggestions": [],
                "gap_analysis": {},
                "persona_insights": {},
            }

            # Get extracted elements based on type
            if entity_type == "application":
                results = self._match_applications(extracted_entities, persona)
            elif entity_type == "vendor":
                results = self._match_vendors(extracted_entities, persona)
            elif entity_type == "capability":
                results = self._match_capabilities(extracted_entities, persona)
            elif entity_type == "archimate":
                results = self._match_archimate_elements(extracted_entities, persona)

            # Add persona-specific insights
            if persona:
                results["persona_insights"] = self._generate_persona_insights(
                    extracted_entities, results, persona
                )

            return results

        except Exception as e:
            logger.error(f"Error matching entities: {e}")
            return {"error": str(e), "matches": [], "new_entities": []}

    def _match_applications(
        self, extracted_entities: Dict[str, Any], persona: Optional[str] = None
    ) -> Dict[str, Any]:
        """Match extracted application data against existing applications."""

        results = {
            "matches": [],
            "potential_duplicates": [],
            "new_entities": [],
            "relationship_suggestions": [],
            "gap_analysis": {},
        }

        # Get application data from extracted entities
        app_data = extracted_entities.get("application_data", {})
        archimate_elements = extracted_entities.get("archimate_elements", [])

        # Extract application name and alternatives
        app_name = app_data.get("name", "")
        app_description = app_data.get("description", "")
        tech_stack = app_data.get("technology_stack", [])
        business_domain = app_data.get("business_domain", "")

        if not app_name and archimate_elements:
            # Try to get name from first ApplicationComponent
            for elem in archimate_elements:
                if elem.get("type") == "ApplicationComponent":
                    app_name = elem.get("name", "")
                    break

        if not app_name:
            return results

        # Query existing applications
        existing_apps = ApplicationComponent.query.all()

        for existing_app in existing_apps:
            # Calculate name similarity
            name_similarity = self._calculate_similarity(
                app_name.lower(), existing_app.name.lower() if existing_app.name else ""
            )

            # Calculate technology similarity
            existing_tech = getattr(existing_app, "technology_stack", "") or ""
            tech_similarity = self._calculate_tech_similarity(tech_stack, existing_tech)

            # Calculate domain similarity
            existing_domain = getattr(existing_app, "business_domain", "") or ""
            domain_similarity = self._calculate_similarity(
                business_domain.lower(), existing_domain.lower()
            )

            # Calculate overall match score
            overall_score = (
                (name_similarity * 0.5) + (tech_similarity * 0.3) + (domain_similarity * 0.2)
            )

            if overall_score >= self.HIGH_MATCH_THRESHOLD:
                results["matches"].append(
                    {
                        "entity_id": existing_app.id,
                        "entity_name": existing_app.name,
                        "entity_type": "ApplicationComponent",
                        "match_confidence": round(overall_score * 100, 1),
                        "match_level": "high",
                        "match_reasons": self._get_match_reasons(
                            name_similarity, tech_similarity, domain_similarity
                        ),
                        "existing_data": {
                            "description": existing_app.description,
                            "technology": existing_tech,
                            "domain": existing_domain,
                            "status": getattr(existing_app, "status", "Unknown"),
                        },
                        "update_suggestions": self._generate_update_suggestions(
                            app_data, existing_app
                        ),
                    }
                )
            elif overall_score >= self.MEDIUM_MATCH_THRESHOLD:
                results["potential_duplicates"].append(
                    {
                        "entity_id": existing_app.id,
                        "entity_name": existing_app.name,
                        "entity_type": "ApplicationComponent",
                        "match_confidence": round(overall_score * 100, 1),
                        "match_level": "medium",
                        "warning": f"Possible duplicate of '{existing_app.name}'",
                        "match_reasons": self._get_match_reasons(
                            name_similarity, tech_similarity, domain_similarity
                        ),
                    }
                )
            elif overall_score >= self.LOW_MATCH_THRESHOLD:
                results["potential_duplicates"].append(
                    {
                        "entity_id": existing_app.id,
                        "entity_name": existing_app.name,
                        "entity_type": "ApplicationComponent",
                        "match_confidence": round(overall_score * 100, 1),
                        "match_level": "low",
                        "warning": f"May be related to '{existing_app.name}'",
                        "match_reasons": self._get_match_reasons(
                            name_similarity, tech_similarity, domain_similarity
                        ),
                    }
                )

        # If no high matches found, mark as new entity
        if not results["matches"]:
            results["new_entities"].append(
                {
                    "name": app_name,
                    "type": "ApplicationComponent",
                    "extracted_data": app_data,
                    "archimate_elements_count": len(archimate_elements),
                    "recommendation": "Create new application record",
                }
            )

        # Find relationship suggestions (enhanced with multiple methods)
        results["relationship_suggestions"] = self._find_application_relationships(
            app_data, archimate_elements, existing_apps
        )

        # ENHANCED: Add co-occurrence analysis
        try:
            from app.services.archimate.semantic_similarity_service import SemanticSimilarityService

            semantic_service = SemanticSimilarityService()

            # Get document text if available
            document_text = app_data.get("description", "") + " " + str(archimate_elements)

            co_occurrence_rels = semantic_service.analyze_co_occurrence(
                archimate_elements, document_text
            )

            # Add co-occurrence relationships
            for rel in co_occurrence_rels:
                # Check if target exists in existing apps
                for existing_app in existing_apps:
                    if existing_app.name and existing_app.name.lower() == rel["target"].lower():
                        results["relationship_suggestions"].append(
                            {
                                "source": rel["source"],
                                "target_id": existing_app.id,
                                "target_name": existing_app.name,
                                "relationship_type": rel["relationship_type"],
                                "confidence": rel["confidence"],
                                "evidence": rel["evidence"],
                                "discovery_method": "co_occurrence",
                            }
                        )
                        break
        except Exception as e:
            logger.warning(f"Co-occurrence analysis failed: {e}")

        # Generate gap analysis
        results["gap_analysis"] = self._generate_application_gap_analysis(
            extracted_entities, existing_apps
        )

        return results

    def _match_vendors(
        self, extracted_entities: Dict[str, Any], persona: Optional[str] = None
    ) -> Dict[str, Any]:
        """Match extracted vendor data against existing vendors."""

        results = {
            "matches": [],
            "potential_duplicates": [],
            "new_entities": [],
            "relationship_suggestions": [],
            "gap_analysis": {},
        }

        vendor_data = extracted_entities.get("vendor_data", {})
        vendor_name = vendor_data.get("name", "")

        if not vendor_name:
            return results

        # Query existing vendors
        existing_vendors = VendorOrganization.query.all()

        for existing_vendor in existing_vendors:
            name_similarity = self._calculate_similarity(
                vendor_name.lower(),
                existing_vendor.display_name.lower() if existing_vendor.display_name else "",
            )

            if name_similarity >= self.HIGH_MATCH_THRESHOLD:
                results["matches"].append(
                    {
                        "entity_id": existing_vendor.id,
                        "entity_name": existing_vendor.display_name,
                        "entity_type": "VendorOrganization",
                        "match_confidence": round(name_similarity * 100, 1),
                        "match_level": "high",
                        "existing_data": {
                            "vendor_type": existing_vendor.vendor_type,
                            "strategic_tier": getattr(existing_vendor, "strategic_tier", "Unknown"),
                            "website": existing_vendor.website,
                        },
                    }
                )
            elif name_similarity >= self.MEDIUM_MATCH_THRESHOLD:
                results["potential_duplicates"].append(
                    {
                        "entity_id": existing_vendor.id,
                        "entity_name": existing_vendor.display_name,
                        "entity_type": "VendorOrganization",
                        "match_confidence": round(name_similarity * 100, 1),
                        "match_level": "medium",
                        "warning": f"Possible duplicate of '{existing_vendor.display_name}'",
                    }
                )

        if not results["matches"]:
            results["new_entities"].append(
                {
                    "name": vendor_name,
                    "type": "VendorOrganization",
                    "extracted_data": vendor_data,
                    "recommendation": "Create new vendor record",
                }
            )

        return results

    def _match_capabilities(
        self, extracted_entities: Dict[str, Any], persona: Optional[str] = None
    ) -> Dict[str, Any]:
        """Match extracted capabilities against existing business capabilities."""

        results = {
            "matches": [],
            "potential_duplicates": [],
            "new_entities": [],
            "relationship_suggestions": [],
            "gap_analysis": {},
        }

        archimate_elements = extracted_entities.get("archimate_elements", [])
        capability_elements = [
            e for e in archimate_elements if e.get("type") in ["BusinessCapability", "Capability"]
        ]

        existing_capabilities = BusinessCapability.query.all()

        for cap_element in capability_elements:
            cap_name = cap_element.get("name", "")
            if not cap_name:
                continue

            best_match = None
            best_score = 0

            for existing_cap in existing_capabilities:
                similarity = self._calculate_similarity(
                    cap_name.lower(), existing_cap.name.lower() if existing_cap.name else ""
                )
                if similarity > best_score:
                    best_score = similarity
                    best_match = existing_cap

            if best_match and best_score >= self.HIGH_MATCH_THRESHOLD:
                results["matches"].append(
                    {
                        "extracted_name": cap_name,
                        "entity_id": best_match.id,
                        "entity_name": best_match.name,
                        "entity_type": "BusinessCapability",
                        "match_confidence": round(best_score * 100, 1),
                        "match_level": "high",
                    }
                )
            elif best_match and best_score >= self.MEDIUM_MATCH_THRESHOLD:
                results["potential_duplicates"].append(
                    {
                        "extracted_name": cap_name,
                        "entity_id": best_match.id,
                        "entity_name": best_match.name,
                        "entity_type": "BusinessCapability",
                        "match_confidence": round(best_score * 100, 1),
                        "match_level": "medium",
                        "warning": f"Similar to existing capability '{best_match.name}'",
                    }
                )
            else:
                results["new_entities"].append(
                    {
                        "name": cap_name,
                        "type": "BusinessCapability",
                        "extracted_data": cap_element,
                        "recommendation": "Create new capability or link to existing",
                    }
                )

        return results

    def _match_archimate_elements(
        self, extracted_entities: Dict[str, Any], persona: Optional[str] = None
    ) -> Dict[str, Any]:
        """Match extracted ArchiMate elements against existing elements."""

        results = {
            "matches": [],
            "potential_duplicates": [],
            "new_entities": [],
            "relationship_suggestions": [],
            "gap_analysis": {},
        }

        archimate_elements = extracted_entities.get("archimate_elements", [])

        # Get existing ArchiMate elements
        existing_elements = ArchiMateElement.query.limit(500).all()

        for extracted_elem in archimate_elements:
            elem_name = extracted_elem.get("name", "")
            elem_type = extracted_elem.get("type", "")

            if not elem_name:
                continue

            best_match = None
            best_score = 0

            for existing_elem in existing_elements:
                # Calculate name similarity
                name_similarity = self._calculate_similarity(
                    elem_name.lower(), existing_elem.name.lower() if existing_elem.name else ""
                )

                # Boost score if types match
                type_boost = 0.2 if existing_elem.element_type == elem_type else 0

                combined_score = name_similarity + type_boost

                if combined_score > best_score:
                    best_score = combined_score
                    best_match = existing_elem

            if best_match and best_score >= self.HIGH_MATCH_THRESHOLD:
                results["matches"].append(
                    {
                        "extracted_name": elem_name,
                        "extracted_type": elem_type,
                        "entity_id": best_match.id,
                        "entity_name": best_match.name,
                        "entity_type": best_match.element_type,
                        "match_confidence": round(min(best_score, 1.0) * 100, 1),
                        "match_level": "high",
                        "same_type": best_match.element_type == elem_type,
                    }
                )
            elif best_match and best_score >= self.MEDIUM_MATCH_THRESHOLD:
                results["potential_duplicates"].append(
                    {
                        "extracted_name": elem_name,
                        "extracted_type": elem_type,
                        "entity_id": best_match.id,
                        "entity_name": best_match.name,
                        "entity_type": best_match.element_type,
                        "match_confidence": round(min(best_score, 1.0) * 100, 1),
                        "match_level": "medium",
                        "warning": f"Similar to existing element '{best_match.name}'",
                    }
                )
            else:
                results["new_entities"].append(
                    {
                        "name": elem_name,
                        "type": elem_type,
                        "layer": extracted_elem.get("layer", "application"),
                        "extracted_data": extracted_elem,
                        "recommendation": "Create new ArchiMate element",
                    }
                )

        # Generate relationship suggestions based on extracted relationships
        extracted_relationships = extracted_entities.get("relationships", [])
        results["relationship_suggestions"] = self._suggest_relationships(
            archimate_elements, extracted_relationships, existing_elements
        )

        # ENHANCED: Add pattern-based relationship suggestions
        try:
            from app.services.archimate.relationship_pattern_service import (
                RelationshipPatternService,
            )

            pattern_service = RelationshipPatternService()

            pattern_suggestions = []
            for extracted_elem in archimate_elements:
                elem_type = extracted_elem.get("type", "")
                elem_layer = extracted_elem.get("layer", "")

                # Find matching existing element
                for existing_elem in existing_elements:
                    if existing_elem.type == elem_type:
                        # Get pattern-based suggestions
                        suggestions = pattern_service.suggest_relationships_from_patterns(
                            elem_type, existing_elem.type, elem_layer, existing_elem.layer
                        )

                        for suggestion in suggestions[:2]:  # Top 2 suggestions
                            pattern_suggestions.append(
                                {
                                    "source_name": extracted_elem.get("name"),
                                    "target_id": existing_elem.id,
                                    "target_name": existing_elem.name,
                                    "relationship_type": suggestion["relationship_type"],
                                    "confidence": suggestion["confidence"],
                                    "evidence": suggestion["evidence"],
                                    "discovery_method": "pattern_learning",
                                }
                            )

            # Merge pattern suggestions
            results["relationship_suggestions"].extend(pattern_suggestions)
        except Exception as e:
            logger.warning(f"Pattern-based relationship discovery failed: {e}")

        return results

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity using SequenceMatcher."""
        if not str1 or not str2:
            return 0.0
        return SequenceMatcher(None, str1, str2).ratio()

    def _calculate_tech_similarity(self, extracted_tech: List[str], existing_tech: str) -> float:
        """Calculate technology stack similarity."""
        if not extracted_tech or not existing_tech:
            return 0.0

        existing_tech_lower = existing_tech.lower()
        matches = 0

        for tech in extracted_tech:
            if tech.lower() in existing_tech_lower:
                matches += 1

        return matches / len(extracted_tech) if extracted_tech else 0.0

    def _get_match_reasons(self, name_sim: float, tech_sim: float, domain_sim: float) -> List[str]:
        """Generate human-readable match reasons."""
        reasons = []

        if name_sim >= 0.8:
            reasons.append(f"Name matches ({round(name_sim * 100)}%)")
        elif name_sim >= 0.5:
            reasons.append(f"Name partially matches ({round(name_sim * 100)}%)")

        if tech_sim >= 0.5:
            reasons.append(f"Technology stack overlap ({round(tech_sim * 100)}%)")

        if domain_sim >= 0.5:
            reasons.append(f"Business domain matches ({round(domain_sim * 100)}%)")

        return reasons

    def _generate_update_suggestions(
        self, extracted_data: Dict, existing_entity: Any
    ) -> List[Dict]:
        """Generate suggestions for updating existing entity with extracted data."""
        suggestions = []

        # Check for missing fields that can be filled
        if extracted_data.get("description") and not getattr(existing_entity, "description", None):
            suggestions.append(
                {
                    "field": "description",
                    "action": "add",
                    "value": extracted_data["description"][:200],
                    "reason": "Missing description can be populated",
                }
            )

        if extracted_data.get("technology_stack"):
            suggestions.append(
                {
                    "field": "technology_stack",
                    "action": "update",
                    "value": extracted_data["technology_stack"],
                    "reason": "Update technology stack from document",
                }
            )

        if extracted_data.get("business_owner") and not getattr(
            existing_entity, "business_owner", None
        ):
            suggestions.append(
                {
                    "field": "business_owner",
                    "action": "add",
                    "value": extracted_data["business_owner"],
                    "reason": "Business owner information found",
                }
            )

        return suggestions

    def _find_application_relationships(
        self, app_data: Dict, archimate_elements: List[Dict], existing_apps: List[Any]
    ) -> List[Dict]:
        """Find potential relationships between extracted app and existing apps."""
        suggestions = []

        # Look for integration mentions in description
        description = app_data.get("description", "").lower()
        integration_points = app_data.get("integration_points", [])

        for existing_app in existing_apps:
            app_name_lower = existing_app.name.lower() if existing_app.name else ""

            # Check if existing app is mentioned in description
            if app_name_lower and app_name_lower in description:
                suggestions.append(
                    {
                        "source": app_data.get("name", "Extracted App"),
                        "target_id": existing_app.id,
                        "target_name": existing_app.name,
                        "relationship_type": "Flow",
                        "confidence": 0.75,
                        "evidence": f"'{existing_app.name}' mentioned in document description",
                        "discovery_method": "text_mention",
                    }
                )

            # Check integration points
            for integration in integration_points:
                if app_name_lower in str(integration).lower():
                    suggestions.append(
                        {
                            "source": app_data.get("name", "Extracted App"),
                            "target_id": existing_app.id,
                            "target_name": existing_app.name,
                            "relationship_type": "Serving",
                            "confidence": 0.85,
                            "evidence": f"Integration point mentions '{existing_app.name}'",
                            "discovery_method": "integration_point",
                        }
                    )

        # ENHANCED: Use graph-based relationship discovery
        try:
            from app.services.archimate.graph_relationship_service import GraphRelationshipService

            graph_service = GraphRelationshipService()

            # Convert existing apps to ArchiMateElement format for graph service
            from app.models.archimate_core import ArchiMateElement

            existing_elements = []
            for app in existing_apps:
                if hasattr(app, "archimate_element_id") and app.archimate_element_id:
                    elem = ArchiMateElement.query.get(app.archimate_element_id)
                    if elem:
                        existing_elements.append(elem)

            # Discover relationships via graph traversal
            graph_relationships = graph_service.discover_relationships_via_graph(
                archimate_elements, existing_elements
            )
            suggestions.extend(graph_relationships)
        except Exception as e:
            logger.warning(f"Graph relationship discovery failed: {e}")

        # ENHANCED: Use semantic similarity for relationship discovery
        try:
            from app.services.archimate.semantic_similarity_service import SemanticSimilarityService

            semantic_service = SemanticSimilarityService()

            # Find semantically similar elements
            for arch_elem in archimate_elements:
                if arch_elem.get("type") == "ApplicationComponent":
                    similar = semantic_service.find_semantically_similar(
                        arch_elem, existing_elements, threshold=0.7
                    )

                    for match in similar[:3]:  # Top 3 matches
                        if match["similarity_score"] >= 0.8:
                            suggestions.append(
                                {
                                    "source": arch_elem.get("name"),
                                    "target_id": match["element_id"],
                                    "target_name": match["element_name"],
                                    "relationship_type": "Association",
                                    "confidence": match["similarity_score"],
                                    "evidence": f"Semantic similarity: {match['similarity_score']:.2f}",
                                    "discovery_method": "semantic_similarity",
                                }
                            )
        except Exception as e:
            logger.warning(f"Semantic similarity discovery failed: {e}")

        return suggestions

    def _suggest_relationships(
        self,
        extracted_elements: List[Dict],
        extracted_relationships: List[Dict],
        existing_elements: List[Any],
    ) -> List[Dict]:
        """Suggest relationships to existing ArchiMate elements."""
        suggestions = []

        # Build map of existing elements by name
        existing_by_name = {e.name.lower(): e for e in existing_elements if e.name}

        for rel in extracted_relationships:
            source_name = rel.get("source", "").lower()
            target_name = rel.get("target", "").lower()
            rel_type = rel.get("type", "Association")

            # Check if target exists in database
            if target_name in existing_by_name:
                existing_target = existing_by_name[target_name]
                suggestions.append(
                    {
                        "source_name": rel.get("source"),
                        "target_id": existing_target.id,
                        "target_name": existing_target.name,
                        "target_type": existing_target.element_type,
                        "relationship_type": rel_type,
                        "confidence": 0.9,
                        "action": "link_to_existing",
                        "evidence": "Target element exists in repository",
                    }
                )
            elif source_name in existing_by_name:
                existing_source = existing_by_name[source_name]
                suggestions.append(
                    {
                        "source_id": existing_source.id,
                        "source_name": existing_source.name,
                        "source_type": existing_source.element_type,
                        "target_name": rel.get("target"),
                        "relationship_type": rel_type,
                        "confidence": 0.9,
                        "action": "link_from_existing",
                        "evidence": "Source element exists in repository",
                    }
                )

        return suggestions

    def _generate_application_gap_analysis(
        self, extracted_entities: Dict, existing_apps: List[Any]
    ) -> Dict[str, Any]:
        """Generate gap analysis comparing extracted elements to existing portfolio."""

        archimate_elements = extracted_entities.get("archimate_elements", [])
        existing_element_names = set()

        # Get names of existing elements
        existing_elements = ArchiMateElement.query.limit(1000).all()
        for elem in existing_elements:
            if elem.name:
                existing_element_names.add(elem.name.lower())

        # Categorize extracted elements
        new_elements = []
        existing_matches = []

        for elem in archimate_elements:
            elem_name = elem.get("name", "").lower()
            if elem_name in existing_element_names:
                existing_matches.append(elem)
            else:
                new_elements.append(elem)

        # Group by layer
        new_by_layer = {}
        for elem in new_elements:
            layer = elem.get("layer", "unknown")
            if layer not in new_by_layer:
                new_by_layer[layer] = []
            new_by_layer[layer].append(elem)

        return {
            "total_extracted": len(archimate_elements),
            "new_elements_count": len(new_elements),
            "existing_matches_count": len(existing_matches),
            "coverage_percentage": round(
                (len(existing_matches) / len(archimate_elements) * 100)
                if archimate_elements
                else 0,
                1,
            ),
            "new_elements": new_elements[:20],  # Limit for display
            "existing_matches": existing_matches[:10],
            "new_by_layer": {layer: len(elems) for layer, elems in new_by_layer.items()},
            "recommendations": self._generate_gap_recommendations(new_elements, new_by_layer),
        }

    def _generate_gap_recommendations(
        self, new_elements: List[Dict], new_by_layer: Dict[str, List]
    ) -> List[str]:
        """Generate recommendations based on gap analysis."""
        recommendations = []

        if len(new_elements) > 10:
            recommendations.append(
                f"Document contains {len(new_elements)} new elements not in repository. "
                "Consider batch import."
            )

        for layer, elements in new_by_layer.items():
            if len(elements) > 5:
                recommendations.append(
                    f"{len(elements)} new {layer} layer elements found. "
                    f"Review for portfolio completeness."
                )

        if not new_elements:
            recommendations.append(
                "All extracted elements already exist in repository. "
                "Consider updating relationships."
            )

        return recommendations

    def _generate_persona_insights(
        self, extracted_entities: Dict, match_results: Dict, persona: str
    ) -> Dict[str, Any]:
        """Generate persona-specific insights from matching results."""

        config = self.PERSONA_EXTRACTION_PRIORITIES.get(persona, {})
        archimate_elements = extracted_entities.get("archimate_elements", [])

        # Filter elements relevant to persona
        relevant_types = config.get("element_types", [])
        relevant_elements = [e for e in archimate_elements if e.get("type") in relevant_types]

        # Generate focus insights
        focus_areas = config.get("focus", [])
        insights = {
            "persona": persona,
            "focus_areas": focus_areas,
            "relevant_elements_count": len(relevant_elements),
            "priority_elements": relevant_elements[:5],
            "recommended_actions": [],
        }

        # Add persona-specific recommendations
        if persona == "enterprise_architect":
            insights["recommended_actions"] = [
                "Review strategic alignment of extracted capabilities",
                "Assess portfolio impact of new applications",
                "Validate governance requirements",
            ]
        elif persona == "solutions_architect":
            insights["recommended_actions"] = [
                "Analyze integration patterns in extracted interfaces",
                "Review NFR implications",
                "Evaluate build vs buy options",
            ]
        elif persona == "integration_architect":
            insights["recommended_actions"] = [
                "Map data flows from extracted interfaces",
                "Identify event-driven patterns",
                "Assess API consolidation opportunities",
            ]
        elif persona == "cio":
            insights["recommended_actions"] = [
                "Evaluate strategic value of new elements",
                "Assess risk implications",
                "Review investment requirements",
            ]

        return insights

    def get_persona_extraction_prompt_additions(self, persona: str) -> str:
        """Get persona-specific additions to extraction prompts."""

        config = self.PERSONA_EXTRACTION_PRIORITIES.get(persona, {})
        if not config:
            return ""

        focus = config.get("focus", [])
        element_types = config.get("element_types", [])
        relationship_focus = config.get("relationship_focus", [])

        return f"""

PERSONA-SPECIFIC EXTRACTION PRIORITIES ({persona.replace('_', ' ').title()}):

Focus Areas: {', '.join(focus)}

Prioritize extracting these element types:
{chr(10).join(f'- {t}' for t in element_types)}

Pay special attention to these relationship types:
{chr(10).join(f'- {r}' for r in relationship_focus)}

Provide additional insights relevant to a {persona.replace('_', ' ').title()} role.
"""
