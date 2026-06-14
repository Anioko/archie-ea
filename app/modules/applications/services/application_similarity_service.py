"""

Application Similarity Analysis Service

AI-powered service for detecting duplicate applications and consolidation opportunities.
Uses LLMs to analyze multiple dimensions of similarity between applications.
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app import db
from app.models import APISettings, LLMInteraction
from app.models.application_consolidation import (
    ApplicationConsolidationRecommendation,
    ApplicationSimilarityAnalysis,
)
from app.models.application_layer import ApplicationComponent
from app.models.application_portfolio import ApplicationCapabilityMapping
from app.models.business_capabilities import BusinessCapability
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ApplicationSimilarityService:
    """
    AI-powered service for analyzing application similarity and detecting duplicates.
    """

    # Weight factors for overall similarity calculation
    SIMILARITY_WEIGHTS = {
        "capability_overlap": 0.30,  # Business capabilities are most important
        "functional_similarity": 0.25,  # Functional overlap
        "technology_similarity": 0.20,  # Tech stack similarity
        "data_similarity": 0.15,  # Data model overlap
        "user_overlap": 0.10,  # User group overlap
    }

    def __init__(self):
        """Initialize the similarity analysis service."""
        self.llm_service = LLMService()

    async def analyze_application_pair(
        self, app1_id: int, app2_id: int, provider: str = "claude", user_id: Optional[int] = None
    ) -> ApplicationSimilarityAnalysis:
        """
        Analyze similarity between two applications using AI.

        Args:
            app1_id: First application ID
            app2_id: Second application ID
            provider: LLM provider ('claude', 'openai', 'gemini')
            user_id: User ID performing the analysis

        Returns:
            ApplicationSimilarityAnalysis object with calculated scores
        """
        app1 = ApplicationComponent.query.get_or_404(app1_id)
        app2 = ApplicationComponent.query.get_or_404(app2_id)

        # Check if analysis already exists
        existing = ApplicationSimilarityAnalysis.query.filter(
            (
                (ApplicationSimilarityAnalysis.app_1_id == app1_id)
                & (ApplicationSimilarityAnalysis.app_2_id == app2_id)
            )
            | (
                (ApplicationSimilarityAnalysis.app_1_id == app2_id)
                & (ApplicationSimilarityAnalysis.app_2_id == app1_id)
            )
        ).first()

        if existing:
            logger.info(f"Similarity analysis already exists for apps {app1_id} and {app2_id}")
            return existing

        # Gather application data for comparison
        app1_data = self._gather_application_data(app1)
        app2_data = self._gather_application_data(app2)

        # Build AI prompt for similarity analysis
        prompt = self._build_similarity_analysis_prompt(app1_data, app2_data)

        # Use LLM service to generate response
        # The service will handle provider/model selection from database
        try:
            # Get configured provider and model
            provider_name, model = LLMService._get_configured_provider()

            # If specific provider requested, try to use it
            if provider and provider != provider_name:
                settings = APISettings.query.filter_by(provider=provider, enabled=True).first()
                if settings and settings.default_model:
                    provider_name = provider
                    model = settings.default_model

            # Call LLM using the internal method
            response_text, interaction = LLMService._call_llm(
                prompt=prompt,
                model=model,
                provider=provider_name,
                user_id=user_id,
                project_id=None,
                max_tokens=4000,
            )
        except Exception as e:
            logger.error(f"Error calling LLM service: {str(e)}")
            raise

        # Parse LLM response
        similarity_data = self._parse_similarity_response(response_text)

        # Calculate overall similarity score
        overall_score = self._calculate_overall_similarity(similarity_data)

        # Create similarity analysis record
        analysis = ApplicationSimilarityAnalysis(
            app_1_id=app1_id,
            app_2_id=app2_id,
            capability_overlap_score=similarity_data.get("capability_overlap_score", 0),
            technology_similarity_score=similarity_data.get("technology_similarity_score", 0),
            functional_similarity_score=similarity_data.get("functional_similarity_score", 0),
            data_similarity_score=similarity_data.get("data_similarity_score", 0),
            user_overlap_score=similarity_data.get("user_overlap_score", 0),
            business_domain_match=similarity_data.get("business_domain_match", 0),
            overall_similarity_score=overall_score,
            shared_capabilities=json.dumps(similarity_data.get("shared_capabilities", [])),
            shared_technologies=json.dumps(similarity_data.get("shared_technologies", [])),
            shared_user_types=json.dumps(similarity_data.get("shared_user_types", [])),
            shared_business_processes=json.dumps(
                similarity_data.get("shared_business_processes", [])
            ),
            consolidation_opportunity=self._determine_consolidation_opportunity(overall_score),
            recommended_action=similarity_data.get("recommended_action", "keep_both"),
            recommended_survivor=similarity_data.get("recommended_survivor_id"),
            estimated_cost_savings=Decimal(str(similarity_data.get("estimated_cost_savings", 0))),
            consolidation_complexity=similarity_data.get("consolidation_complexity", "moderate"),
            reasoning=similarity_data.get("reasoning", ""),
            analyzed_by_ai_model=model or "unknown",
            confidence_score=similarity_data.get("confidence_score", 0.7),
            analysis_date=datetime.utcnow(),
            data_migration_required=similarity_data.get("data_migration_required", False),
            user_migration_required=similarity_data.get("user_migration_required", False),
            integration_changes_required=similarity_data.get("integration_changes_required", False),
            blocking_dependencies=json.dumps(similarity_data.get("blocking_dependencies", [])),
        )

        db.session.add(analysis)
        db.session.commit()

        logger.info(
            f"Created similarity analysis: {app1.name} vs {app2.name} - {overall_score}% similar"
        )

        return analysis

    def analyze_portfolio(
        self,
        application_ids: Optional[List[int]] = None,
        provider: str = "claude",
        user_id: Optional[int] = None,
        min_similarity_threshold: int = 40,
    ) -> Dict[str, Any]:
        """
        Analyze entire portfolio or subset of applications for duplicates.

        Args:
            application_ids: Optional list of application IDs to analyze. If None, analyzes all.
            provider: LLM provider
            user_id: User ID performing the analysis
            min_similarity_threshold: Minimum similarity score to consider (0 - 100)

        Returns:
            Dictionary with analysis results and statistics
        """
        if application_ids:
            applications = ApplicationComponent.query.filter(
                ApplicationComponent.id.in_(application_ids)
            ).all()
        else:
            applications = ApplicationComponent.query.all()

        if len(applications) < 2:
            return {
                "total_analyses": 0,
                "duplicate_pairs": 0,
                "high_similarity_pairs": 0,
                "medium_similarity_pairs": 0,
                "low_similarity_pairs": 0,
            }

        # Generate all pairs (n choose 2)
        # Build lookup dict to avoid N+1 queries when filtering pairs
        app_lookup = {app.id: app for app in applications}
        pairs = []
        for i in range(len(applications)):
            for j in range(i + 1, len(applications)):
                pairs.append((applications[i].id, applications[j].id))

        # Pre-filter pairs to avoid expensive LLM calls on obviously different applications
        filtered_pairs = []
        for app1_id, app2_id in pairs:
            app1 = app_lookup[app1_id]
            app2 = app_lookup[app2_id]

            # Skip if basic checks fail
            if not self._should_analyze_pair(app1, app2):
                logger.info(f"Skipping pair {app1_id}-{app2_id}: basic filtering failed")
                continue

            filtered_pairs.append((app1_id, app2_id))

        total_pairs = len(filtered_pairs)
        logger.info(
            f"Analyzing {total_pairs} application pairs for similarity (after pre-filtering)"
        )

        # Analyze pairs (in production, this should be done in background jobs)
        results = {
            "total_analyses": 0,
            "duplicate_pairs": 0,
            "high_similarity_pairs": 0,  # >= 70
            "medium_similarity_pairs": 0,  # 50 - 69
            "low_similarity_pairs": 0,  # 40 - 49
            "analyses_created": [],
        }

        # Note: In production, this should use background jobs for large portfolios
        # For now, we'll analyze synchronously (can be slow for large portfolios)
        from app.services.core.async_utils import get_or_create_event_loop

        loop = get_or_create_event_loop()

        for app1_id, app2_id in filtered_pairs:
            try:
                analysis = loop.run_until_complete(
                    self.analyze_application_pair(app1_id, app2_id, provider, user_id)
                )

                results["total_analyses"] += 1

                if analysis.overall_similarity_score >= min_similarity_threshold:
                    results["duplicate_pairs"] += 1

                    if analysis.overall_similarity_score >= 70:
                        results["high_similarity_pairs"] += 1
                    elif analysis.overall_similarity_score >= 50:
                        results["medium_similarity_pairs"] += 1
                    else:
                        results["low_similarity_pairs"] += 1

                    results["analyses_created"].append(
                        {
                            "app1_id": app1_id,
                            "app2_id": app2_id,
                            "similarity_score": analysis.overall_similarity_score,
                        }
                    )
            except Exception as e:
                logger.error(f"Error analyzing pair {app1_id}-{app2_id}: {str(e)}")
                continue

        return results

    def _should_analyze_pair(self, app1: ApplicationComponent, app2: ApplicationComponent) -> bool:
        """Pre-filter application pairs to avoid unnecessary LLM calls."""

        # Skip if names are too different (basic similarity check)
        name_similarity = self._calculate_name_similarity(app1.name, app2.name)
        if name_similarity < 30:  # Less than 30% name similarity
            return False

        # Skip if business domains are completely different
        domain1 = (app1.business_domain or "").lower()
        domain2 = (app2.business_domain or "").lower()
        if domain1 and domain2 and domain1 != domain2:
            # Only skip if both have domains and they're different
            return False

        # Skip if application types are completely different
        type1 = (app1.application_type or "").lower()
        type2 = (app2.application_type or "").lower()
        if type1 and type2 and type1 != type2 and not self._are_compatible_types(type1, type2):
            return False

        # Skip if both have technology stacks with no overlap
        tech1 = (app1.technology_stack or "").lower()
        tech2 = (app2.technology_stack or "").lower()
        if tech1 and tech2 and not self._has_tech_overlap(tech1, tech2):
            return False

        return True

    def _calculate_name_similarity(self, name1: str, name2: str) -> int:
        """Calculate basic name similarity percentage."""
        name1 = name1.lower()
        name2 = name2.lower()

        # Extract key words (remove common words)
        common_words = {
            "system",
            "application",
            "app",
            "platform",
            "portal",
            "management",
            "service",
        }
        words1 = [w for w in name1.split() if w not in common_words and len(w) > 2]
        words2 = [w for w in name2.split() if w not in common_words and len(w) > 2]

        if not words1 or not words2:
            return 0

        # Calculate Jaccard similarity
        set1 = set(words1)
        set2 = set(words2)
        intersection = set1.intersection(set2)
        union = set1.union(set2)

        return int((len(intersection) / len(union)) * 100)

    def _are_compatible_types(self, type1: str, type2: str) -> bool:
        """Check if application types are compatible for potential duplication."""
        compatible_pairs = {
            ("web", "portal"),
            ("web", "application"),
            ("portal", "application"),
            ("system", "platform"),
            ("service", "application"),
            ("tool", "application"),
        }

        # Add reverse pairs
        compatible_pairs.update({(b, a) for a, b in compatible_pairs})

        return (type1, type2) in compatible_pairs

    def _has_tech_overlap(self, tech1: str, tech2: str) -> bool:
        """Check if technology stacks have any overlap."""
        # Extract technology keywords
        tech1_words = set(tech1.lower().replace(",", " ").replace(";", " ").split())
        tech2_words = set(tech2.lower().replace(",", " ").replace(";", " ").split())

        # Look for common technologies
        common_techs = {
            "java",
            "python",
            "javascript",
            "node",
            "react",
            "angular",
            "vue",
            "spring",
            "django",
            "flask",
            "express",
            "dotnet",
            ".net",
            "sql",
            "mysql",
            "postgres",
            "oracle",
            "mongodb",
            "redis",
            "aws",
            "azure",
            "gcp",
            "docker",
            "kubernetes",
            "k8s",
            "html",
            "css",
            "bootstrap",
            "tailwind",
            "jquery",
        }

        tech1_relevant = tech1_words.intersection(common_techs)
        tech2_relevant = tech2_words.intersection(common_techs)

        return bool(tech1_relevant.intersection(tech2_relevant))

    def _gather_application_data(self, app: ApplicationComponent) -> Dict[str, Any]:
        """Gather all relevant data about an application for comparison."""
        # Get capabilities
        capabilities = []
        try:
            capability_mappings = ApplicationCapabilityMapping.query.filter_by(
                application_component_id=app.id
            ).all()
            for mapping in capability_mappings:
                if mapping.capability:
                    capabilities.append(
                        {
                            "name": mapping.capability.name,
                            "description": mapping.capability.description,
                            "level": mapping.capability.level,
                        }
                    )
        except Exception:
            logger.debug("Failed to load capability mappings for app %s", app.id, exc_info=True)

        # Get business processes
        business_processes = []
        try:
            from app.models.process_data import BusinessProcess

            processes = BusinessProcess.query.filter_by(application_component_id=app.id).all()
            for process in processes:
                business_processes.append(
                    {
                        "name": process.name,
                        "level": process.level,
                        "description": process.description,
                    }
                )
        except Exception:
            logger.debug("Failed to load business processes for app %s", app.id, exc_info=True)

        # Get technology stack (from description or custom fields)
        technology_stack = app.technology_stack or ""

        # Extract user communities from description or other fields
        user_communities = []
        description = app.description or ""
        owner_team = getattr(app, "owner_team", None) or ""  # model-safety-ok: optional field (not on all ApplicationComponent variants)

        # Extract user types from description
        user_keywords = [
            "user",
            "staff",
            "employee",
            "customer",
            "client",
            "admin",
            "manager",
            "analyst",
            "operator",
        ]
        for keyword in user_keywords:
            if keyword in description.lower():
                user_communities.append(keyword.title())

        if owner_team:
            user_communities.append(owner_team)

        # Get cost information if available
        annual_cost = getattr(app, "annual_cost", 0) or 0  # model-safety-ok: optional field (annual_cost on VendorContract, not ApplicationComponent)
        maintenance_cost = app.maintenance_cost or 0

        # Get ArchiMate elements linked to this application
        archimate_elements = []
        if app.archimate_element_id:
            try:
                from app.models import ArchiMateElement

                element = ArchiMateElement.query.get(app.archimate_element_id)
                if element:
                    archimate_elements.append(
                        {
                            "name": element.name,
                            "type": element.type,
                            "description": element.description,
                        }
                    )
            except Exception:
                logger.debug("Failed to load ArchiMate elements for app %s", app.id, exc_info=True)

        return {
            "id": app.id,
            "name": app.name,
            "description": app.description or "",
            "application_type": app.application_type or "",
            "deployment_status": app.deployment_status or "",
            "technology_stack": technology_stack,
            "capabilities": capabilities,
            "business_processes": business_processes,
            "user_communities": list(set(user_communities)),  # Remove duplicates
            "archimate_elements": archimate_elements,
            "owner_team": owner_team,
            "business_domain": app.business_domain or "",
            "annual_cost": annual_cost,
            "maintenance_cost": maintenance_cost,
            "criticality": app.business_criticality or "Medium",
            "integration_count": self._get_integration_count(app.id),
        }

    def _get_integration_count(self, app_id: int) -> int:
        """Get number of integrations for an application."""
        try:
            from app.models.application_layer import ApplicationInterface

            count = ApplicationInterface.query.filter(
                (ApplicationInterface.source_application_id == app_id)
                | (ApplicationInterface.target_application_id == app_id)
            ).count()
            return count
        except Exception:
            return 0

    def _build_similarity_analysis_prompt(
        self, app1_data: Dict[str, Any], app2_data: Dict[str, Any]
    ) -> str:
        """Build LLM prompt for similarity analysis."""

        # Format capabilities for better readability
        app1_caps = "\n".join(
            [
                f"  - {cap['name']}: {cap.get('description', 'No description')}"
                for cap in app1_data["capabilities"]
            ]
        )
        app2_caps = "\n".join(
            [
                f"  - {cap['name']}: {cap.get('description', 'No description')}"
                for cap in app2_data["capabilities"]
            ]
        )

        # Format business processes
        app1_processes = "\n".join(
            [
                f"  - {proc['name']} (Level {proc['level']})"
                for proc in app1_data["business_processes"]
            ]
        )
        app2_processes = "\n".join(
            [
                f"  - {proc['name']} (Level {proc['level']})"
                for proc in app2_data["business_processes"]
            ]
        )

        # Calculate potential savings
        potential_savings = (
            app1_data.get("annual_cost", 0) + app2_data.get("annual_cost", 0)
        ) * 0.3  # 30% savings assumption

        return f"""You are an expert Enterprise Architect specializing in application portfolio optimization and consolidation analysis.

