"""
Gap Analysis Agent

Intelligent agent for comprehensive gap analysis and recommendations
across capabilities, technology, and processes.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import db
from app.models.traceability import ImpactAnalysisResult
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


@dataclass
class Gap:
    """Represents an identified gap."""

    gap_type: str  # capability, technology, process, integration
    entity_type: str
    entity_id: Optional[int]
    entity_name: str
    description: str
    severity: str  # critical, high, medium, low
    business_impact: str
    recommended_action: str


@dataclass
class Recommendation:
    """Prioritized recommendation for gap remediation."""

    priority: int
    title: str
    description: str
    effort_level: str  # low, medium, high
    related_gaps: List[str]
    expected_benefit: str


@dataclass
class RemediationRoadmap:
    """Phased roadmap for gap remediation."""

    phases: List[Dict[str, Any]]
    total_gaps_addressed: int
    estimated_completion: str


class GapAnalysisAgent:
    """
    Intelligent agent for comprehensive gap analysis and recommendations.

    Builds on existing GapDiscoveryService with LLM-powered analysis:
    1. Identify capability gaps
    2. Identify technology gaps
    3. Identify process gaps
    4. Generate prioritized recommendations
    """

    AGENT_NAME = "gap_analysis"
    AGENT_DEPENDENCIES = ["capability_discovery", "archimate_mapping", "apqc_extraction"]

    def __init__(self, user_id: Optional[int] = None):
        self.llm_service = LLMService()
        self.user_id = user_id

    async def analyze_capability_gaps(self, architecture_id: int = None) -> Dict[str, Any]:
        """Comprehensive capability gap analysis with LLM insights."""
        from app.models.application_portfolio import ApplicationComponent
        from app.models.business_capabilities import BusinessCapability

        # Get capabilities and applications
        capabilities = BusinessCapability.query.limit(100).all()
        # Get active applications (architecture_id param reserved for future use)
        applications = (
            ApplicationComponent.query.filter(
                ApplicationComponent.lifecycle_status.in_(
                    ["active", "production", "Active", "Production", None]
                )
            )
            .limit(100)
            .all()
        )

        cap_data = [
            {"id": c.id, "name": c.name, "maturity": getattr(c, "current_maturity_level", None)}
            for c in capabilities
        ]
        app_data = [
            {"id": a.id, "name": a.name, "status": a.lifecycle_status} for a in applications
        ]

        prompt = f"""Analyze capability and application alignment for gaps.

CAPABILITIES ({len(capabilities)}):
{json.dumps(cap_data[:20], indent=2)}

APPLICATIONS ({len(applications)}):
{json.dumps(app_data[:20], indent=2)}

Identify:
1. Capabilities without supporting applications
2. Applications without clear capability alignment
3. Low maturity capabilities needing investment
4. Redundant capabilities/applications

