"""H4/L1: shared enum-to-label helper (`humanize_key` Jinja filter).

Covers app/utils/template_utils.py's humanize_key_filter, and its use on
/admin/governance-gates so a gate's raw key never renders without a human
label beside it.
"""

from flask import render_template, render_template_string


def test_humanize_key_known_override(app):
    with app.test_request_context("/"):
        assert (
            render_template_string("{{ 'arb_review_is_legacy_generic'|humanize_key }}")
            == "Legacy review (predates typed ARB submission)"
        )


def test_humanize_key_falls_back_to_title_case(app):
    with app.test_request_context("/"):
        assert render_template_string("{{ 'some_new_reason_code'|humanize_key }}") == "Some New Reason Code"


def test_humanize_key_none_passthrough(app):
    with app.test_request_context("/"):
        assert render_template_string("{{ (none|humanize_key) is none }}") == "True"


def test_governance_gates_default_gate_shows_label_and_key(app):
    """/admin/governance-gates rendered a raw `arb_submission` key with no
    human label next to it (L1). The default-gates loop now runs the key
    through `humanize_key` for a real label, and keeps the raw key as a
    secondary, explicitly-labelled hint rather than dropping it."""
    from app.modules.solutions_strategic.v2.services.governance_gate_service import (
        DEFAULT_GATES,
    )

    with app.test_request_context("/"):
        body = render_template(
            "admin/governance_gates.html",
            default_gates=DEFAULT_GATES,
            can_manage_governance_gates=False,
        )
    assert "Architecture Review Board submission" in body
    assert "arb_submission" in body  # raw key kept, but now labelled "Gate key"
