"""
Code Spec Inference — LLM-powered field inference for Blueprint-to-Code.

Uses the platform's configured LLM to propose schema fields for each
SolutionAppElement based on:
- Element name and description
- Linked requirements (functional + non-functional)
- Integration flows (upstream/downstream)
- SLAs and quality attributes
- Technology stack

The LLM proposes fields. The architect confirms. Confirmed fields are
saved as code_spec on the element for deterministic future generation.
"""
import json
import logging

logger = logging.getLogger(__name__)

# ── Prompt Template ──────────────────────────────────────────────────────

FIELD_INFERENCE_PROMPT = """You are a senior API architect. Given the following architecture element, its relationships, and full context, propose the data fields for its API schema.

## Solution Context
{solution_brief}

## Element
- **Name:** {element_name}
- **Type:** {element_type}
- **Description:** {description}
- **Technology:** {technology}

## ArchiMate Relationships (what this element connects to)
{relationships_text}

## Requirements
{requirements_text}

## Integration Flows
{flows_text}

## SLAs & Quality Attributes
{sla_text}

{quality_text}

## Linked Capabilities
{capabilities_text}

## Instructions
Propose fields for this element's API schema. For each field, provide:
- name (snake_case)
- type (string, integer, number, boolean, array, object, or a specific format like uuid, email, date-time, uri)
- required (true/false)
- description (one sentence)
- constraints (if any: enum values, min/max, pattern, unique, references)

Rules:
- Include standard infrastructure fields: id (uuid, readonly), created_at (date-time, readonly), updated_at (date-time, readonly)
- Derive fields from requirements — if a requirement mentions a data attribute, include it
- Derive fields from integration flows — if data flows between systems, include the linking fields
- Use enum types when requirements specify fixed values or statuses
- Mark fields as required when requirements use "must" or "mandatory"
- Do NOT include fields that aren't supported by the requirements or description
- Keep it focused: 8-20 fields maximum

Respond ONLY with valid JSON in this exact format:
{{
  "fields": [
    {{
      "name": "id",
      "type": "string",
      "format": "uuid",
      "required": true,
      "readonly": true,
      "description": "Unique identifier"
    }},
    {{
      "name": "status",
      "type": "string",
      "format": "enum",
      "enum": ["active", "inactive"],
      "required": true,
      "readonly": false,
      "description": "Current lifecycle status"
    }}
  ],
  "confidence": 0.85,
  "reasoning": "Brief explanation of key design decisions"
}}"""


def _build_requirements_text(requirements):
    """Format requirements for the prompt."""
    if not requirements:
        return "No requirements defined."
    lines = []
    for r in requirements[:15]:
        priority = f"P{r.priority}" if r.priority else ""
        req_type = r.requirement_type.value if r.requirement_type else "general"
        lines.append(f"- [{req_type}] {priority} {r.name}: {r.description or 'No description'}")
    return "\n".join(lines)


def _build_flows_text(flows, element_name):
    """Format integration flows relevant to this element."""
    if not flows:
        return "No integration flows defined."
    lines = []
    for f in flows:
        direction = f.flow_direction or "unknown"
        protocol = f.protocol or "unspecified"
        pii = " (contains PII)" if f.contains_pii else ""
        lines.append(f"- {f.flow_name}: {direction} via {protocol}{pii}")
        if f.data_format:
            lines[-1] += f" [{f.data_format}]"
    return "\n".join(lines) if lines else "No integration flows defined."


def _build_sla_text(slas):
    """Format SLAs for the prompt."""
    if not slas:
        return "No SLAs defined."
    lines = []
    for s in slas:
        parts = [s.sla_name]
        if s.response_time_ms:
            parts.append(f"response: {s.response_time_ms}ms")
        if s.availability_target:
            parts.append(f"availability: {s.availability_target}%")
        if s.rto_hours:
            parts.append(f"RTO: {s.rto_hours}h")
        lines.append("- " + ", ".join(parts))
    return "\n".join(lines)


