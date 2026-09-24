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
        # T-005 (US-5) addition: the yield endpoint's p95 bucket-edge read
        # (D3) has no honest number to report when the 95th percentile falls
        # in the histogram's +Inf overflow bucket -- reporting the top
        # declared boundary (5.0) as if it were the measured value would be
        # exactly the fabrication CLAUDE.md's "never invent data" rule
        # forbids.
        "p95_above_highest_bucket",
        # L3/L6 brief (2026-09-21) addition: Ask's Portfolio lens resolves an
        # ArchiMate element to its ApplicationComponent (the row the
        # rationalization/duplicate/TCO pages are keyed on) before it can
        # offer a deep link. Not every element is one -- most are not -- and
        # that is an honest absence, not an error.
        "no_application_component",
        # L5 brief (2026-09-22) additions: Ask's Programme lens seeds from
        # UnifiedWorkPackage rows linked to the picked element. Most
        # elements have none -- an honest absence, matching L6's
        # no_risk_recorded precedent -- and a real work package with no
        # estimated_cost is a distinct fact from "unknown": nobody budgeted
        # it, not that the figure failed to load.
        "no_work_package_recorded",
        "not_costed",
        # L2 brief (2026-09-22) addition: Ask's Strategy lens seeds from
        # PortfolioInitiative rows linked to the picked element (the
        # existing "no_initiative_linked" member above covers that honest
        # absence). A real initiative with no total_budget is a distinct
        # fact from "unknown" -- nobody budgeted it -- the same distinction
        # L5's not_costed draws for a different field pair
        # (UnifiedWorkPackage.estimated_cost/actual_cost); not_costed
        # itself is not reused here so each code stays tied to one field
        # pair's own absence condition.
        "no_budget_recorded",
        # L4 brief (2026-09-22) additions: Ask's Accountability lens resolves
        # an element to its ApplicationComponent (reusing L3's own
        # resolution) then lists ApplicationOwnership rows for it.
        # no_ownership_records covers the honest-empty case -- a real
        # component with zero ownership rows -- distinct from the
        # pre-existing no_ownership_recorded (a single element's owner
        # field inside the L1 impact traversal, a different table and a
        # different absence condition). capacity_not_available is not a
        # per-request absence at all: no Workforce/Skill/Headcount model
        # exists anywhere in this codebase, so every accountability
        # response, success included, honestly discloses that gap rather
        # than silently answering only half the lens's own question.
        "no_ownership_records",
        "capacity_not_available",
        # Role-gating brief (2026-09-22): financial figures on the Strategy
        # and Programme lenses (budget/cost variance) are redacted at the
        # route layer for roles without budget authority (mirrors
        # ROLE_SECTION_ACCESS's existing role-gating precedent, applied here
        # per-field rather than per-page). Redaction is honest, not silent:
        # the field is None and this reason names why, the same discipline
        # not_costed/no_budget_recorded already use for a different kind of
        # absence.
        "financial_data_restricted",
        # Risk/control-gaps (2026-09-23) addition: Ask's Risk lens lists
        # the compliance gap rows recorded against anything on the answer's
        # own element set, beside the risks, and the resolved component's own
        # recorded compliance tags. Most elements name no compliance
        # requirement at all, and most components carry none of the three
        # text columns that would evidence one -- an honest absence, the same
        # discipline no_risk_recorded already applies to a different table on
        # the same answer.
        "no_compliance_mapping_recorded",
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
