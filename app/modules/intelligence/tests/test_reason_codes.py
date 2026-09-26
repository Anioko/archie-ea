"""T-001 acceptance criterion 13: the DE-14 reason-code vocabulary is closed.

Mapping:
    13 -> test_reason_codes_has_exactly_thirty_one_members,
          test_unknown_reason_code_is_rejected_not_passed_through

T-004 (US-1) added two members -- ``no_tenant_context`` and
``element_not_found`` -- for absence conditions on the cross-layer impact
read path that sdd-v2.md's original sixteen do not cover. T-005 (US-5) added
one more -- ``p95_above_highest_bucket`` (D3) -- for the yield endpoint's
p95 bucket-edge read having no honest number to report when the 95th
percentile falls in the histogram's +Inf overflow bucket. Ask's Portfolio
lens (L3) added ``no_application_component``; the Programme lens (L5) added
two more -- ``no_work_package_recorded`` and ``not_costed``. The Strategy
lens (L2) added ``no_budget_recorded``; the Accountability lens (L4) added
``no_ownership_records``/``capacity_not_available``, later
``ownership_reader_not_built`` when its read was withdrawn per external
review. Role-gating added ``financial_data_restricted``. T-S1 (value streams
at risk, curated path) added four more -- ``no_value_stream_recorded``,
``no_capability_linked``, ``value_stream_not_linked_to_model`` and
``dependency_direction_unknown`` -- of which T-S1 emits only the first two;
the other two are reserved for T-S3's graph path.

"Closed" means no endpoint may invent an absence string inline, not that the
set is frozen at sixteen forever; the module's own docstring says a new
absence condition adds a member here, and nowhere else. This test is
updated in lockstep -- this ``_EXPECTED`` list has drifted out of sync with
reality more than once already (found and corrected twice tonight,
independently, by two different lenses' briefs each adding a member without
re-deriving the true count); merging two branches that each added members
independently (L2/L4/role-gating on one side, T-S1 on the other) is a third
instance of the same class of drift, resolved here by re-deriving the real
count (31) rather than trusting either side's own stale number.
"""

from __future__ import annotations

import pytest

from app.modules.intelligence.services.reason_codes import (
    REASON_CODES,
    UnknownReasonCodeError,
    is_valid_reason_code,
    validate_reason_code,
)

# sdd-v2.md § API-8's original sixteen, T-004's two additions, T-005's one
# addition (p95_above_highest_bucket, D3), the Portfolio and Programme
# lenses' three additions, plus T-S1's four additions.
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
    "no_ownership_records",
    "capacity_not_available",
    "financial_data_restricted",
    "ownership_reader_not_built",
    "no_value_stream_recorded",
    "no_capability_linked",
    "value_stream_not_linked_to_model",
    "dependency_direction_unknown",
    "no_data_recorded",
    "no_steward_recorded",
    "no_lineage_recorded",
}


def test_reason_codes_has_exactly_thirty_four_members():
    assert len(REASON_CODES) == 34
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
