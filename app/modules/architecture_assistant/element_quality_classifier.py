"""
Deterministic quality classifier for LLM-generated ArchiMate elements.

No LLM call — purely rule-based scoring. Called during Step 3 persistence to
decide whether each element should be:

  "accept"  — auto-accepted as primary, no human review needed
  "review"  — flagged for optional human review (short list, ≤ 15 per solution)
  "reject"  — silently discarded, never written to DB

Design principles:
- Fast (no I/O, no LLM)
- Conservative on reject (prefer "review" over "reject" when uncertain)
- Strict on the GENERIC_BLOCKLIST (known-bad placeholder names)
"""

# ---------------------------------------------------------------------------
# Generic placeholder names that carry zero architectural information.
# These originate from ArchiMateTemplateService, old prompt versions, and
# pattern-library scaffolding that ran before solution-specific names were used.
# Any element whose name (lowercased + stripped) matches this set is rejected.
# ---------------------------------------------------------------------------
GENERIC_BLOCKLIST = frozenset({
    # Application layer generic placeholders
    "frontend application",
    "primary data store",
    "core business entity",
    "business logic layer",
    "core business api",
    "core business function",
    "primary business service",
    "primary user interface",
    "primary integration point",
    "analytics data store",
    "analytics engine",
    "core application",
    "api service",
    "application data",
    "infrastructure services",
    "core business logic",
    "data access layer",
    "user interface",
    "business logic",
    "reporting service",
    # Business layer generics
    "key metrics and kpis",
    "end user",
    "business user",
    "primary business service",
    # Technology layer generics
    "application server",
    "database server",
    "web server",
    "database cluster",
    "message queue",
    # Generic motivation/strategy
    "business process management",
    "service management",
    "digital operations",
    "data management",
    "customer engagement",
    "system modernization initiative",
    "service-oriented architecture",
    "microservices adoption strategy",
    "data management capability",
    # Generic nodes / infra
    "application server",
    "database server",
    "web server node",
    # Generic business layer
    "business data",
    "customer service",
    "business user",
    "service management",
    "data entry process",
    "data query service",
    "database",
    # Generic from template seeding
    "api gateway",           # too generic without a qualifier
    "message broker",        # too generic without a qualifier
    "monitoring platform",   # too generic without a qualifier
})

# ArchiMate types where a single-word name is actually fine
# (e.g., "GDPR" is a valid Constraint, "Node" types are OK)
_SINGLE_WORD_OK_TYPES = frozenset({
    "Constraint", "Principle", "Driver", "Node", "Device",
    "CommunicationNetwork", "Artifact", "Equipment", "Facility",
})


def classify_element(el_data: dict) -> dict:
    """
    Classify a single LLM-generated ArchiMate element.

    Args:
        el_data: dict with keys: name, type, description, source, layer,
                 capability_source, data_classification, contains_pii

    Returns:
        dict with keys:
          verdict  : "accept" | "review" | "reject"
          score    : int 0-100 (informational)
          reasons  : list[str] — human-readable explanation
    """
    name = (el_data.get("name") or "").strip()
    description = (el_data.get("description") or "").strip()
    el_type = (el_data.get("type") or "").strip()
    source = (el_data.get("source") or "derived").strip()

    reasons: list[str] = []

    # ── Existing catalog elements are always accepted ──────────────────────
    if source in ("existing", "pattern"):
        return {"verdict": "accept", "score": 100, "reasons": [f"source={source}"]}

    # ── Hard reject — empty name ───────────────────────────────────────────
    if not name:
        return {"verdict": "reject", "score": 0, "reasons": ["empty name"]}

    name_lower = name.lower()

    # ── Hard reject — unfilled template placeholder ────────────────────────
    if "{" in name or "}" in name:
        return {"verdict": "reject", "score": 0, "reasons": ["unfilled template placeholder"]}

    # ── Hard reject — generic blocklist ───────────────────────────────────
    if name_lower in GENERIC_BLOCKLIST:
        return {"verdict": "reject", "score": 0,
                "reasons": [f"generic placeholder name: '{name}'"]}

    # ── Hard reject — name identical to type ──────────────────────────────
    if name_lower == el_type.lower():
        return {"verdict": "reject", "score": 0, "reasons": ["name identical to type"]}

    # ── Hard reject — name has ArchiMate type prefix ──────────────────────
    _type_prefixes = (
        "businessprocess:", "applicationcomponent:", "technologyservice:",
        "requirement:", "constraint:", "goal:", "capability:",
        "applicationservice:", "outcome:", "assessment:",
    )
    for _pfx in _type_prefixes:
        if name_lower.startswith(_pfx):
            return {"verdict": "reject", "score": 5,
                    "reasons": [f"name has ArchiMate type prefix '{_pfx}'"]}

    # ── Quality scoring ────────────────────────────────────────────────────
    score = 75  # baseline — most LLM-generated elements are reasonable

    words = name.split()
    word_count = len(words)

    # Short name penalty
    if word_count == 1 and len(name) < 6 and el_type not in _SINGLE_WORD_OK_TYPES:
        score -= 35
        reasons.append(f"single very-short name '{name}'")
    elif word_count == 1 and el_type not in _SINGLE_WORD_OK_TYPES:
        score -= 10
        reasons.append(f"single-word name '{name}'")

    # Description quality
    if not description:
        score -= 15
        reasons.append("missing description")
    elif len(description) < 10:
        score -= 10
        reasons.append("very short description (<10 chars)")
    elif description.lower().strip() == name_lower:
        score -= 20
        reasons.append("description is identical to name")
    elif description.lower().strip() == el_type.lower():
        score -= 15
        reasons.append("description is just the type name")

    # ── Verdict ────────────────────────────────────────────────────────────
    if score >= 60:
        return {"verdict": "accept", "score": score, "reasons": reasons}
    elif score >= 30:
        return {"verdict": "review", "score": score, "reasons": reasons}
    else:
        return {"verdict": "reject", "score": score, "reasons": reasons}
