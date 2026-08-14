"""Regression tests for the ARB reviewer-side AI pre-brief.

The ARB flow already let a submitter draft a submission with AI; the
reviewer side had nothing — no pre-brief, no conflict surfacing, no draft
disposition. This pins the new POST /arb/api/reviews/<id>/ai-prebrief:
happy path returns the parsed JSON pre-brief, an unparseable/failing LLM
call is a 502 (never a fabricated fallback), an unknown review is a 404,
and the endpoint is AI-gated (503 when no LLM is configured).

Uses the shared fixtures in tests/conftest.py (db_session rolls everything
back) and the logged-in-client / auth-cache pattern from
tests/test_bounded_ai_endpoints.py, per CLAUDE.md.
"""

from __future__ import annotations

import json
import uuid

import pytest


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_org(db_session, make_org, client):
    """A confirmed user in a fresh org, logged into the test client."""
    from app.models.user import User

    org = make_org("arb-ai")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"arb-ai-{suffix}@example.com",
        first_name="ARB",
        last_name="Reviewer",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    db_session.add(user)
    db_session.flush()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True

    _clear_auth_caches()
    return org, user


def _clear_auth_caches():
    """Anything that touches current_user on the shared app context
    re-caches an anonymous user in `g`; call this right before each
    test-client request."""
    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)


def _make_review(db_session, org, user, **overrides):
    from app.models.architecture_review_board import ARBReviewItem

    suffix = uuid.uuid4().hex[:8]
    kwargs = dict(
        review_number=f"REV-{suffix}",
        title="Customer 360 platform review",
        description="Consolidating CRM + support into one platform.",
        review_type="solution_architecture",
        status="submitted",
        submitter_id=user.id,
        organization_id=org.id,
    )
    kwargs.update(overrides)
    review = ARBReviewItem(**kwargs)
    db_session.add(review)
    db_session.flush()
    return review


_VALID_LLM_JSON = json.dumps(
    {
        "summary": "A solution architecture review for a customer platform consolidation.",
        "key_risks": ["Data migration risk", "Vendor lock-in"],
        "questions_for_submitter": ["What is the rollback plan?"],
        "conflicts_or_overlaps": [],
        "draft_disposition": "approved_with_conditions",
        "draft_conditions": ["Provide a rollback plan before go-live"],
        "rationale": "Sound approach but needs a documented rollback plan.",
    }
)


def test_ai_prebrief_happy_path(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org

    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.architecture.services.arb_review_ai_service as svc_module
    monkeypatch.setattr(
        svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: _VALID_LLM_JSON)
    )

    review = _make_review(db_session, org, user)
    _clear_auth_caches()

    resp = client.post(f"/arb/api/reviews/{review.id}/ai-prebrief")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    prebrief = data["prebrief"]
    assert prebrief["draft_disposition"] == "approved_with_conditions"
    assert prebrief["key_risks"] == ["Data migration risk", "Vendor lock-in"]
    assert prebrief["draft_conditions"] == ["Provide a rollback plan before go-live"]

    # Advisory only: nothing was written back to the review.
    db_session.refresh(review)
    assert review.decision is None


def test_ai_prebrief_llm_failure_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org

    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.architecture.services.arb_review_ai_service as svc_module

    def _boom(*a, **k):
        raise RuntimeError("LLM provider unavailable")

    monkeypatch.setattr(svc_module.LLMService, "generate_from_prompt", staticmethod(_boom))

    review = _make_review(db_session, org, user)
    _clear_auth_caches()

    resp = client.post(f"/arb/api/reviews/{review.id}/ai-prebrief")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_ai_prebrief_unparseable_llm_output_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org

    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.architecture.services.arb_review_ai_service as svc_module
    monkeypatch.setattr(
        svc_module.LLMService,
        "generate_from_prompt",
        staticmethod(lambda *a, **k: "not json at all"),
    )

    review = _make_review(db_session, org, user)
    _clear_auth_caches()

    resp = client.post(f"/arb/api/reviews/{review.id}/ai-prebrief")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_ai_prebrief_unknown_review_is_404(logged_in_org, client, monkeypatch):
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    _clear_auth_caches()
    resp = client.post("/arb/api/reviews/999999999/ai-prebrief")
    assert resp.status_code == 404


def test_ai_prebrief_disabled_is_503(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org

    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: False)

    review = _make_review(db_session, org, user)
    _clear_auth_caches()

    resp = client.post(f"/arb/api/reviews/{review.id}/ai-prebrief")
    assert resp.status_code == 503
