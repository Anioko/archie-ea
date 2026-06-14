"""ArchiMate 3.2 Relationship Grammar Validator.

Enforces the 10 core relationship types against the ArchiMate metamodel's
aspect compatibility rules.  Every element type maps to an *aspect*
(ActiveStructure, PassiveStructure, Behavior, Motivation, CompositeElement)
and a *layer*.  Relationship rules constrain which aspect pairs are legal.

Public API
----------
validate_relationship(source_type, target_type, relationship_type)
    -> {"valid": bool, "rule_id": str, "message": str, "suggestions": list[str]}

suggest_valid_relationships(source_type, target_type)
    -> list[str]  (relationship types that are legal between the two element types)
"""

from __future__ import annotations

import re
from typing import Dict, List

# ── Aspect classification ────────────────────────────────────────────────────
# ArchiMate 3.2 Table B.1 — every element type → (aspect, layer)

ASPECT_MAP: Dict[str, str] = {
    # Motivation layer — all Motivation aspect
    "stakeholder": "ActiveStructure",   # stakeholder is active
    "driver": "Motivation",
    "assessment": "Motivation",
    "goal": "Motivation",
    "outcome": "Motivation",
    "principle": "Motivation",
    "requirement": "Motivation",
    "constraint": "Motivation",
    "meaning": "Motivation",
    "value": "Motivation",
    # Strategy layer
    "resource": "PassiveStructure",
    "capability": "Behavior",
    "value_stream": "Behavior",
    "course_of_action": "Behavior",
    # Business layer
    "business_actor": "ActiveStructure",
    "business_role": "ActiveStructure",
    "business_collaboration": "ActiveStructure",
    "business_interface": "ActiveStructure",
    "business_process": "Behavior",
    "business_function": "Behavior",
    "business_interaction": "Behavior",
    "business_event": "Behavior",
    "business_service": "Behavior",
    "business_object": "PassiveStructure",
    "contract": "PassiveStructure",
    "representation": "PassiveStructure",
    "product": "CompositeElement",
    "location": "CompositeElement",
    # Application layer
    "application_component": "ActiveStructure",
    "application_collaboration": "ActiveStructure",
    "application_interface": "ActiveStructure",
    "application_function": "Behavior",
    "application_interaction": "Behavior",
    "application_process": "Behavior",
    "application_event": "Behavior",
    "application_service": "Behavior",
    "data_object": "PassiveStructure",
    # Technology layer
    "node": "ActiveStructure",
    "device": "ActiveStructure",
    "system_software": "ActiveStructure",
    "technology_collaboration": "ActiveStructure",
    "technology_interface": "ActiveStructure",
    "path": "ActiveStructure",
    "communication_network": "ActiveStructure",
    "technology_function": "Behavior",
    "technology_process": "Behavior",
    "technology_interaction": "Behavior",
    "technology_event": "Behavior",
    "technology_service": "Behavior",
    "artifact": "PassiveStructure",
    "technology_object": "PassiveStructure",
    # Implementation & Migration
    "work_package": "Behavior",
    "deliverable": "PassiveStructure",
    "implementation_event": "Behavior",
    "plateau": "CompositeElement",
    "gap": "PassiveStructure",
    # Composite / Other
    "grouping": "CompositeElement",
    "junction": "CompositeElement",
}

LAYER_MAP: Dict[str, str] = {
    "stakeholder": "motivation", "driver": "motivation", "assessment": "motivation",
    "goal": "motivation", "outcome": "motivation", "principle": "motivation",
    "requirement": "motivation", "constraint": "motivation", "meaning": "motivation",
    "value": "motivation",
    "resource": "strategy", "capability": "strategy", "value_stream": "strategy",
    "course_of_action": "strategy",
    "business_actor": "business", "business_role": "business",
    "business_collaboration": "business", "business_interface": "business",
    "business_process": "business", "business_function": "business",
    "business_interaction": "business", "business_event": "business",
    "business_service": "business", "business_object": "business",
    "contract": "business", "representation": "business", "product": "business",
    "location": "business",
    "application_component": "application", "application_collaboration": "application",
    "application_interface": "application", "application_function": "application",
    "application_interaction": "application", "application_process": "application",
    "application_event": "application", "application_service": "application",
    "data_object": "application",
    "node": "technology", "device": "technology", "system_software": "technology",
    "technology_collaboration": "technology", "technology_interface": "technology",
    "path": "technology", "communication_network": "technology",
    "technology_function": "technology", "technology_process": "technology",
    "technology_interaction": "technology", "technology_event": "technology",
    "technology_service": "technology", "artifact": "technology",
    "technology_object": "technology",
    "work_package": "implementation", "deliverable": "implementation",
    "implementation_event": "implementation", "plateau": "implementation",
    "gap": "implementation",
}

