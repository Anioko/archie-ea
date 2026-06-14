"""
DEPRECATED: Import from app.modules.capabilities.services instead.
-> app.modules.capabilities.services.capability_service

Business Capability Mapping Service

Maps applications to business capabilities using multiple analysis methods.
Provides intelligent mapping recommendations for gap analysis.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import joinedload

from app import db
from app.models.application_layer import ApplicationComponent
from app.models.business_capabilities import ApplicationCapabilityCoverage, BusinessCapability

logger = logging.getLogger(__name__)


class CapabilityMappingService:
    """
    Business capability mapping service.

    Uses multiple strategies to map applications to business capabilities:
    1. Name/description semantic analysis
    2. Technology stack inference
    3. Manual mapping recommendations
    4. Public information on vendor websites and search engines
    """

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
        existing_mappings = ApplicationCapabilityCoverage.query.all()

        # Analyze coverage
        analysis = {
            "total_applications": len(applications),
            "total_capabilities": len(capabilities),
            "existing_mappings": len(existing_mappings),
            "unmapped_applications": 0,
            "mapped_applications": 0,
            "coverage_percentage": 0,
            "mapping_opportunities": [],
            "coverage_by_domain": {},
            "coverage_by_level": {},
        }

        # Check each application for capability mapping
        for app in applications:
            app_mappings = ApplicationCapabilityCoverage.query.filter_by(
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
        1. Name matching
        2. Description matching
        3. Technology stack inference
        """
        suggestions = []
        app_name = (application.name or "").lower()
        app_desc = (application.description or "").lower()

        for capability in capabilities:
            cap_name = (capability.name or "").lower()
            cap_desc = (capability.description or "").lower()
            cap_domain = (capability.business_domain or "").lower()

            score = 0
            reasons = []

            # Name matching
            if cap_name in app_name or app_name in cap_name:
                score += 40
                reasons.append("name_match")

            # Description matching
            if cap_name in app_desc or app_desc in cap_desc:
                score += 30
                reasons.append("description_match")

            # Domain matching
            if self._domain_matches_application(cap_domain, application):
                score += 20
                reasons.append("domain_match")

            # Technology stack inference
            if self._technology_matches_capability(application, capability):
                score += 25
                reasons.append("technology_match")

            # Capability type matching
            if self._capability_type_matches_application(capability, application):
                score += 15
                reasons.append("type_match")

            if score >= 30:  # Minimum threshold for suggestion
                confidence = "high" if score >= 70 else "medium" if score >= 50 else "low"
                suggestions.append(
                    {
                        "capability_id": capability.id,
                        "capability_name": capability.name,
                        "capability_domain": capability.business_domain,
                        "score": score,
                        "confidence": confidence,
                        "reasons": reasons,
                    }
                )

        # Sort by score and return top suggestions
        suggestions.sort(key=lambda x: x["score"], reverse=True)
        return suggestions[:5]  # Return top 5 suggestions

    def _domain_matches_application(self, domain: str, application: ApplicationComponent) -> bool:
        """Check if capability domain matches application characteristics."""
        domain_keywords = {
            "customer": ["crm", "customer", "sales", "marketing", "service"],
            "product": ["product", "manufacturing", "inventory", "catalog"],
            "operations": ["operations", "logistics", "supply", "chain", "warehouse"],
            "finance": ["finance", "accounting", "billing", "payment", "budget"],
            "hr": ["hr", "human", "resources", "payroll", "recruitment"],
            "it": ["it", "infrastructure", "network", "security", "backup"],
        }

        app_text = f"{application.name or ''} {application.description or ''}".lower()

        keywords = domain_keywords.get(domain, [])
        return any(keyword in app_text for keyword in keywords)

    def _technology_matches_capability(
        self, application: ApplicationComponent, capability: BusinessCapability
    ) -> bool:
        """Check if application technology stack matches capability requirements."""
        # This is a simplified version - in production, you'd analyze actual tech stack
        tech_capability_map = {
            "web": ["customer", "product", "marketing"],
            "database": ["finance", "operations", "hr"],
            "api": ["integration", "operations", "supply"],
            "mobile": ["customer", "sales", "field"],
            "cloud": ["infrastructure", "it", "backup"],
        }

        # Simplified tech detection from application name/description
        app_text = f"{application.name or ''} {application.description or ''}".lower()

        for tech, domains in tech_capability_map.items():
            if (
                tech in app_text
                and capability.business_domain
                and capability.business_domain.lower() in domains
            ):
                return True

        return False

    def _capability_type_matches_application(
        self, capability: BusinessCapability, application: ApplicationComponent
    ) -> bool:
        """Check if capability type matches application type."""
        type_app_map = {
            "core": ["erp", "crm", "core", "platform"],
            "supporting": ["support", "help", "assist", "tool"],
            "differentiating": ["analytics", "ai", "innovation", "advanced"],
        }

        app_text = f"{application.name or ''} {application.description or ''}".lower()

        for cap_type, app_types in type_app_map.items():
            if capability.capability_type == cap_type:
                return any(app_type in app_text for app_type in app_types)

        return False

    def create_capability_mapping(
        self,
        application_id: int,
        capability_id: int,
        coverage_percentage: int = 50,
        support_level: str = "partial",
        assessor: str = "System",
    ) -> ApplicationCapabilityCoverage:
        """
        Create a new capability mapping.

        Args:
            application_id: ID of the application
            capability_id: ID of the business capability
            coverage_percentage: Coverage percentage (0 - 100)
            support_level: Support level (full, partial, minimal)
            assessor: Who made this assessment

        Returns:
            Created ApplicationCapabilityCoverage
        """
        # Check if mapping already exists
        existing = ApplicationCapabilityCoverage.query.filter_by(
            application_component_id=application_id, capability_id=capability_id
        ).first()

        if existing:
            # Update existing mapping
            existing.coverage_percentage = coverage_percentage
            existing.support_level = support_level
            db.session.commit()
            return existing
        else:
            # Create new mapping
            mapping = ApplicationCapabilityCoverage(
                application_component_id=application_id,
                capability_id=capability_id,
                coverage_percentage=coverage_percentage,
                support_level=support_level,
            )
            db.session.add(mapping)
            db.session.commit()
            return mapping

    def remove_capability_mapping(self, application_id: int, capability_id: int) -> bool:
        """
        Remove a capability mapping.

        Args:
            application_id: ID of the application
            capability_id: ID of the business capability

        Returns:
            True if mapping was removed, False if not found
        """
        mapping = ApplicationCapabilityCoverage.query.filter_by(
            application_component_id=application_id, capability_id=capability_id
        ).first()

        if mapping:
            db.session.delete(mapping)
            db.session.commit()
            return True

        return False

    def get_application_capabilities(
        self, application_id: int
    ) -> List[ApplicationCapabilityCoverage]:
        """Get all capability mappings for an application."""
        return (
            ApplicationCapabilityCoverage.query.filter_by(application_component_id=application_id)
            .options(joinedload(ApplicationCapabilityCoverage.capability))
            .all()
        )

    def get_capability_applications(
        self, capability_id: int
    ) -> List[ApplicationCapabilityCoverage]:
        """Get all application mappings for a capability."""
        return (
            ApplicationCapabilityCoverage.query.filter_by(capability_id=capability_id)
            .all()
        )

    def get_mappings(self, application_id=None, domain=None, maturity_level=None):
        """Application<->capability mappings, optionally filtered by application."""
        from app.models.application_capability import ApplicationCapabilityMapping
        q = ApplicationCapabilityMapping.query
        if application_id:
            q = q.filter(ApplicationCapabilityMapping.application_component_id == application_id)
        return [
            {"id": m.id, "application_component_id": m.application_component_id,
             "business_capability_id": getattr(m, "business_capability_id", None),
             "support_level": getattr(m, "support_level", None),
             "coverage_percentage": getattr(m, "coverage_percentage", None)}
            for m in q.limit(1000).all()
        ]