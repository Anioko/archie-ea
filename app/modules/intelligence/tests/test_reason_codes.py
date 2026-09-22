"""T-001 acceptance criterion 13: the DE-14 reason-code vocabulary is closed.

Mapping:
    13 -> test_reason_codes_has_exactly_twenty_three_members,
          test_unknown_reason_code_is_rejected_not_passed_through

T-004 (US-1) added two members -- ``no_tenant_context`` and
``element_not_found`` -- for absence conditions on the cross-layer impact
read path that sdd-v2.md's original sixteen do not cover. T-005 (US-5) added
one more -- ``p95_above_highest_bucket`` (D3) -- for the yield endpoint's
p95 bucket-edge read having no honest number to report when the 95th
percentile falls in the histogram's +Inf overflow bucket. "Closed" means no
endpoint may invent an absence string inline, not that the set is frozen at
sixteen forever; the module's own docstring says a new absence condition
adds a member here, and nowhere else. This test is updated in lockstep.

This ``_EXPECTED`` list drifted out of sync with reality some time before
this fix -- the L3/L5 briefs each added a member to ``reason_codes.py``
(``no_application_component``, ``no_work_package_recorded``, ``not_costed``)
without updating this ratchet, only the two route-count ratchets. Found
while adding the L2 brief's own ``no_budget_recorded`` member; corrected to
the real, current set (23) rather than bumped by one on top of a stale base.
"""

from __future__ import annotations

import pytest

from app.modules.intelligence.services.reason_codes import (
    REASON_CODES,
    UnknownReasonCodeError,
    is_valid_reason_code,
    validate_reason_code,
)

# sdd-v2.md § API-8's original sixteen, T-004's two additions, plus T-005's
# one addition (p95_above_highest_bucket, D3).
_EXPECTED = {
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
    "no_tenant_context",
    "element_not_found",
    "p95_above_highest_bucket",
    "no_application_component",
    "no_work_package_recorded",
    "not_costed",
    "no_budget_recorded",
}


def test_reason_codes_has_exactly_twenty_three_members():
    assert len(REASON_CODES) == 23
    assert REASON_CODES == frozenset(_EXPECTED)


@pytest.mark.parametrize("code", sorted(_EXPECTED))
def test_every_listed_member_is_valid(code):
    assert is_valid_reason_code(code) is True
    assert validate_reason_code(code) == code


def test_unknown_reason_code_is_rejected_not_passed_through():
    assert is_valid_reason_code("not_a_real_reason_code") is False
    with pytest.raises(UnknownReasonCodeError):
        validate_reason_code("not_a_real_reason_code")


def test_membership_is_closed_no_inline_invention():
    """A new absence condition must add a member to REASON_CODES rather than
    an endpoint inventing a string inline — this pins that the module is the
    single point of truth an endpoint can be checked against."""
    made_up = "definitely_not_in_the_api8_vocabulary"
    assert made_up not in REASON_CODES
    with pytest.raises(UnknownReasonCodeError):
        validate_reason_code(made_up)
