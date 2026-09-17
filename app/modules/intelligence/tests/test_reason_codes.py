"""T-001 acceptance criterion 13: the DE-14 reason-code vocabulary is closed.

Mapping:
    13 -> test_reason_codes_has_exactly_sixteen_members,
          test_unknown_reason_code_is_rejected_not_passed_through
"""

from __future__ import annotations

import pytest

from app.modules.intelligence.services.reason_codes import (
    REASON_CODES,
    UnknownReasonCodeError,
    is_valid_reason_code,
    validate_reason_code,
)

# sdd-v2.md § API-8 — the sixteen members, exactly as listed there.
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
}


def test_reason_codes_has_exactly_sixteen_members():
    assert len(REASON_CODES) == 16
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