RESPOND WITH JSON:
{{
    "gaps": [
        {{
            "gap_type": "capability",
            "entity_name": "...",
            "description": "...",
            "severity": "high",
            "business_impact": "...",
            "recommended_action": "..."
        }}
    ],
    "summary": {{
        "total_gaps": 5,
        "critical_gaps": 1,
        "high_gaps": 2,
        "coverage_score": 75
    }}
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
            logger.error(f"Error analyzing capability gaps: {e}")
            return {"gaps": [], "summary": {"error": str(e)}}

    async def generate_recommendations(self, gaps: List[Gap]) -> List[Recommendation]:
        """Generate prioritized recommendations using LLM."""
        gap_data = [
            {
                "type": g.gap_type,
                "name": g.entity_name,
                "severity": g.severity,
                "impact": g.business_impact,
            }
            for g in gaps[:15]
        ]

        prompt = f"""Generate prioritized recommendations for these gaps.

GAPS:
{json.dumps(gap_data, indent=2)}

Create recommendations that:
1. Address multiple gaps where possible
2. Prioritize by business impact
3. Consider implementation effort
4. Provide clear benefits

RESPOND WITH JSON:
{{
    "recommendations": [
        {{
            "priority": 1,
            "title": "...",
            "description": "...",
            "effort_level": "medium",
            "related_gaps": ["gap names"],
            "expected_benefit": "..."
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
            recommendations = []

            for rec in parsed.get("recommendations", []):
                recommendations.append(
                    Recommendation(
                        priority=rec.get("priority", 99),
                        title=rec.get("title", ""),
                        description=rec.get("description", ""),
                        effort_level=rec.get("effort_level", "medium"),
                        related_gaps=rec.get("related_gaps", []),
                        expected_benefit=rec.get("expected_benefit", ""),
                    )
                )

            return sorted(recommendations, key=lambda r: r.priority)

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return []

    async def create_remediation_roadmap(self, gaps: List[Gap]) -> RemediationRoadmap:
        """Create phased roadmap for gap remediation."""
        gap_data = [
            {"name": g.entity_name, "severity": g.severity, "type": g.gap_type} for g in gaps[:20]
        ]

        prompt = f"""Create a phased roadmap to address these gaps.

GAPS:
{json.dumps(gap_data, indent=2)}

Create 3 - 4 phases:
1. Quick Wins (low effort, high impact)
2. Foundation (essential prerequisites)
3. Core Improvements (main gap remediation)
4. Optimization (refinement and enhancement)

RESPOND WITH JSON:
{{
    "phases": [
        {{
            "phase_number": 1,
            "name": "Quick Wins",
            "description": "...",
            "gaps_addressed": ["gap names"],
            "key_activities": ["activity descriptions"]
        }}
    ],
    "total_gaps_addressed": 10,
    "estimated_timeline": "6 - 12 months"
}}"""

        try:
            response = self.llm_service.generate_from_prompt(prompt=prompt)
            cleaned = response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0]

            parsed = json.loads(cleaned)

            return RemediationRoadmap(
                phases=parsed.get("phases", []),
                total_gaps_addressed=parsed.get("total_gaps_addressed", 0),
                estimated_completion=parsed.get("estimated_timeline", "TBD"),
            )

        except Exception as e:
            logger.error(f"Error creating roadmap: {e}")
            return RemediationRoadmap(
                phases=[], total_gaps_addressed=0, estimated_completion="Error"
            )

    async def analyze_impact(
        self, element_type: str, element_id: int, change_type: str
    ) -> ImpactAnalysisResult:
        """Analyze impact of a proposed change."""
        # Get element details
        element_name = f"{element_type}:{element_id}"

        prompt = f"""Analyze the impact of this change.

CHANGE:
Type: {change_type}
Element: {element_type} (ID: {element_id})

Consider impact on:
1. Upstream dependencies
2. Downstream dependents
3. Related capabilities
4. Business processes
5. Applications

RESPOND WITH JSON:
{{
    "overall_severity": "high",
    "affected_capabilities_count": 5,
    "affected_applications_count": 3,
    "affected_processes_count": 8,
    "key_impacts": ["impact descriptions"],
    "risk_factors": ["risk descriptions"],
    "mitigation_suggestions": ["suggestions"]
}}"""

        try:
            response = self.llm_service.generate_from_prompt(prompt=prompt)
            cleaned = response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0]

            parsed = json.loads(cleaned)

            # Create impact analysis result
            result = ImpactAnalysisResult(
                analysis_type=change_type,
                trigger_element_type=element_type,
                trigger_element_id=element_id,
                overall_severity=parsed.get("overall_severity", "medium"),
                affected_capabilities_count=parsed.get("affected_capabilities_count", 0),
                affected_applications_count=parsed.get("affected_applications_count", 0),
                affected_processes_count=parsed.get("affected_processes_count", 0),
                impacted_elements=json.dumps(parsed.get("key_impacts", [])),
                impact_summary=json.dumps(
                    {
                        "risk_factors": parsed.get("risk_factors", []),
                        "mitigation": parsed.get("mitigation_suggestions", []),
                    }
                ),
                created_by_id=self.user_id,
            )

            db.session.add(result)
            db.session.commit()

            return result

        except Exception as e:
            logger.error(f"Error analyzing impact: {e}")
            return ImpactAnalysisResult(
                analysis_type=change_type,
                trigger_element_type=element_type,
                trigger_element_id=element_id,
                overall_severity="unknown",
                impact_summary=json.dumps({"error": str(e)}),
            )

    def run_sync(self, architecture_id: int) -> Dict[str, Any]:
        """Synchronous wrapper for analyze_capability_gaps."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.analyze_capability_gaps(architecture_id))
