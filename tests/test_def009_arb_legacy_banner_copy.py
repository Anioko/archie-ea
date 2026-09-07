"""DEF-009: the legacy-generic ARB banner claimed a review was "read-only
here" when the untyped decision path rendered directly below it (in
``_decision_bar.html``) was fully functional for decidable reviews. Fixed by
correcting the banner copy in
``app/templates/arb/partials/_typed_review_legacy_generic.html``.

The first fix pass introduced a second inaccuracy: it unconditionally claimed
"It can still be approved, rejected or deferred below", which is false for a
Draft-status review, since ``_decision_bar.html`` renders nothing at all in
that state. These tests pin the corrected, state-conditional copy.
"""

from __future__ import annotations

from types import SimpleNamespace

from flask import render_template


def _orm_review(**overrides):
    base = dict(
        id=15,
        status="submitted",
        priority="high",
        review_type="architecture",
        submitter=None,
        submitter_id=None,
        submitted_at=None,
        description=None,
        decision=None,
        decision_rationale=None,
        decision_date=None,
        decided_by=None,
        conditions=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _review_readmodel():
    return {
        "state": "legacy_generic",
        "reason": "arb_review_is_legacy_generic",
        "identity": {"review_item_id": 15},
        "subject": None,
    }


def _render(app, orm_review):
    with app.test_request_context("/arb/"):
        return render_template(
            "arb/partials/_typed_review_legacy_generic.html",
            review=_review_readmodel(),
            _orm_review=orm_review,
            decision_action_url="/arb/reviews/15/decision",
        )


def test_decidable_review_banner_claims_decidable(app):
    body = _render(app, _orm_review(status="submitted"))
    assert "It can still be approved, rejected or deferred below" in body
    assert "read-only here" not in body


def test_draft_review_banner_does_not_claim_decidable(app):
    """A Draft review has no decision bar (decidable_statuses excludes draft),
    so the banner must not promise a control that will not render."""
    body = _render(app, _orm_review(status="draft"))
    assert "It can still be approved, rejected or deferred below" not in body
    assert "Submit it for review before it can be decided" in body


def test_already_decided_review_banner_points_at_recorded_decision(app):
    body = _render(app, _orm_review(status="submitted", decision="approved"))
    assert "It can still be approved, rejected or deferred below" not in body
    assert "A decision has already been recorded on it" in body


def test_banner_never_claims_unconditional_read_only(app):
    for status in ("draft", "submitted", "under_review", "deferred"):
        body = _render(app, _orm_review(status=status))
        assert "read-only here" not in body


# H4: a Draft-status legacy review told the user to "submit it for review"
# with no control anywhere on the page to do so. POST /arb/reviews/<id>/submit
# (arb_routes.py::submit_review) already handles exactly this case -- it
# refuses any review carrying solution_id/adr_id/architecture_model_id, so it
# is safe to wire up unconditionally in this always-untyped partial.
def test_draft_review_gets_a_working_submit_control(app):
    body = _render(app, _orm_review(status="draft"))
    assert 'action="/arb/reviews/15/submit"' in body
    assert "Submit for review" in body


def test_non_draft_reviews_do_not_render_a_submit_control(app):
    for status in ("submitted", "under_review", "deferred"):
        body = _render(app, _orm_review(status=status))
        assert "/reviews/15/submit" not in body


# H4/L1: the raw enum reason code must never reach the page beside its own
# label -- it is mapped through the shared `humanize_key` filter.
def test_legacy_generic_reason_is_humanized_not_raw_enum(app):
    body = _render(app, _orm_review(status="submitted"))
    assert "arb_review_is_legacy_generic" not in body
    assert "Legacy review (predates typed ARB submission)" in body