TASK: Analyze these two applications for potential duplication and consolidation opportunities.

APPLICATION 1:
- Name: {app1_data['name']}
- Description: {app1_data['description']}
- Type: {app1_data['application_type']}
- Criticality: {app1_data['criticality']}
- Business Domain: {app1_data['business_domain']}
- Owner Team: {app1_data['owner_team']}
- Annual Cost: ${app1_data.get('annual_cost', 0):,}
- Technology Stack: {app1_data['technology_stack']}
- Integration Count: {app1_data.get('integration_count', 0)}

Business Capabilities:
{app1_caps if app1_caps else '  - No capabilities specified'}

Business Processes:
{app1_processes if app1_processes else '  - No processes specified'}

User Communities: {', '.join(app1_data.get('user_communities', []))}

APPLICATION 2:
- Name: {app2_data['name']}
- Description: {app2_data['description']}
- Type: {app2_data['application_type']}
- Criticality: {app2_data['criticality']}
- Business Domain: {app2_data['business_domain']}
- Owner Team: {app2_data['owner_team']}
- Annual Cost: ${app2_data.get('annual_cost', 0):,}
- Technology Stack: {app2_data['technology_stack']}
- Integration Count: {app2_data.get('integration_count', 0)}

Business Capabilities:
{app2_caps if app2_caps else '  - No capabilities specified'}

