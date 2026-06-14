"""
Capability Discovery Agent

Intelligent agent for capability discovery and classification using
semantic search and LLM analysis.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import db
from app.models.business_capabilities import BusinessCapability
from app.models.constants import ArchiMateLayer, CapabilityType
from app.services.llm_service import LLMService
from app.services.vector_embedding_service import VectorEmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredCapability:
    """Represents a discovered capability."""

    name: str
    description: str
    capability_type: str
    archimate_layer: str
    confidence_score: float
    source: str
    suggested_parent_id: Optional[int] = None


@dataclass
class CapabilityClassification:
    """Result of capability classification."""

    capability_type: str
    archimate_layer: str
    archimate_element_type: str
    confidence_score: float
    reasoning: str


class CapabilityDiscoveryAgent:
    """
    Intelligent agent for capability discovery and classification.

    Uses semantic search and LLM to:
    1. Discover capabilities from documents, descriptions, and applications
    2. Classify capabilities by type and ArchiMate layer
    3. Suggest capability hierarchies
    4. Map capabilities to APQC processes
    """

    AGENT_NAME = "capability_discovery"
    AGENT_DEPENDENCIES = []

    def __init__(self, user_id: Optional[int] = None):
        self.llm_service = LLMService()
        self.embedding_service = VectorEmbeddingService()
        self.user_id = user_id

    async def discover_capabilities_from_text(
        self, text: str, context: Dict[str, Any] = None
    ) -> List[DiscoveredCapability]:
        """Extract capabilities from unstructured text using LLM."""
        context = context or {}

        prompt = f"""Analyze this text and extract business capabilities.

TEXT:
"{text}"

CONTEXT:
{json.dumps(context, indent=2)}

For each capability found, provide:
1. name: Clear, concise capability name
2. description: What this capability enables
3. capability_type: One of {CapabilityType.ALL}
4. archimate_layer: One of {ArchiMateLayer.ALL}
5. confidence_score: 0.0 - 1.0

RESPOND WITH JSON:
{{
    "capabilities": [
        {{
            "name": "...",
            "description": "...",
            "capability_type": "...",
            "archimate_layer": "...",
            "confidence_score": 0.85
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
            capabilities = []

            for cap in parsed.get("capabilities", []):
                capabilities.append(
                    DiscoveredCapability(
                        name=cap.get("name", ""),
                        description=cap.get("description", ""),
                        capability_type=cap.get("capability_type", "business"),
                        archimate_layer=cap.get("archimate_layer", "business"),
                        confidence_score=cap.get("confidence_score", 0.5),
                        source="text_extraction",
                    )
                )

            return capabilities

        except Exception as e:
            logger.error(f"Error discovering capabilities: {e}")
            return []

    async def classify_capability(self, capability: BusinessCapability) -> CapabilityClassification:
        """Classify capability type and ArchiMate mapping using semantic matching."""
        text = f"{capability.name} - {capability.description or ''}"

        prompt = f"""Classify this business capability:

CAPABILITY:
Name: {capability.name}
Description: {capability.description or 'Not provided'}

Determine:
1. capability_type: Best match from {CapabilityType.ALL}
2. archimate_layer: Best match from {ArchiMateLayer.ALL}
3. archimate_element_type: Best ArchiMate element type for this capability

RESPOND WITH JSON:
{{
    "capability_type": "...",
    "archimate_layer": "...",
    "archimate_element_type": "...",
    "confidence_score": 0.85,
    "reasoning": "..."
}}"""

        try:
            response = self.llm_service.generate_from_prompt(prompt=prompt)
            cleaned = response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0]

            parsed = json.loads(cleaned)

            return CapabilityClassification(
                capability_type=parsed.get("capability_type", "business"),
                archimate_layer=parsed.get("archimate_layer", "business"),
                archimate_element_type=parsed.get("archimate_element_type", "Capability"),
                confidence_score=parsed.get("confidence_score", 0.7),
                reasoning=parsed.get("reasoning", ""),
            )

        except Exception as e:
            logger.error(f"Error classifying capability: {e}")
            return CapabilityClassification(
                capability_type="business",
                archimate_layer="business",
                archimate_element_type="Capability",
                confidence_score=0.5,
                reasoning="Default classification due to error",
            )

    async def suggest_hierarchy(self, capabilities: List[BusinessCapability]) -> Dict[str, Any]:
        """Suggest parent-child relationships using LLM analysis."""
        cap_list = [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description[:100] if c.description else "",
            }
            for c in capabilities[:20]
        ]

        prompt = f"""Analyze these capabilities and suggest a hierarchy.

CAPABILITIES:
{json.dumps(cap_list, indent=2)}

Suggest parent-child relationships where one capability logically contains or enables another.

RESPOND WITH JSON:
{{
    "hierarchy_suggestions": [
        {{"child_id": 123, "parent_id": 456, "reasoning": "..."}}
    ],
    "root_capabilities": [list of IDs that should be top-level]
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
            logger.error(f"Error suggesting hierarchy: {e}")
            return {"hierarchy_suggestions": [], "root_capabilities": []}

    async def discover_from_applications(self, architecture_id: int) -> List[DiscoveredCapability]:
        """Discover capabilities by analyzing application portfolio."""
        from app.models.application_portfolio import ApplicationComponent

        apps = ApplicationComponent.query.filter_by(architecture_id=architecture_id).limit(50).all()

        discovered = []
        for app in apps:
            text = f"{app.name} - {app.description or ''}"
            if app.business_domain:
                text += f" Domain: {app.business_domain}"

            caps = await self.discover_capabilities_from_text(
                text, context={"application_id": app.id, "application_name": app.name}
            )
            discovered.extend(caps)

        return discovered

    def run_sync(self, text: str) -> List[Dict[str, Any]]:
        """Synchronous wrapper for discover_capabilities_from_text."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        capabilities = loop.run_until_complete(self.discover_capabilities_from_text(text))
        return [
            {
                "name": c.name,
                "description": c.description,
                "capability_type": c.capability_type,
                "archimate_layer": c.archimate_layer,
                "confidence_score": c.confidence_score,
                "source": c.source,
            }
            for c in capabilities
        ]