_STRUCTURE_ASPECTS = {"ActiveStructure", "PassiveStructure"}


def _normalize(name: str) -> str:
    """PascalCase / spaces -> snake_case."""
    s = name.replace(" ", "")
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower()


# ── Grammar rules ────────────────────────────────────────────────────────────

def _check_composition(src_aspect: str, tgt_aspect: str, **_kw) -> bool:
    """COMP-01: Both Structure, same aspect."""
    return (src_aspect in _STRUCTURE_ASPECTS
            and tgt_aspect in _STRUCTURE_ASPECTS
            and src_aspect == tgt_aspect)


def _check_aggregation(src_aspect: str, tgt_aspect: str, **_kw) -> bool:
    """AGG-01: Both Structure, same aspect."""
    return (src_aspect in _STRUCTURE_ASPECTS
            and tgt_aspect in _STRUCTURE_ASPECTS
            and src_aspect == tgt_aspect)


def _check_assignment(src_aspect: str, tgt_aspect: str, src_layer: str, tgt_layer: str, **_kw) -> bool:
    """ASGN-01: ActiveStructure -> Behavior (same layer) OR ActiveStructure -> ActiveStructure."""
    if src_aspect != "ActiveStructure":
        return False
    if tgt_aspect == "Behavior" and src_layer == tgt_layer:
        return True
    if tgt_aspect == "ActiveStructure":
        return True
    return False


def _check_realization(src_aspect: str, tgt_aspect: str, **_kw) -> bool:
    """REAL-01: any -> Motivation OR Behavior -> PassiveStructure."""
    if tgt_aspect == "Motivation":
        return True
    if src_aspect == "Behavior" and tgt_aspect == "PassiveStructure":
        return True
    return False


def _check_serving(src_aspect: str, tgt_aspect: str, **_kw) -> bool:
    """SERV-01: Behavior -> Behavior."""
    return src_aspect == "Behavior" and tgt_aspect == "Behavior"


def _check_access(src_aspect: str, tgt_aspect: str, **_kw) -> bool:
    """ACC-01: Behavior -> PassiveStructure."""
    return src_aspect == "Behavior" and tgt_aspect == "PassiveStructure"


def _check_influence(src_aspect: str, tgt_aspect: str, **_kw) -> bool:
    """INF-01: Motivation -> Motivation."""
    return src_aspect == "Motivation" and tgt_aspect == "Motivation"


def _check_association(**_kw) -> bool:
    """ASSOC-01: any -> any (always valid)."""
    return True


def _check_triggering(src_aspect: str, tgt_aspect: str, **_kw) -> bool:
    """TRIG-01: Behavior -> Behavior."""
    return src_aspect == "Behavior" and tgt_aspect == "Behavior"


def _check_flow(src_aspect: str, tgt_aspect: str, **_kw) -> bool:
    """FLOW-01: Behavior -> Behavior OR PassiveStructure -> PassiveStructure."""
    if src_aspect == "Behavior" and tgt_aspect == "Behavior":
        return True
    if src_aspect == "PassiveStructure" and tgt_aspect == "PassiveStructure":
        return True
    return False