Business Processes:
{app2_processes if app2_processes else '  - No processes specified'}

User Communities: {', '.join(app2_data.get('user_communities', []))}

ANALYSIS CRITERIA:
1. **Functional Overlap**: Do they support the same business processes and capabilities?
2. **Technical Similarity**: Do they use similar technology stacks and architectures?
3. **User Community Overlap**: Do they serve the same user groups?
4. **Data Model Overlap**: Do they work with similar data structures?
5. **Integration Complexity**: How complex would consolidation be?
6. **Cost Impact**: What are the potential cost savings?

CONSOLIDATION SCENARIOS:
- **MERGE**: Combine into a single application (high overlap, similar tech)
- **RETIRE**: One app can be absorbed by the other (functional subset)
- **STANDARDIZE**: Keep both but standardize on common platform
- **KEEP BOTH**: Low overlap, different purposes, or high complexity

POTENTIAL SAVINGS: ${potential_savings:,.0f} annually (30% of combined costs assumed)

Provide a JSON response with this structure:
{{
    "capability_overlap_score": <0 - 100>,
    "technology_similarity_score": <0 - 100>,
    "functional_similarity_score": <0 - 100>,
    "data_similarity_score": <0 - 100>,
    "user_overlap_score": <0 - 100>,
    "business_domain_match": <0 - 100>,
    "shared_capabilities": ["capability1", "capability2"],
    "shared_technologies": ["tech1", "tech2"],
    "shared_user_types": ["user_type1"],
    "shared_business_processes": ["process1"],
    "recommended_action": "<merge|retire_app1|retire_app2|standardize|keep_both>",
    "recommended_survivor_id": <app_id or null>,
    "estimated_cost_savings": <number>,
    "consolidation_complexity": "<simple|moderate|complex|critical>",
    "data_migration_required": <true|false>,
    "user_migration_required": <true|false>,
    "integration_changes_required": <true|false>,
    "blocking_dependencies": ["dependency1"],
    "reasoning": "<detailed explanation>",
    "confidence_score": <0.0 - 1.0>
}}