def _build_capabilities_text(solution_id):
    """Format linked capabilities for the prompt."""
    try:
        from app.models.solution_models import SolutionArchiMateElement
        caps = SolutionArchiMateElement.query.filter_by(
            solution_id=solution_id, layer_type="business"
        ).limit(10).all()
        if not caps:
            return "No capabilities linked."
        return "\n".join(f"- {c.element_name}" for c in caps)
    except Exception:
        return "No capabilities linked."


def _build_relationships_text(element_id):
    """Build ArchiMate relationship context for an element.

    Shows what this element serves, realizes, accesses, and is assigned to,
    including the connected elements' descriptions. This is the richest
    source of context for accurate field inference — e.g. knowing that an
    ApplicationComponent 'serves' a BusinessProcess 'Order Processing' that
    has description 'Handles B2B orders from SAP SD module' tells the LLM
    exactly what fields and integrations to generate.
    """
    try:
        from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
        from app import db

        lines = []
        # Outgoing relationships (this element is source)
        outgoing = ArchiMateRelationship.query.filter_by(source_id=element_id).limit(15).all()
        for rel in outgoing:
            target = ArchiMateElement.query.get(rel.target_id)
            if target:
                desc = f' — "{target.description}"' if target.description else ""
                lines.append(f"- This element --[{rel.relationship_type}]--> {target.name} ({target.type}, {target.layer or '?'} layer){desc}")

        # Incoming relationships (this element is target)
        incoming = ArchiMateRelationship.query.filter_by(target_id=element_id).limit(15).all()
        for rel in incoming:
            source = ArchiMateElement.query.get(rel.source_id)
            if source:
                desc = f' — "{source.description}"' if source.description else ""
                lines.append(f"- {source.name} ({source.type}, {source.layer or '?'} layer) --[{rel.relationship_type}]--> This element{desc}")

        return "\n".join(lines) if lines else "No ArchiMate relationships found for this element."
    except Exception as e:
        logger.debug("Could not build relationships text: %s", e)
        return "No ArchiMate relationships available."


def _build_quality_text(solution_id):
    """Format quality attributes for the prompt (beyond SLAs)."""
    try:
        from app.models.solution_sad_models import SolutionQualityAttribute
        qas = SolutionQualityAttribute.query.filter_by(solution_id=solution_id).limit(10).all()
        if not qas:
            return ""
        lines = ["## Quality Attributes"]
        for qa in qas:
            parts = [qa.name]
            if qa.target_value:
                parts.append(f"target: {qa.target_value}")
            if qa.priority:
                parts.append(f"priority: {qa.priority}")
            if qa.description:
                parts.append(qa.description[:100])
            lines.append("- " + " | ".join(parts))
        return "\n".join(lines)
    except Exception:
        return ""


