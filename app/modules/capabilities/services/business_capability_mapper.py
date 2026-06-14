"""
DEPRECATED: Import from app.modules.capabilities.services instead.
-> app.modules.capabilities.services.seeder_service

Business Capability Mapping Service

Maps applications to business capabilities using multiple analysis methods:
1. Direct ArchiMate relationships
2. Name/description semantic analysis
3. Technology stack inference
4. AI-powered capability detection
"""

import json
import logging
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_

from app import db
from app.models.application_layer import ApplicationComponent
from app.models.application_portfolio import ApplicationCapabilityMapping
from app.models.business_capabilities import BusinessCapability
from app.models.models import ArchiMateElement
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class BusinessCapabilityMapper:
    """
    Intelligent business capability mapping service.

    Uses multiple strategies to map applications to business capabilities:
    1. ArchiMate relationship analysis
    2. Semantic name/description matching
    3. Technology stack capability inference
    4. AI-powered semantic analysis
    """

    def __init__(self):
        self.llm_service = LLMService()

    def analyze_portfolio_capability_coverage(self) -> Dict:
        """
        Analyze entire application portfolio for business capability coverage.

        Returns:
            Dict with coverage analysis and mapping recommendations
        """
        # Get all active applications
        applications = ApplicationComponent.query.filter(
            ApplicationComponent.deployment_status.in_(["production", "Production", "Implementing"])
        ).all()

        # Get all business capabilities
        capabilities = BusinessCapability.query.all()

        # Check existing mappings
        existing_mappings = ApplicationCapabilityMapping.query.all()

        # Analyze coverage
        analysis = {
            "total_applications": len(applications),
            "total_capabilities": len(capabilities),
            "existing_mappings": len(existing_mappings),
            "unmapped_applications": 0,
            "mapped_applications": 0,
            "coverage_percentage": 0,
            "mapping_opportunities": [],
            "data_requirements": self._assess_data_requirements(applications, capabilities),
        }

        # Check each application for capability mapping
        for app in applications:
            app_mappings = ApplicationCapabilityMapping.query.filter_by(
                application_component_id=app.id
            ).all()

            if app_mappings:
                analysis["mapped_applications"] += 1
            else:
                analysis["unmapped_applications"] += 1
                # Suggest potential mappings
                suggested_caps = self._suggest_capability_mappings(app, capabilities)
                if suggested_caps:
                    analysis["mapping_opportunities"].append(
                        {
                            "application": app.name,
                            "application_id": app.id,
                            "suggested_capabilities": suggested_caps,
                            "confidence": "medium",
                        }
                    )

        # Calculate coverage percentage
        if analysis["total_applications"] > 0:
            analysis["coverage_percentage"] = int(
                (analysis["mapped_applications"] / analysis["total_applications"]) * 100
            )

        return analysis

    def _suggest_capability_mappings(
        self, application: ApplicationComponent, capabilities: List[BusinessCapability]
    ) -> List[Dict]:
        """
        Suggest business capability mappings for an application.

        Uses multiple strategies:
        1. ArchiMate relationship analysis
        2. Name/description semantic matching
        3. Technology stack inference
        """
        suggestions = []

        # Strategy 1: ArchiMate relationship analysis
        archimate_suggestions = self._analyze_archimate_relationships(application, capabilities)
        suggestions.extend(archimate_suggestions)

        # Strategy 2: Semantic name/description matching
        semantic_suggestions = self._semantic_capability_matching(application, capabilities)
        suggestions.extend(semantic_suggestions)

        # Strategy 3: Technology stack inference
        tech_suggestions = self._infer_capabilities_from_tech_stack(application, capabilities)
        suggestions.extend(tech_suggestions)

        # Remove duplicates and rank by confidence
        unique_suggestions = {}
        for suggestion in suggestions:
            cap_id = suggestion["capability_id"]
            if (
                cap_id not in unique_suggestions
                or suggestion["confidence_score"] > unique_suggestions[cap_id]["confidence_score"]
            ):
                unique_suggestions[cap_id] = suggestion

        # Sort by confidence score and return top 5
        return sorted(
            unique_suggestions.values(), key=lambda x: x["confidence_score"], reverse=True
        )[:5]

    def _analyze_archimate_relationships(
        self, application: ApplicationComponent, capabilities: List[BusinessCapability]
    ) -> List[Dict]:
        """
        Analyze ArchiMate relationships to find capability mappings.
        """
        suggestions = []

        if not application.archimate_element_id:
            return suggestions

        # Get the ArchiMate element
        archimate_elem = (
            db.session.query(ArchiMateElement)
            .filter_by(id=application.archimate_element_id)
            .first()
        )

        if not archimate_elem:
            return suggestions

        # Look for related capability elements
        related_capabilities = (
            db.session.query(ArchiMateElement)
            .filter(
                and_(
                    ArchiMateElement.type == "Capability",
                    ArchiMateElement.architecture_id == archimate_elem.architecture_id,
                )
            )
            .all()
        )

        for cap_elem in related_capabilities:
            # Find corresponding business capability
            business_cap = self._find_business_capability_by_name(cap_elem.name, capabilities)
            if business_cap:
                suggestions.append(
                    {
                        "capability_id": business_cap.id,
                        "capability_name": business_cap.name,
                        "mapping_method": "archimate_relationship",
                        "confidence_score": 0.8,
                        "reasoning": f"ArchiMate relationship between {archimate_elem.name} and capability {cap_elem.name}",
                    }
                )

        return suggestions

    def _semantic_capability_matching(
        self, application: ApplicationComponent, capabilities: List[BusinessCapability]
    ) -> List[Dict]:
        """
        Use semantic matching to find relevant capabilities.
        """
        suggestions = []

        # Create search text from application name and description
        app_text = f"{application.name} {application.description or ''}"

        for capability in capabilities:
            # Simple keyword matching for now (can be enhanced with AI)
            cap_text = f"{capability.name} {capability.description or ''}"

            # Calculate simple similarity based on keyword overlap
            similarity = self._calculate_keyword_similarity(app_text, cap_text)

            if similarity > 0.3:  # Threshold for semantic similarity
                suggestions.append(
                    {
                        "capability_id": capability.id,
                        "capability_name": capability.name,
                        "mapping_method": "semantic_matching",
                        "confidence_score": similarity,
                        "reasoning": f"Semantic similarity between application and capability names/descriptions",
                    }
                )

        return suggestions

    def _infer_capabilities_from_tech_stack(
        self, application: ApplicationComponent, capabilities: List[BusinessCapability]
    ) -> List[Dict]:
        """
        Infer capabilities from technology stack.
        """
        suggestions = []

        if not application.technology_stack:
            return suggestions

        # Technology-to-capability mappings
        tech_capability_map = {
            "crm": ["Customer Relationship Management", "Sales Management", "Customer Service"],
            "erp": [
                "Enterprise Resource Planning",
                "Financial Management",
                "Supply Chain Management",
            ],
            "sap": ["Enterprise Resource Planning", "Financial Management", "Human Resources"],
            "salesforce": ["Customer Relationship Management", "Sales Management"],
            "workday": ["Human Resources", "Payroll Management", "Talent Management"],
            "oracle": [
                "Database Management",
                "Enterprise Resource Planning",
                "Financial Management",
            ],
            "microsoft": ["Office Productivity", "Collaboration", "Email Management"],
            "aws": ["Cloud Infrastructure", "Platform Services", "Data Storage"],
            "azure": ["Cloud Infrastructure", "Platform Services", "Data Analytics"],
            "python": ["Data Analytics", "Business Intelligence", "Application Development"],
            "java": ["Application Development", "Enterprise Integration", "Web Services"],
            "react": ["User Interface Development", "Web Application Development"],
            "node.js": ["Application Development", "API Development", "Web Services"],
        }

        tech_stack = application.technology_stack.lower()

        for tech, capability_names in tech_capability_map.items():
            if tech in tech_stack:
                for cap_name in capability_names:
                    capability = self._find_business_capability_by_name(cap_name, capabilities)
                    if capability:
                        suggestions.append(
                            {
                                "capability_id": capability.id,
                                "capability_name": capability.name,
                                "mapping_method": "technology_inference",
                                "confidence_score": 0.6,
                                "reasoning": f'Technology stack "{tech}" suggests capability "{cap_name}"',
                            }
                        )

        return suggestions

    def _calculate_keyword_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate simple keyword similarity between two texts.
        """
        # Convert to lowercase and split into words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        # Calculate Jaccard similarity
        intersection = words1.intersection(words2)
        union = words1.union(words2)

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def _find_business_capability_by_name(
        self, name: str, capabilities: List[BusinessCapability]
    ) -> Optional[BusinessCapability]:
        """
        Find business capability by name (fuzzy matching).
        """
        name_lower = name.lower()

        # Exact match first
        for cap in capabilities:
            if cap.name.lower() == name_lower:
                return cap

        # Partial match
        for cap in capabilities:
            if name_lower in cap.name.lower() or cap.name.lower() in name_lower:
                return cap

        return None

    def _assess_data_requirements(
        self, applications: List[ApplicationComponent], capabilities: List[BusinessCapability]
    ) -> Dict:
        """
        Assess what data is missing for proper capability mapping.
        """
        requirements = {
            "missing_descriptions": 0,
            "missing_tech_stacks": 0,
            "missing_archimate_links": 0,
            "applications_needing_review": [],
            "total_applications": len(applications),
        }

        for app in applications:
            issues = []

            if not app.description or len(app.description.strip()) < 10:
                requirements["missing_descriptions"] += 1
                issues.append("description")

            if not app.technology_stack:
                requirements["missing_tech_stacks"] += 1
                issues.append("technology_stack")

            if not app.archimate_element_id:
                requirements["missing_archimate_links"] += 1
                issues.append("archimate_link")

            if issues:
                requirements["applications_needing_review"].append(
                    {"application_id": app.id, "application_name": app.name, "missing_data": issues}
                )

        return requirements

    def create_capability_mapping(
        self,
        application_id: int,
        capability_id: int,
        support_level: str = "Primary",
        coverage_percentage: int = 80,
        maturity_level: int = 3,
        mapping_method: str = "manual",
    ) -> bool:
        """
        Create a new application-capability mapping.
        """
        try:
            # Check if mapping already exists
            existing = ApplicationCapabilityMapping.query.filter_by(
                application_component_id=application_id, business_capability_id=capability_id
            ).first()

            if existing:
                return False  # Mapping already exists

            # Create new mapping
            mapping = ApplicationCapabilityMapping(
                application_component_id=application_id,
                business_capability_id=capability_id,
                support_level=support_level,
                coverage_percentage=coverage_percentage,
                is_strategic=True if mapping_method == "vendor_catalog_analysis" else False,
                investment_priority="High"
                if mapping_method == "vendor_catalog_analysis"
                else "Medium",
            )

            db.session.add(mapping)
            db.session.commit()

            logger.info(
                f"Created capability mapping: Application {application_id} -> Capability {capability_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error creating capability mapping: {e}")
            db.session.rollback()
            return False