GRAMMAR_RULES: Dict[str, dict] = {
    "Composition":  {"rule_id": "COMP-01",  "check": _check_composition,
                     "constraint": "Both endpoints must be Structure aspect (Active or Passive), same aspect."},
    "Aggregation":  {"rule_id": "AGG-01",   "check": _check_aggregation,
                     "constraint": "Both endpoints must be Structure aspect, same aspect."},
    "Assignment":   {"rule_id": "ASGN-01",  "check": _check_assignment,
                     "constraint": "ActiveStructure -> Behavior (same layer) OR ActiveStructure -> ActiveStructure."},
    "Realization":  {"rule_id": "REAL-01",  "check": _check_realization,
                     "constraint": "Any -> Motivation OR Behavior -> PassiveStructure."},
    "Serving":      {"rule_id": "SERV-01",  "check": _check_serving,
                     "constraint": "Behavior -> Behavior."},
    "Access":       {"rule_id": "ACC-01",   "check": _check_access,
                     "constraint": "Behavior -> PassiveStructure."},
    "Influence":    {"rule_id": "INF-01",   "check": _check_influence,
                     "constraint": "Motivation -> Motivation."},
    "Association":  {"rule_id": "ASSOC-01", "check": _check_association,
                     "constraint": "Any -> Any (always valid)."},
    "Triggering":   {"rule_id": "TRIG-01",  "check": _check_triggering,
                     "constraint": "Behavior -> Behavior."},
    "Flow":         {"rule_id": "FLOW-01",  "check": _check_flow,
                     "constraint": "Behavior -> Behavior OR PassiveStructure -> PassiveStructure."},
}


# ── Public API ───────────────────────────────────────────────────────────────

def validate_relationship(
    source_type: str,
    target_type: str,
    relationship_type: str,
) -> dict:
    """Validate a single relationship against ArchiMate 3.2 grammar.

    Returns dict with keys: valid, rule_id, message, suggestions.
    """
    src = _normalize(source_type)
    tgt = _normalize(target_type)

    src_aspect = ASPECT_MAP.get(src)
    tgt_aspect = ASPECT_MAP.get(tgt)

    if src_aspect is None:
        return {
            "valid": False,
            "rule_id": "UNKNOWN",
            "message": f"Unknown source element type: {source_type}",
            "suggestions": [],
        }
    if tgt_aspect is None:
        return {
            "valid": False,
            "rule_id": "UNKNOWN",
            "message": f"Unknown target element type: {target_type}",
            "suggestions": [],
        }

    rule = GRAMMAR_RULES.get(relationship_type)
    if rule is None:
        return {
            "valid": False,
            "rule_id": "UNKNOWN",
            "message": f"Unknown relationship type: {relationship_type}",
            "suggestions": list(GRAMMAR_RULES.keys()),
        }

    src_layer = LAYER_MAP.get(src, "")
    tgt_layer = LAYER_MAP.get(tgt, "")

    is_valid = rule["check"](
        src_aspect=src_aspect, tgt_aspect=tgt_aspect,
        src_layer=src_layer, tgt_layer=tgt_layer,
    )

    if is_valid:
        return {
            "valid": True,
            "rule_id": rule["rule_id"],
            "message": f"{relationship_type} from {source_type} to {target_type} is valid.",
            "suggestions": [],
        }

    suggestions = suggest_valid_relationships(source_type, target_type)
    return {
        "valid": False,
        "rule_id": rule["rule_id"],
        "message": (
            f"{rule['constraint']} "
            f"{source_type} ({src_aspect}) -> {target_type} ({tgt_aspect}) "
            f"is invalid in ArchiMate 3.2."
        ),
        "suggestions": suggestions,
    }


def suggest_valid_relationships(source_type: str, target_type: str) -> List[str]:
    """Return all relationship types that are legal between two element types."""
    src = _normalize(source_type)
    tgt = _normalize(target_type)

    src_aspect = ASPECT_MAP.get(src)
    tgt_aspect = ASPECT_MAP.get(tgt)
    if src_aspect is None or tgt_aspect is None:
        return []

    src_layer = LAYER_MAP.get(src, "")
    tgt_layer = LAYER_MAP.get(tgt, "")

    valid = []
    for rel_type, rule in GRAMMAR_RULES.items():
        if rule["check"](
            src_aspect=src_aspect, tgt_aspect=tgt_aspect,
            src_layer=src_layer, tgt_layer=tgt_layer,
        ):
            valid.append(rel_type)
    return valid
