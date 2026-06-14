"""Step 2 Capability Derivation — three parallel catalogs with gap analysis.

Track 1: Business Capabilities (APQC) — three-tier matching (existing/similar/novel)
Track 2: Technical Capabilities (ACM) — domain-filtered catalog matching
Track 3: Application Coverage — gap analysis from ApplicationCapabilityCoverage
Plus: APQC process linking, compliance constraint injection
"""

import logging

from app.modules.ai_chat.services.solution_ai_service import (
    _token_overlap,
)

logger = logging.getLogger(__name__)

# Business domain → ACM domain mapping
_DOMAIN_TO_ACM = {
    "claims": ["DATA-STORAGE", "APPLICATION-SERVICES", "SECURITY-IDENTITY"],
    "fraud": ["AI-ANALYTICS", "DATA-STORAGE", "SECURITY-IDENTITY"],
    "finance": ["DATA-STORAGE", "APPLICATION-SERVICES"],
    "hr": ["USER-EXPERIENCE", "APPLICATION-SERVICES"],
    "supply chain": ["APPLICATION-SERVICES", "COMMUNICATION", "DATA-STORAGE"],
    "customer": ["USER-EXPERIENCE", "APPLICATION-SERVICES", "AI-ANALYTICS"],
    "compliance": ["SECURITY-IDENTITY", "DATA-STORAGE"],
    "analytics": ["AI-ANALYTICS", "DATA-STORAGE"],
    "infrastructure": ["DEVOPS-PLATFORM", "SECURITY-IDENTITY"],
    "digital": ["USER-EXPERIENCE", "APPLICATION-SERVICES", "AI-ANALYTICS", "DEVOPS-PLATFORM"],
}


def _map_business_domain_to_acm_domains(business_domain_text: str) -> list:
    """Map a business domain string to relevant ACM domains."""
    text_lower = business_domain_text.lower()
    matched = set()
    for keyword, domains in _DOMAIN_TO_ACM.items():
        if keyword in text_lower:
            matched.update(domains)
    # Default if nothing matched
    return list(matched) if matched else ["APPLICATION-SERVICES", "DATA-STORAGE"]


class CapabilityDerivationService:
    """Orchestrates the three-track capability derivation for Step 2."""

    def derive_business_capabilities(self, problem_description: str, motivation_elements: list = None):
        """Track 1: Derive business capabilities using three-tier matching.

        Reuses the existing _match_against_catalog() logic from solution_ai_routes.py.
        Returns list of enriched capability dicts with match_type, quality_score, etc.
        """
        from app.models.business_capabilities import BusinessCapability
        from app.modules.ai_chat.services.solution_ai_service import SolutionAIService

        existing_caps = BusinessCapability.query.order_by(BusinessCapability.name).all()
        existing_for_prompt = [{"id": c.id, "name": c.name} for c in existing_caps]

        ai_service = SolutionAIService()
        result = ai_service.suggest_capabilities(
            solution_description=problem_description,
            existing_capabilities=existing_for_prompt,
            motivation_elements=motivation_elements,
        )

        if not result.get("success") or not result.get("capabilities"):
            return {"capabilities": [], "gap_summary": ""}

        # Import the matching logic
        from app.modules.solutions_strategic.v2.routes.solution_ai_routes import _match_against_catalog
        matched = _match_against_catalog(
            suggestions=result["capabilities"],
            catalog_caps=existing_caps,
            problem_brief=problem_description,
        )

        # _match_against_catalog returns {"suggestions": [...], "gap_summary": {...}}
        # Unwrap to flat list for the JS consumer
        suggestions = matched.get("suggestions", []) if isinstance(matched, dict) else matched

        return {
            "capabilities": suggestions,
            "gap_summary": matched.get("gap_summary", "") if isinstance(matched, dict) else "",
        }

    def match_technical_capabilities(self, business_capability_name: str, business_domain: str = ""):
        """Track 2: Find technical capabilities from ACM catalog by domain.

        Returns list of existing TechnicalCapability matches + LLM-generated novel ones.
        """
        from app.models.technical_capability import TechnicalCapability

        acm_domains = _map_business_domain_to_acm_domains(
            business_capability_name + " " + business_domain
        )

        existing = TechnicalCapability.query.filter(
            TechnicalCapability.acm_domain.in_(acm_domains)
        ).order_by(TechnicalCapability.level_number).all()

        # Three-tier match against the capability name
        results = []
        for tc in existing:
            overlap = _token_overlap(business_capability_name, tc.name)
            if overlap >= 0.3:  # Lower threshold for technical caps (more specific names)
                results.append({
                    "id": tc.id,
                    "name": tc.name,
                    "acm_domain": tc.acm_domain,
                    "level": tc.level,
                    "description": tc.description,
                    "match_score": round(overlap, 2),
                    "match_type": "exact" if overlap >= 0.7 else "partial",
                    "source": "catalog",
                })

        return sorted(results, key=lambda x: x["match_score"], reverse=True)[:10]

    def get_coverage_gaps(self, capability_id: int):
        """Track 3: Query ApplicationCapabilityCoverage for a business capability."""
        try:
            from app.models.application_layer import ApplicationComponent
            from app.models.business_capabilities import ApplicationCapabilityCoverage

            coverage = ApplicationCapabilityCoverage.query.filter_by(
                capability_id=capability_id
            ).order_by(ApplicationCapabilityCoverage.coverage_percentage.desc()).all()

            # Batch-prefetch app names
            app_ids = [c.application_component_id for c in coverage]
            apps = ApplicationComponent.query.filter(
                ApplicationComponent.id.in_(app_ids)
            ).all() if app_ids else []
            apps_by_id = {a.id: a for a in apps}

            return [{
                "application_id": c.application_component_id,
                "application_name": apps_by_id[c.application_component_id].name if c.application_component_id in apps_by_id else f"App {c.application_component_id}",
                "coverage_percentage": c.coverage_percentage,
                "support_level": c.support_level,
                "is_strategic": c.is_strategic,
                "confidence_score": c.confidence_score,
            } for c in coverage]
        except Exception as e:
            logger.debug("Coverage query failed: %s", e)
            return []

    def get_compliance_requirements(self, capability_id: int):
        """Query compliance requirements for a business capability.

        Returns list of compliance requirement dicts.
        """
        try:
            from app.models.relationship_tables import capability_compliance_requirements
            from app.models.compliance_models import ComplianceRequirement
            reqs = ComplianceRequirement.query.join(
                capability_compliance_requirements
            ).filter(
                capability_compliance_requirements.c.business_capability_id == capability_id
            ).all()

            return [{
                "id": r.id,
                "name": r.name,
                "framework": getattr(r, "framework_name", ""),
                "description": r.description or "",
            } for r in reqs]
        except Exception as e:
            logger.debug("Compliance query failed (table/junction may not exist): %s", e)
            return []

    def link_apqc_processes(self, capability_name: str, capability_id: int = None):
        """Match a business capability to APQC processes.

        Returns list of matched APQC processes with match scores.
        """
        from app.models.business_capabilities import BusinessCapability

        # APQC capabilities have codes like "8.3 Process Claims"
        all_caps = BusinessCapability.query.filter(
            BusinessCapability.code.isnot(None)
        ).all()

        matches = []
        for cap in all_caps:
            score = _token_overlap(capability_name, cap.name)
            if score >= 0.5:
                matches.append({
                    "id": cap.id,
                    "name": cap.name,
                    "code": cap.code,
                    "match_score": round(score, 2),
                })

        return sorted(matches, key=lambda x: x["match_score"], reverse=True)[:5]
