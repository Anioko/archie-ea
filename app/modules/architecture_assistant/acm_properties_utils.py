"""Normalize ACM property dicts for promotion and codegen.

Wizard properties may be plain scalars or {value, source} dicts (see PropertyService).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

_PRIORITY_TO_MOSCOW = {
    "must-have": "MUST",
    "should-have": "SHOULD",
    "could-have": "COULD",
    "wont-have": "WONT",
}


def unwrap_acm_value(raw: Any) -> Optional[str]:
    """Return a string for DB / JSON, or None if empty."""
    if raw is None:
        return None
    if isinstance(raw, dict) and "value" in raw:
        v = raw.get("value")
        if v is None:
            return None
        s = str(v).strip()
        return s or None
    if isinstance(raw, (list, dict)):
        return None
    s = str(raw).strip()
    return s or None


def moscow_from_acm_properties(acm: Dict[str, Any]) -> Optional[str]:
    """Map wizard `priority` (must-have, …) or explicit `moscow_priority` to MUST/SHOULD/…"""
    if not acm:
        return None
    explicit = unwrap_acm_value(acm.get("moscow_priority"))
    if explicit:
        return explicit.upper()[:10]
    pri = unwrap_acm_value(acm.get("priority"))
    if not pri:
        return None
    key = pri.lower().strip()
    return _PRIORITY_TO_MOSCOW.get(key, pri.upper()[:10])


def compliance_tags_from_acm(acm: Dict[str, Any]) -> List[str]:
    """Merge explicit compliance_tags with compliance_reference text."""
    tags: List[str] = []
    if not acm:
        return tags
    raw = acm.get("compliance_tags")
    if isinstance(raw, list):
        tags.extend(str(x).strip() for x in raw if x and str(x).strip())
    elif isinstance(raw, str) and raw.strip():
        tags.append(raw.strip())
    ref = unwrap_acm_value(acm.get("compliance_reference"))
    if ref and ref not in tags:
        tags.append(ref)
    return tags


def build_requirement_traceability_from_acm(acm: Dict[str, Any]) -> Dict[str, str]:
    """Fields for UML / codegen prompts (motivation-layer elements)."""
    if not acm:
        return {}
    out: Dict[str, str] = {}
    for key in (
        "priority",
        "compliance_reference",
        "verification_method",
        "acceptance_criteria",
        "stakeholder",
    ):
        v = unwrap_acm_value(acm.get(key))
        if v:
            out[key] = v
    alt_stake = unwrap_acm_value(acm.get("stakeholder_name"))
    if alt_stake and "stakeholder" not in out:
        out["stakeholder"] = alt_stake
    m = moscow_from_acm_properties(acm)
    if m:
        out["moscow_priority"] = m
    return out