def infer_code_spec(element, requirements, flows, slas, solution_id, element_id=None):
    """Use LLM to propose schema fields for a SolutionAppElement.

    Args:
        element: SolutionAppElement instance (or proxy with name, element_type, description)
        requirements: list of SolutionRequirement instances for the solution
        flows: list of SolutionIntegrationFlow instances for the solution
        slas: list of SolutionSLA instances for the solution
        solution_id: int
        element_id: int (optional, for relationship lookup)

    Returns:
        dict with keys: fields (list), confidence (float), reasoning (str), raw_response (str)
        or None on failure
    """
    try:
        from app.modules.ai_chat.services.llm_service import LLMService
        provider, model = LLMService._get_configured_provider()
    except Exception as e:
        logger.warning("LLM not configured for code spec inference: %s", e)
        return None

    # Build relationship, quality, and solution context
    rels_text = _build_relationships_text(element_id) if element_id else "No element ID — relationships unavailable."
    quality_text = _build_quality_text(solution_id)

    # Solution brief — the architect's original problem statement
    solution_brief = "No solution brief available."
    try:
        from app.models.solution_models import Solution
        sol = Solution.query.get(solution_id)
        if sol:
            parts = []
            if sol.name:
                parts.append(f"**Solution:** {sol.name}")
            if sol.business_domain:
                parts.append(f"**Domain:** {sol.business_domain}")
            brief = getattr(sol, "problem_clarification", None) or getattr(sol, "description", None)
            if brief:
                brief_text = brief if isinstance(brief, str) else str(brief)
                parts.append(f"**Problem:** {brief_text[:500]}")
            if parts:
                solution_brief = "\n".join(parts)
    except Exception as e:
        logger.debug("Could not load solution brief for spec inference: %s", e)

    prompt = FIELD_INFERENCE_PROMPT.format(
        solution_brief=solution_brief,
        element_name=element.name,
        element_type=element.element_type or "component",
        description=element.description or "No description provided.",
        technology=element.technology or "Not specified",
        relationships_text=rels_text,
        requirements_text=_build_requirements_text(requirements),
        flows_text=_build_flows_text(flows, element.name),
        sla_text=_build_sla_text(slas),
        quality_text=quality_text,
        capabilities_text=_build_capabilities_text(solution_id),
    )

    try:
        response_text, interaction = LLMService._call_llm(
            prompt=prompt, model=model, provider=provider
        )
    except Exception as e:
        logger.error("LLM call failed for code spec inference: %s", e)
        return None

    # Parse JSON from response
    try:
        # Strip markdown code fences if present
        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            if text.startswith("json"):
                text = text[4:].strip()

        parsed = json.loads(text)
        return {
            "fields": parsed.get("fields", []),
            "confidence": parsed.get("confidence", 0.7),
            "reasoning": parsed.get("reasoning", ""),
            "raw_response": response_text,
            "provider": provider,
            "model": model,
        }
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to parse LLM response as JSON: %s", e)
        return {
            "fields": [],
            "confidence": 0,
            "reasoning": "LLM response could not be parsed as JSON",
            "raw_response": response_text,
            "provider": provider,
            "model": model,
            "parse_error": str(e),
        }


def infer_all_code_specs(solution_id):
    """Infer code specs for all app elements in a solution.

    Returns a dict mapping element_id -> inference result.
    """
    from app.models.solution_sad_models import (
        SolutionAppElement, SolutionIntegrationFlow, SolutionSLA,
    )

    app_elements = SolutionAppElement.query.filter_by(
        solution_id=solution_id
    ).order_by(SolutionAppElement.name).all()

    if not app_elements:
        return {}

    flows = SolutionIntegrationFlow.query.filter_by(solution_id=solution_id).all()
    slas = SolutionSLA.query.filter_by(solution_id=solution_id).all()

    # Load requirements
    requirements = []
    try:
        from app.models.solution_architect_models import SolutionRequirement
        requirements = SolutionRequirement.query.filter_by(
            solution_id=solution_id
        ).filter(SolutionRequirement.deleted_at.is_(None)).all()
    except Exception as e:
        logger.debug("Could not load requirements for code spec inference: %s", e)

    results = {}
    for elem in app_elements:
        # Skip elements that already have confirmed code_spec
        if elem.code_spec:
            results[elem.id] = {
                "fields": elem.code_spec.get("fields", []),
                "confidence": 1.0,
                "reasoning": "Previously confirmed by architect",
                "status": "confirmed",
            }
            continue

        result = infer_code_spec(elem, requirements, flows, slas, solution_id)
        if result:
            result["status"] = "proposed"
            result["element_id"] = elem.id
            result["element_name"] = elem.name
            results[elem.id] = result
        else:
            results[elem.id] = {
                "fields": [],
                "confidence": 0,
                "reasoning": "Inference failed — LLM not available or returned error",
                "status": "failed",
                "element_id": elem.id,
                "element_name": elem.name,
            }

    return results
