"""DE-14: the closed reason-code vocabulary (FR-15, NFR-2).

One vocabulary, read by both the REST and MCP surfaces (SEC-15; sdd-v2.md
§ API-8). No endpoint may invent an absence string inline — a new absence
condition adds a member here, and nowhere else.

Every code renders as an informative empty state with a one-click fix, never
a blank, a zero or an estimate (UX principle P-3; the ``fabricated-data``
gate enforces this mechanically at the template layer, out of scope here).
"""

from __future__ import annotations

# sdd-v2.md § API-8 — the original sixteen members, plus the two T-004
# additions below (eighteen total), exactly, nothing invented.
REASON_CODES = frozenset(
    {
        "no_ownership_recorded",
        "no_maturity_recorded",
        "derivation_not_computed",
        "derivation_stale",
        "no_crosswalk_match",
        "no_crosswalk_row",
        "crosswalk_element_deleted",
        "external_id_maps_to_many_elements",
        "source_unavailable",
        "no_risk_recorded",
        "no_realising_element",
        "no_initiative_linked",
        "initiative_not_linked_to_model",
        "review_item_not_visible",
        "insufficient_samples_for_p95",
        "feed_not_connected",
        # T-004 (US-1) additions: absence conditions on the cross-layer
        # impact read path that the original sixteen do not cover. Added
        # here, and nowhere else, per this module's own rule that no
        # endpoint may invent an absence string inline.
        "no_tenant_context",
        "element_not_found",
    }
)


class UnknownReasonCodeError(ValueError):
    """A caller asked for a reason code outside the DE-14 closed vocabulary."""


def is_valid_reason_code(code: str) -> bool:
    """True when *code* is a member of the closed vocabulary."""
    return code in REASON_CODES


def validate_reason_code(code: str) -> str:
    """Return *code* unchanged if it is a member of the closed vocabulary.

    Raises ``UnknownReasonCodeError`` otherwise. This is the enforcement
    point that keeps a later endpoint from inventing an absence string
    inline (API-8) — call it wherever a reason code is about to leave this
    module, rather than passing a raw string through unchecked.
    """
    if code not in REASON_CODES:
        raise UnknownReasonCodeError(
            f"{code!r} is not a member of the DE-14 reason-code vocabulary"
        )
    return code


__all__ = [
    "REASON_CODES",
    "UnknownReasonCodeError",
    "is_valid_reason_code",
    "validate_reason_code",
]
