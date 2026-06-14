"""
APQC Extraction Agent

Intelligent agent for extracting and mapping business processes
to APQC PCF hierarchy.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import db
from app.models.apqc_process import APQCProcess, ProcessApplicationMapping
from app.services.llm_service import LLMService
from app.services.unified_apqc_service import (
    APQCClassificationResult,
    APQCMatch,
    get_unified_apqc_service,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractedProcess:
    """Represents an extracted business process."""

    name: str
    description: str
    process_type: str  # core, support, management
    suggested_apqc_codes: List[str]
    confidence_score: float
    source: str


@dataclass
class ProcessGap:
    """Represents a gap in process coverage."""

    apqc_code: str
    apqc_name: str
    gap_type: str  # missing, partial, outdated
    severity: str  # high, medium, low
    recommendation: str


class APQCExtractionAgent:
    """
    Intelligent agent for APQC process extraction and mapping.

    Uses semantic search and LLM to:
    1. Extract processes from text/documents
    2. Map processes to APQC PCF hierarchy
    3. Identify process-capability relationships
    4. Suggest process improvements
    """

    AGENT_NAME = "apqc_extraction"
    AGENT_DEPENDENCIES = ["capability_discovery"]

    def __init__(self, user_id: Optional[int] = None):
        self.llm_service = LLMService()
        self.unified_apqc = get_unified_apqc_service()  # Use unified service
        self.user_id = user_id

    async def extract_processes_from_text(
        self, text: str, context: Dict[str, Any] = None
    ) -> List[ExtractedProcess]:
        """Extract business processes from unstructured text."""
        context = context or {}

        prompt = f"""Analyze this text and extract business processes.

TEXT:
"{text}"

CONTEXT:
{json.dumps(context, indent=2)}

For each process found, provide:
1. name: Clear process name
2. description: What this process does
3. process_type: core (value-creating), support (enabling), management (governance)
4. suggested_apqc_codes: Likely APQC PCF codes (e.g., ["4.1", "4.2.1"])
5. confidence_score: 0.0 - 1.0

APQC CATEGORIES:
1.0 Strategy & Planning
2.0 Product Development
3.0 Marketing & Sales
4.0 Supply Chain
5.0 Operations/Manufacturing
6.0 Human Resources
7.0 Information Technology
8.0 Finance
9.0 Facilities & Assets
10.0 Enterprise Risk
11.0 External Relations
12.0 Knowledge Management
13.0 Emergency Management

RESPOND WITH JSON:
{{
    "processes": [
        {{
            "name": "...",
            "description": "...",
            "process_type": "core",
            "suggested_apqc_codes": ["4.1", "4.1.1"],
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
            processes = []

            for proc in parsed.get("processes", []):
                processes.append(
                    ExtractedProcess(
                        name=proc.get("name", ""),
                        description=proc.get("description", ""),
                        process_type=proc.get("process_type", "support"),
                        suggested_apqc_codes=proc.get("suggested_apqc_codes", []),
                        confidence_score=proc.get("confidence_score", 0.5),
                        source="text_extraction",
                    )
                )

            return processes

        except Exception as e:
            logger.error(f"Error extracting processes: {e}")
            return []

    async def map_to_apqc(self, process_description: str) -> List[APQCClassificationResult]:
        """Map process to APQC PCF using semantic matching."""
        # Use synchronous unified service (no async needed)
        results = self.unified_apqc.classify(text=process_description, top_k=5)
        return results

    async def link_process_to_capabilities(self, apqc_process_id: int) -> List[Dict[str, Any]]:
        """Suggest capability-process relationships."""
        from app.models.business_capabilities import BusinessCapability

        process = db.session.get(APQCProcess, apqc_process_id)
        if not process:
            return []

        # Get capabilities that might relate
        capabilities = BusinessCapability.query.limit(50).all()

        # Build context for LLM
        cap_list = [{"id": c.id, "name": c.name} for c in capabilities]

        prompt = f"""Which capabilities support this APQC process?

PROCESS:
Code: {process.process_code}
Name: {process.process_name}
Category: {process.category_level_1}

CAPABILITIES:
{json.dumps(cap_list, indent=2)}

RESPOND WITH JSON:
{{
    "capability_links": [
        {{"capability_id": 123, "relationship_type": "enables", "confidence": 0.8}}
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
            return parsed.get("capability_links", [])

        except Exception as e:
            logger.error(f"Error linking capabilities: {e}")
            return []

    async def analyze_process_gaps(self, capability_id: int) -> List[ProcessGap]:
        """Identify missing processes for a capability."""
        from app.models.business_capabilities import BusinessCapability

        capability = db.session.get(BusinessCapability, capability_id)
        if not capability:
            return []

        # Get existing process mappings
        existing_mappings = ProcessApplicationMapping.query.filter(
            ProcessApplicationMapping.application_id == capability_id
        ).all()
        existing_codes = [m.apqc_process.process_code for m in existing_mappings if m.apqc_process]

        # Use LLM to identify gaps
        prompt = f"""Analyze this capability and identify missing APQC processes.

CAPABILITY:
Name: {capability.name}
Description: {capability.description or 'Not provided'}

EXISTING PROCESS MAPPINGS:
{', '.join(existing_codes) if existing_codes else 'None'}

What APQC processes are missing that this capability should support?

RESPOND WITH JSON:
{{
    "gaps": [
        {{
            "apqc_code": "4.1.1",
            "apqc_name": "Process name",
            "gap_type": "missing",
            "severity": "high",
            "recommendation": "..."
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
            gaps = []

            for gap in parsed.get("gaps", []):
                gaps.append(
                    ProcessGap(
                        apqc_code=gap.get("apqc_code", ""),
                        apqc_name=gap.get("apqc_name", ""),
                        gap_type=gap.get("gap_type", "missing"),
                        severity=gap.get("severity", "medium"),
                        recommendation=gap.get("recommendation", ""),
                    )
                )

            return gaps

        except Exception as e:
            logger.error(f"Error analyzing gaps: {e}")
            return []

    def run_sync(self, text: str) -> List[Dict[str, Any]]:
        """Synchronous wrapper for extract_processes_from_text."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        processes = loop.run_until_complete(self.extract_processes_from_text(text))
        return [
            {
                "name": p.name,
                "description": p.description,
                "process_type": p.process_type,
                "suggested_apqc_codes": p.suggested_apqc_codes,
                "confidence_score": p.confidence_score,
                "source": p.source,
            }
            for p in processes
        ]