SCORING GUIDELINES:
- 70 - 100: High similarity, strong consolidation candidate
- 50 - 69: Medium similarity, consider standardization
- 30 - 49: Low similarity, keep separate
- 0 - 29: No meaningful overlap

BE REALISTIC about consolidation complexity and savings. Don't recommend consolidation unless there's clear business value.
"""

    def _parse_similarity_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM response into structured similarity data."""
        try:
            # Try to extract JSON from response
            import re

            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                # Validate and sanitize the response
                validated_data = self._validate_and_sanitize_response(data)
                return validated_data
        except Exception as e:
            logger.warning(f"Failed to parse LLM response as JSON: {response_text[:200]}")
            logger.warning(f"Parse error: {e}")

        # Fallback: try parsing entire response as JSON
        try:
            data = json.loads(response_text)
            return self._validate_and_sanitize_response(data)
        except Exception as e:
            logger.warning(f"Failed to parse entire response as JSON: {e}")
            # Return default structure
            return {
                "capability_overlap_score": 0,
                "technology_similarity_score": 0,
                "functional_similarity_score": 0,
                "data_similarity_score": 0,
                "user_overlap_score": 0,
                "business_domain_match": 0,
                "shared_capabilities": [],
                "shared_technologies": [],
                "shared_user_types": [],
                "shared_business_processes": [],
                "recommended_action": "keep_both",
                "recommended_survivor_id": None,
                "estimated_cost_savings": 0,
                "consolidation_complexity": "moderate",
                "data_migration_required": False,
                "user_migration_required": False,
                "integration_changes_required": False,
                "blocking_dependencies": [],
                "reasoning": "Unable to parse AI analysis response",
                "confidence_score": 0.0,
            }

    def _validate_and_sanitize_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize LLM response data."""
        sanitized = data.copy()

        # Ensure all required fields exist with proper types
        sanitized.setdefault("capability_overlap_score", 0)
        sanitized.setdefault("technology_similarity_score", 0)
        sanitized.setdefault("functional_similarity_score", 0)
        sanitized.setdefault("data_similarity_score", 0)
        sanitized.setdefault("user_overlap_score", 0)
        sanitized.setdefault("business_domain_match", 0)
        sanitized.setdefault("shared_capabilities", [])
        sanitized.setdefault("shared_technologies", [])
        sanitized.setdefault("shared_user_types", [])
        sanitized.setdefault("shared_business_processes", [])
        sanitized.setdefault("recommended_action", "keep_both")
        sanitized.setdefault("recommended_survivor_id", None)
        sanitized.setdefault("estimated_cost_savings", 0)
        sanitized.setdefault("consolidation_complexity", "moderate")
        sanitized.setdefault("data_migration_required", False)
        sanitized.setdefault("user_migration_required", False)
        sanitized.setdefault("integration_changes_required", False)
        sanitized.setdefault("blocking_dependencies", [])
        sanitized.setdefault("reasoning", "")
        sanitized.setdefault("confidence_score", 0.5)

        # Validate score ranges
        for score_field in [
            "capability_overlap_score",
            "technology_similarity_score",
            "functional_similarity_score",
            "data_similarity_score",
            "user_overlap_score",
            "business_domain_match",
        ]:
            sanitized[score_field] = max(0, min(100, int(sanitized[score_field])))

        # Validate confidence score
        sanitized["confidence_score"] = max(0.0, min(1.0, float(sanitized["confidence_score"])))

        # Validate cost savings
        try:
            sanitized["estimated_cost_savings"] = max(0, float(sanitized["estimated_cost_savings"]))
        except (TypeError, ValueError):
            sanitized["estimated_cost_savings"] = 0

        # Validate recommended action
        valid_actions = ["merge", "retire_app1", "retire_app2", "standardize", "keep_both"]
        if sanitized["recommended_action"] not in valid_actions:
            sanitized["recommended_action"] = "keep_both"

        # Ensure lists are actually lists
        for list_field in [
            "shared_capabilities",
            "shared_technologies",
            "shared_user_types",
            "shared_business_processes",
            "blocking_dependencies",
        ]:
            if not isinstance(sanitized[list_field], list):
                sanitized[list_field] = []

        # Validate boolean fields
        for bool_field in [
            "data_migration_required",
            "user_migration_required",
            "integration_changes_required",
        ]:
            sanitized[bool_field] = bool(sanitized[bool_field])

        return sanitized

    def _calculate_overall_similarity(self, similarity_data: Dict[str, Any]) -> int:
        """Calculate weighted overall similarity score."""
        weights = self.SIMILARITY_WEIGHTS

        # Calculate weighted score
        overall = (
            similarity_data.get("capability_overlap_score", 0) * weights["capability_overlap"]
            + similarity_data.get("functional_similarity_score", 0)
            * weights["functional_similarity"]
            + similarity_data.get("technology_similarity_score", 0)
            * weights["technology_similarity"]
            + similarity_data.get("data_similarity_score", 0) * weights["data_similarity"]
            + similarity_data.get("user_overlap_score", 0) * weights["user_overlap"]
        )

        # Apply business domain match as a multiplier
        domain_match = similarity_data.get("business_domain_match", 0) / 100
        overall *= domain_match

        # Round to nearest integer
        return int(round(overall))

    def _determine_consolidation_opportunity(self, overall_score: int) -> str:
        """Determine consolidation opportunity based on overall similarity."""
        if overall_score >= 70:
            return "high"
        elif overall_score >= 50:
            return "medium"
        elif overall_score >= 40:
            return "low"
        else:
            return "none"

    # =========================================================================
    # Gap-Driven Reuse Analysis Methods (PRD: LLM-Driven Gap Analysis)
    # =========================================================================

    def find_reuse_candidates_for_gap(
        self, gap: Dict[str, Any], threshold: float = 0.6, max_candidates: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find applications that could be extended/reused to address a specific gap.

        This method supports the "Discovery and Reuse-First Planning" requirement
        from the PRD by searching existing applications that could address a gap
        before recommending building new solutions.

        Args:
            gap: Gap dictionary from GapDiscoveryService or CapabilityGapAnalysisService
                 containing: capability_id, capability_name, gap_type, severity, etc.
            threshold: Minimum capability overlap score (0.0 - 1.0) to consider as candidate
            max_candidates: Maximum number of candidates to return

        Returns:
            List of candidate dictionaries with:
            - application_id, name, description
            - similarity_score (0.0 - 1.0)
            - reuse_type: 'full_reuse' | 'extension' | 'partial_reuse'
            - capability_overlap: list of shared capabilities
            - extension_effort_estimate: 'low' | 'medium' | 'high'
            - rationale: LLM-generated explanation
        """
        candidates = []

        # Extract gap information
        capability_id = gap.get("capability_id")
        capability_name = gap.get("capability_name", "")
        gap_type = gap.get("gap_type", "unknown")
        domain = gap.get("domain", "")

        logger.info(f"Finding reuse candidates for gap: {capability_name} ({gap_type})")

        # Get the target capability if available
        target_capability = None
        if capability_id:
            target_capability = BusinessCapability.query.get(capability_id)

        # Get all active applications
        applications = ApplicationComponent.query.filter(
            ApplicationComponent.deployment_status.in_(["production", "active", "deployed", None])
        ).all()

        for app in applications:
            try:
                # Calculate capability overlap
                overlap_score, shared_capabilities = self._calculate_capability_overlap_for_gap(
                    app, target_capability, gap
                )

                # Skip if below threshold
                if overlap_score < threshold:
                    continue

                # Calculate technology compatibility
                tech_compatibility = self._calculate_tech_compatibility_for_gap(app, gap)

                # Determine reuse type based on overlap and compatibility
                reuse_type = self._determine_reuse_type(overlap_score, tech_compatibility, gap)

                # Estimate extension effort
                effort_estimate = self._estimate_extension_effort(
                    app, gap, overlap_score, tech_compatibility
                )

                # Generate rationale (lightweight, no LLM call here)
                rationale = self._generate_lightweight_rationale(
                    app, gap, overlap_score, shared_capabilities, reuse_type
                )

                candidates.append(
                    {
                        "application_id": app.id,
                        "application_name": app.name,
                        "application_description": app.description or "",
                        "application_type": app.application_type or "",
                        "technology_stack": app.technology_stack or "",
                        "owner_team": getattr(app, "owner_team", ""),  # model-safety-ok: optional field (not on all ApplicationComponent variants)
                        "similarity_score": round(overlap_score, 2),
                        "tech_compatibility_score": round(tech_compatibility, 2),
                        "reuse_type": reuse_type,
                        "capability_overlap": shared_capabilities,
                        "extension_effort_estimate": effort_estimate,
                        "rationale": rationale,
                        "gap_id": gap.get("id"),
                        "gap_type": gap_type,
                        "capability_id": capability_id,
                    }
                )

            except Exception as e:
                logger.warning(f"Error analyzing app {app.id} for gap reuse: {e}")
                continue

        # Sort by similarity score (descending) and limit results
        candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
        candidates = candidates[:max_candidates]

        logger.info(f"Found {len(candidates)} reuse candidates for gap: {capability_name}")

        return candidates

    def _calculate_capability_overlap_for_gap(
        self,
        app: ApplicationComponent,
        target_capability: Optional[BusinessCapability],
        gap: Dict[str, Any],
    ) -> Tuple[float, List[str]]:
        """
        Calculate capability overlap between an application and a gap's target capability.

        Returns:
            Tuple of (overlap_score, list of shared capability names)
        """
        shared_capabilities = []

        # Get application's capabilities
        app_capabilities = []
        try:
            capability_mappings = ApplicationCapabilityMapping.query.filter_by(
                application_component_id=app.id
            ).all()
            for mapping in capability_mappings:
                if mapping.capability:
                    app_capabilities.append(mapping.capability)
        except Exception as e:
            logger.warning(f"Error getting capabilities for app {app.id}: {e}")

        if not app_capabilities:
            return 0.0, []

        # Check for direct capability match
        if target_capability:
            for cap in app_capabilities:
                if cap.id == target_capability.id:
                    shared_capabilities.append(cap.name)
                    return 1.0, shared_capabilities

                # Check for parent/child relationship
                if target_capability.parent_capability_id == cap.id:
                    shared_capabilities.append(f"{cap.name} (parent)")
                    return 0.85, shared_capabilities

                if cap.parent_capability_id == target_capability.id:
                    shared_capabilities.append(f"{cap.name} (child of target)")
                    return 0.75, shared_capabilities

        # Check for same-domain capabilities
        gap_domain = gap.get("domain", "").lower()
        domain_matches = 0

        for cap in app_capabilities:
            cap_domain = self._get_capability_domain(cap).lower()
            if gap_domain and cap_domain and gap_domain in cap_domain:
                domain_matches += 1
                shared_capabilities.append(f"{cap.name} (same domain)")

        if domain_matches > 0:
            # Score based on domain matches
            overlap_score = min(0.7, 0.3 + (domain_matches * 0.1))
            return overlap_score, shared_capabilities

        # Check for functional similarity via name/description matching
        gap_keywords = self._extract_keywords(gap.get("capability_name", ""))
        gap_keywords.update(self._extract_keywords(gap.get("gap_description", "")))

        for cap in app_capabilities:
            cap_keywords = self._extract_keywords(cap.name)
            cap_keywords.update(self._extract_keywords(cap.description or ""))

            overlap = gap_keywords.intersection(cap_keywords)
            if len(overlap) >= 2:
                shared_capabilities.append(
                    f"{cap.name} (keyword match: {', '.join(list(overlap)[:3])})"
                )

        if shared_capabilities:
            return min(0.5, len(shared_capabilities) * 0.15), shared_capabilities

        return 0.0, []

    def _get_capability_domain(self, capability: BusinessCapability) -> str:
        """Get the domain (Level 0 capability) for a capability."""
        if capability.level == 0 or not capability.parent_capability_id:
            return capability.name

        current = capability
        while current.parent_capability_id:
            parent = db.session.get(BusinessCapability, current.parent_capability_id)
            if not parent:
                break
            if parent.level == 0 or not parent.parent_capability_id:
                return parent.name
            current = parent

        return current.name

    def _extract_keywords(self, text: str) -> set:
        """Extract meaningful keywords from text."""
        if not text:
            return set()

        # Common words to exclude
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "been",
            "be",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "need",
            "application",
            "system",
            "service",
            "platform",
            "tool",
            "process",
            "management",
            "support",
            "capability",
            "gap",
            "no",
            "not",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
        }

        # Extract words and filter
        words = set(word.lower() for word in text.split() if len(word) > 2)
        return words - stopwords

    def _calculate_tech_compatibility_for_gap(
        self, app: ApplicationComponent, gap: Dict[str, Any]
    ) -> float:
        """
        Calculate technology compatibility score for extending an application.

        Higher scores indicate the application uses modern, extensible technologies.
        """
        tech_stack = app.technology_stack or ""
        tech_stack_lower = tech_stack.lower()

        # Modern, extensible technologies
        modern_tech = {
            "api": 0.15,
            "rest": 0.15,
            "graphql": 0.15,
            "microservice": 0.2,
            "cloud": 0.15,
            "aws": 0.1,
            "azure": 0.1,
            "gcp": 0.1,
            "docker": 0.1,
            "kubernetes": 0.15,
            "k8s": 0.15,
            "react": 0.1,
            "angular": 0.1,
            "vue": 0.1,
            "python": 0.1,
            "java": 0.1,
            "node": 0.1,
            ".net": 0.1,
            "spring": 0.1,
            "django": 0.1,
            "flask": 0.1,
        }

        # Legacy technologies (reduce score)
        legacy_tech = {
            "mainframe": -0.3,
            "cobol": -0.3,
            "vb6": -0.2,
            "classic asp": -0.2,
            "powerbuilder": -0.2,
        }

        score = 0.5  # Base score

        for tech, weight in modern_tech.items():
            if tech in tech_stack_lower:
                score += weight

        for tech, weight in legacy_tech.items():
            if tech in tech_stack_lower:
                score += weight

        # Clamp to 0.0 - 1.0
        return max(0.0, min(1.0, score))

    def _determine_reuse_type(
        self, overlap_score: float, tech_compatibility: float, gap: Dict[str, Any]
    ) -> str:
        """
        Determine the type of reuse recommended.

        Returns:
            'full_reuse': Application fully addresses the gap
            'extension': Application can be extended to address the gap
            'partial_reuse': Only partial functionality can be reused
        """
        if overlap_score >= 0.9 and tech_compatibility >= 0.6:
            return "full_reuse"
        elif overlap_score >= 0.6 and tech_compatibility >= 0.5:
            return "extension"
        else:
            return "partial_reuse"

    def _estimate_extension_effort(
        self,
        app: ApplicationComponent,
        gap: Dict[str, Any],
        overlap_score: float,
        tech_compatibility: float,
    ) -> str:
        """
        Estimate effort required to extend application to address gap.

        Returns:
            'low': Minor configuration or integration work
            'medium': Moderate development effort
            'high': Significant development required
        """
        # Base effort calculation
        effort_score = (1 - overlap_score) + (1 - tech_compatibility)

        # Adjust for gap severity
        severity = gap.get("severity", "medium").lower()
        if severity == "critical":
            effort_score += 0.3  # Critical gaps often need more thorough solutions
        elif severity == "low":
            effort_score -= 0.2

        # Adjust for integration complexity
        integration_count = self._get_integration_count(app.id)
        if integration_count > 10:
            effort_score += 0.2  # High integration complexity

        if effort_score < 0.5:
            return "low"
        elif effort_score < 1.0:
            return "medium"
        else:
            return "high"

    def _generate_lightweight_rationale(
        self,
        app: ApplicationComponent,
        gap: Dict[str, Any],
        overlap_score: float,
        shared_capabilities: List[str],
        reuse_type: str,
    ) -> str:
        """
        Generate a brief rationale without LLM call (for performance).
        Full LLM rationale is generated in generate_reuse_vs_build_recommendation.
        """
        capability_name = gap.get("capability_name", "the capability")

        if reuse_type == "full_reuse":
            return (
                f"Application '{app.name}' already supports capabilities closely related to "
                f"'{capability_name}'. Shared capabilities: {', '.join(shared_capabilities[:3])}. "
                f"Consider direct reuse with minimal configuration."
            )
        elif reuse_type == "extension":
            return (
                f"Application '{app.name}' can be extended to support '{capability_name}'. "
                f"It shares {len(shared_capabilities)} related capabilities. "
                f"Extension recommended over building new."
            )
        else:
            return (
                f"Application '{app.name}' provides partial coverage for '{capability_name}'. "
                f"Consider integration or partial reuse of its components."
            )

    def generate_reuse_vs_build_recommendation(
        self, gap: Dict[str, Any], candidates: List[Dict[str, Any]], user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Use LLM to analyze candidates and recommend reuse vs build new.

        This method supports the "Discovery and Reuse-First Planning" and
        "Solution Design" requirements from the PRD by providing AI-powered
        recommendations with full cost-benefit analysis.

        Args:
            gap: Gap dictionary from gap analysis services
            candidates: List of reuse candidates from find_reuse_candidates_for_gap()
            user_id: User ID for LLM cost tracking

        Returns:
            Dictionary with:
            - recommendation: 'reuse' | 'extend' | 'replace' | 'build_new'
            - recommended_application_id: ID if reuse/extend (None if build_new)
            - confidence_score: 0.0 - 1.0
            - rationale: detailed explanation
            - cost_comparison: estimated costs for each option
            - implementation_approach: recommended implementation strategy
            - risks: list of risks for recommended approach
            - alternatives: list of alternative approaches
        """
        logger.info(
            f"Generating reuse vs build recommendation for gap: {gap.get('capability_name')}"
        )

        # Build prompt for LLM analysis
        prompt = self._build_reuse_recommendation_prompt(gap, candidates)

        try:
            # Get configured provider and model
            provider_name, model = LLMService._get_configured_provider()

            # Call LLM
            response_text, interaction = LLMService._call_llm(
                prompt=prompt,
                model=model,
                provider=provider_name,
                user_id=user_id,
                project_id=None,
                max_tokens=4000,
            )

            # Parse and validate response
            recommendation = self._parse_reuse_recommendation_response(
                response_text, gap, candidates
            )

            logger.info(
                f"Recommendation for '{gap.get('capability_name')}': "
                f"{recommendation['recommendation']} "
                f"(confidence: {recommendation['confidence_score']})"
            )

            return recommendation

        except Exception as e:
            logger.error(f"Error generating reuse recommendation: {e}")
            # Return fallback recommendation
            return self._generate_fallback_recommendation(gap, candidates)

    def _build_reuse_recommendation_prompt(
        self, gap: Dict[str, Any], candidates: List[Dict[str, Any]]
    ) -> str:
        """Build LLM prompt for reuse vs build recommendation."""

        # Format gap information
        gap_info = f"""
GAP INFORMATION:
- Capability: {gap.get('capability_name', 'Unknown')}
- Description: {gap.get('capability_description', gap.get('gap_description', 'No description'))}
- Domain: {gap.get('domain', 'Unknown')}
- Gap Type: {gap.get('gap_type', 'Unknown')}
- Severity: {gap.get('severity', 'medium')}
- Current Coverage: {gap.get('current_coverage', 0)}%
- Strategic Importance: {gap.get('strategic_importance', 'medium')}
"""

        # Format candidates
        if candidates:
            candidates_info = "\nREUSE CANDIDATES:\n"
            for i, candidate in enumerate(candidates[:5], 1):  # Limit to top 5
                candidates_info += f"""
Candidate {i}: {candidate['application_name']}
- Application ID: {candidate['application_id']}
- Description: {candidate['application_description'][:200]}...
- Technology Stack: {candidate['technology_stack']}
- Owner Team: {candidate['owner_team']}
- Similarity Score: {candidate['similarity_score'] * 100:.0f}%
- Tech Compatibility: {candidate['tech_compatibility_score'] * 100:.0f}%
- Suggested Reuse Type: {candidate['reuse_type']}
- Extension Effort: {candidate['extension_effort_estimate']}
- Shared Capabilities: {', '.join(candidate['capability_overlap'][:5])}
"""
        else:
            candidates_info = "\nNO REUSE CANDIDATES FOUND (similarity threshold not met)\n"

        return f"""You are an expert Enterprise Architect analyzing a capability gap and potential solutions.

{gap_info}
{candidates_info}

TASK: Recommend the best approach to address this gap:
1. REUSE - Use an existing application as-is with configuration only
2. EXTEND - Extend an existing application with new features
3. REPLACE - Replace an existing inadequate application with a better one
4. BUILD_NEW - Build a new application from scratch

EVALUATION CRITERIA:
- Cost efficiency (reuse/extend is typically 30 - 70% cheaper than build new)
- Time to value (reuse/extend is faster)
- Technical fit (does the technology stack align?)
- Organizational fit (does the owner team have capacity?)
- Risk (reuse carries less risk than building new)
- Strategic alignment (does this align with enterprise architecture goals?)

Provide a JSON response:
{{
    "recommendation": "<reuse|extend|replace|build_new>",
    "recommended_application_id": <app_id or null>,
    "recommended_application_name": "<name or null>",
    "confidence_score": <0.0 - 1.0>,
    "rationale": "<detailed explanation of the recommendation>",
    "cost_comparison": {{
        "reuse_estimated_cost": <number or null>,
        "extend_estimated_cost": <number or null>,
        "build_new_estimated_cost": <number or null>,
        "cost_savings_percentage": <percentage saved by recommended approach>
    }},
    "implementation_approach": "<step-by-step implementation strategy>",
    "estimated_effort_weeks": <number>,
    "risks": ["risk1", "risk2"],
    "alternatives": [
        {{"option": "<option>", "description": "<why this is alternative>"}}
    ],
    "success_criteria": "<how to measure success>",
    "dependencies": ["dependency1", "dependency2"]
}}

IMPORTANT:
- Prefer REUSE or EXTEND when candidates have similarity score >= 60%
- Recommend BUILD_NEW only when no suitable candidates exist OR all candidates are unsuitable
- Be specific about which application to use if recommending reuse/extend
- Provide realistic cost estimates in USD
"""

    def _parse_reuse_recommendation_response(
        self, response_text: str, gap: Dict[str, Any], candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Parse and validate LLM response for reuse recommendation."""
        try:
            # Extract JSON from response
            import re

            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return self._validate_reuse_recommendation(data, gap, candidates)
        except Exception as e:
            logger.warning(f"Failed to parse reuse recommendation response: {e}")

        # Fallback
        return self._generate_fallback_recommendation(gap, candidates)

    def _validate_reuse_recommendation(
        self, data: Dict[str, Any], gap: Dict[str, Any], candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate and sanitize recommendation data."""
        validated = {}

        # Validate recommendation type
        valid_recommendations = ["reuse", "extend", "replace", "build_new"]
        recommendation = str(data.get("recommendation", "build_new")).lower()
        if recommendation not in valid_recommendations:
            recommendation = "build_new"
        validated["recommendation"] = recommendation

        # Validate application ID if reuse/extend
        app_id = data.get("recommended_application_id")
        if recommendation in ["reuse", "extend"] and app_id:
            # Verify the app ID is in our candidates
            valid_ids = [c["application_id"] for c in candidates]
            if app_id not in valid_ids and candidates:
                app_id = candidates[0]["application_id"]  # Use top candidate
        elif recommendation in ["reuse", "extend"] and candidates:
            app_id = candidates[0]["application_id"]
        else:
            app_id = None
        validated["recommended_application_id"] = app_id

        validated["recommended_application_name"] = data.get("recommended_application_name")

        # Validate confidence score
        try:
            confidence = float(data.get("confidence_score", 0.5))
            validated["confidence_score"] = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            validated["confidence_score"] = 0.5

        # Copy other fields with defaults
        validated["rationale"] = str(
            data.get("rationale", "Analysis based on capability overlap and technology fit.")
        )

        validated["cost_comparison"] = data.get(
            "cost_comparison",
            {
                "reuse_estimated_cost": None,
                "extend_estimated_cost": None,
                "build_new_estimated_cost": None,
                "cost_savings_percentage": 0,
            },
        )

        validated["implementation_approach"] = str(
            data.get(
                "implementation_approach",
                "Standard implementation approach based on enterprise architecture patterns.",
            )
        )

        try:
            validated["estimated_effort_weeks"] = int(data.get("estimated_effort_weeks", 8))
        except (TypeError, ValueError):
            validated["estimated_effort_weeks"] = 8

        validated["risks"] = data.get("risks", [])
        if not isinstance(validated["risks"], list):
            validated["risks"] = []

        validated["alternatives"] = data.get("alternatives", [])
        if not isinstance(validated["alternatives"], list):
            validated["alternatives"] = []

        validated["success_criteria"] = str(
            data.get(
                "success_criteria",
                f"Gap closed with {gap.get('capability_name', 'capability')} fully supported.",
            )
        )

        validated["dependencies"] = data.get("dependencies", [])
        if not isinstance(validated["dependencies"], list):
            validated["dependencies"] = []

        # Add gap context
        validated["gap_id"] = gap.get("id")
        validated["gap_type"] = gap.get("gap_type")
        validated["capability_id"] = gap.get("capability_id")
        validated["capability_name"] = gap.get("capability_name")

        return validated

    def _generate_fallback_recommendation(
        self, gap: Dict[str, Any], candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate fallback recommendation when LLM fails."""

        # Simple heuristic-based recommendation
        if candidates and candidates[0]["similarity_score"] >= 0.7:
            recommendation = "reuse" if candidates[0]["reuse_type"] == "full_reuse" else "extend"
            app_id = candidates[0]["application_id"]
            app_name = candidates[0]["application_name"]
            rationale = (
                f"Based on capability analysis, '{app_name}' shows strong alignment "
                f"(similarity: {candidates[0]['similarity_score']*100:.0f}%) with the gap requirements."
            )
        elif candidates and candidates[0]["similarity_score"] >= 0.5:
            recommendation = "extend"
            app_id = candidates[0]["application_id"]
            app_name = candidates[0]["application_name"]
            rationale = (
                f"'{app_name}' provides partial coverage and can be extended to address the gap."
            )
        else:
            recommendation = "build_new"
            app_id = None
            app_name = None
            rationale = (
                "No suitable existing applications found with sufficient capability overlap. "
                "Building a new solution is recommended."
            )

        return {
            "recommendation": recommendation,
            "recommended_application_id": app_id,
            "recommended_application_name": app_name,
            "confidence_score": 0.6,
            "rationale": rationale,
            "cost_comparison": {
                "reuse_estimated_cost": None,
                "extend_estimated_cost": None,
                "build_new_estimated_cost": None,
                "cost_savings_percentage": 30 if recommendation != "build_new" else 0,
            },
            "implementation_approach": "Manual analysis required to determine detailed implementation approach.",
            "estimated_effort_weeks": 8,
            "risks": ["Recommendation generated without full LLM analysis"],
            "alternatives": [],
            "success_criteria": f"Gap closed with {gap.get('capability_name', 'capability')} supported.",
            "dependencies": [],
            "gap_id": gap.get("id"),
            "gap_type": gap.get("gap_type"),
            "capability_id": gap.get("capability_id"),
            "capability_name": gap.get("capability_name"),
        }
