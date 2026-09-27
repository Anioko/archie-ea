"""Genome-patch JSON Schema (ADR 0009 / ADR 0010).

A *genome patch* is the ONLY thing the AI copilot is allowed to emit when it
wants to change the enterprise model. It never writes artifacts or rows
directly; it proposes one of these, a human approves it, and deterministic code
(`app.modules.genome.patch.applier`) renders it into the model. That is what
makes the copilot governable by construction.

The schema is expressed as a JSON-Schema-shaped Python dict. It is interpreted
by a small, self-contained, deterministic validator
(`app.modules.genome.patch.validator`) rather than the `jsonschema` package, so
the genome-patch flow adds no new runtime dependency and the validation is
fully under our control (fail-closed, never coercing, never defaulting). The
subset of JSON Schema the validator understands is: ``type`` (object/string/
integer/number/boolean/array), ``required``, ``properties``,
``additionalProperties`` (bool), ``enum``, ``minLength``, and ``items``.

A patch names:
  * target      — which org and which genome domain it lands in;
  * operation   — add a new element, or modify an existing one;
  * element     — the ArchiMate element/type/layer + fields being written;
  * provenance  — REQUIRED who/why plus the ArchiMate anchor. A patch with no
                  rationale or no anchor is rejected, never applied with a
                  fabricated default (CLAUDE.md: never invent data).
"""

# Genome domains an enterprise patch may target. These mirror the deterministic
# emitter families already in the codebase (business / data / application aka
# implementation / technology / security-motivation).
GENOME_DOMAINS = (
    "business",
    "data",
    "application",
    "technology",
    "motivation",
    "implementation",
    "security",
)

# ArchiMate 3.2 layers (DESIGN.md "ArchiMate Layer Rules"). The element's layer
# must be one of these; the applier maps it onto the ArchiMateElement.layer
# column verbatim.
ARCHIMATE_LAYERS = (
    "motivation",
    "strategy",
    "business",
    "application",
    "technology",
    "implementation",
    "physical",
)

# ArchiMate element types this first increment knows how to render. Kept
# deliberately small and explicit — an unknown type is REJECTED, not guessed.
# Every motivation type here triggers a synced ArchiMateElement on apply
# (CLAUDE.md: "the field IS the element").
ARCHIMATE_TYPES = (
    # Motivation layer
    "Driver",
    "Goal",
    "Outcome",
    "Constraint",
    "Requirement",
    "Principle",
    "Risk",
    "Assessment",
    "Stakeholder",
    "Metric",
    # Strategy layer
    "Capability",
    "CourseOfAction",
    "ValueStream",
    # Implementation layer
    "WorkPackage",
    "Plateau",
    # Business layer
    "BusinessService",
    "BusinessProcess",
    # Application layer
    "ApplicationComponent",
    "ApplicationService",
    "DataObject",
    # Technology layer
    "Node",
    "TechnologyService",
)

# Canonical layer for each ArchiMate type above — promoted from the grouping
# comments so grounding can check an element's declared `layer` against the
# layer its `archimate_type` actually belongs to (a Capability declared in the
# business layer is a hallucination, schema-valid though it is).
ARCHIMATE_TYPE_LAYER = {
    # Motivation
    "Driver": "motivation", "Goal": "motivation", "Outcome": "motivation",
    "Constraint": "motivation", "Requirement": "motivation", "Principle": "motivation",
    "Risk": "motivation", "Assessment": "motivation", "Stakeholder": "motivation",
    "Metric": "motivation",
    # Strategy
    "Capability": "strategy", "CourseOfAction": "strategy", "ValueStream": "strategy",
    # Implementation
    "WorkPackage": "implementation", "Plateau": "implementation",
    # Business
    "BusinessService": "business", "BusinessProcess": "business",
    # Application
    "ApplicationComponent": "application", "ApplicationService": "application",
    "DataObject": "application",
    # Technology
    "Node": "technology", "TechnologyService": "technology",
}

GENOME_PATCH_OPERATIONS = ("add", "modify")

# --------------------------------------------------------------------------- #
# The schema itself.                                                           #
# --------------------------------------------------------------------------- #

GENOME_PATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": True,  # forward-compatible envelope fields tolerated
    "required": ["target", "operation", "element", "provenance"],
    "properties": {
        "target": {
            "type": "object",
            "required": ["organization_id", "domain"],
            "additionalProperties": True,
            "properties": {
                "organization_id": {"type": "integer"},
                "domain": {"type": "string", "enum": list(GENOME_DOMAINS)},
            },
        },
        "operation": {"type": "string", "enum": list(GENOME_PATCH_OPERATIONS)},
        "element": {
            "type": "object",
            "required": ["archimate_type", "layer", "name"],
            "additionalProperties": True,
            "properties": {
                "archimate_type": {"type": "string", "enum": list(ARCHIMATE_TYPES)},
                "layer": {"type": "string", "enum": list(ARCHIMATE_LAYERS)},
                "name": {"type": "string", "minLength": 1},
                "description": {"type": "string"},
                # Required by the validator only when operation == "modify"
                # (a conditional the JSON-Schema subset can't express, enforced
                # in validator.validate_genome_patch).
                "element_id": {"type": "integer"},
                # Optional as-is / to-be state, so the AI copilot can propose a
                # TARGET (to-be) architecture, not just untagged elements — the
                # applier maps it to ArchiMateElement.togaf_plateau. Baseline =
                # As-Is, Target = To-Be, Transition = interim plateau.
                "architecture_state": {
                    "type": "string",
                    "enum": ["Baseline", "Target", "Transition"],
                },
                # Optional free-form fields the applier maps onto the element.
                "fields": {"type": "object", "additionalProperties": True},
            },
        },
        "provenance": {
            "type": "object",
            "required": ["proposed_by", "rationale", "archimate_anchor"],
            "additionalProperties": True,
            "properties": {
                # WHO proposed it — a user id, agent id, or descriptive label.
                "proposed_by": {"type": "string", "minLength": 1},
                # WHY — a non-empty human rationale. No default is ever supplied.
                "rationale": {"type": "string", "minLength": 1},
                # The ArchiMate anchor this element hangs off: the type or id of
                # the existing element that motivates/contains it. Non-empty.
                "archimate_anchor": {"type": "string", "minLength": 1},
                # Optional: where the proposal came from (e.g. "ai_copilot").
                "source": {"type": "string"},
            },
        },
    },
}

__all__ = [
    "GENOME_PATCH_SCHEMA",
    "GENOME_DOMAINS",
    "ARCHIMATE_LAYERS",
    "ARCHIMATE_TYPES",
    "GENOME_PATCH_OPERATIONS",
]
