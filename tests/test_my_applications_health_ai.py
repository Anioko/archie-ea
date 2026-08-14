"""Regression tests for the Application Manager AI health assessment.

An application manager could already see (and edit) an owned application's
health/lifecycle status but had no help deciding what those values should
be. This pins the new POST /my-applications/api/app/<id>/ai-health-assessment:
happy path returns the parsed JSON assessment, an unparseable/failing LLM
call is a 502 (never a fabricated fallback), an application the caller does
not own 404s even when it exists in their org, and the endpoint is
AI-gated (503 when no LLM is configured). Advisory only: nothing is
written back to the application record.

Uses the shared fixtures in tests/conftest.py (db_session rolls everything
back) and the logged-in-client / auth-cache pattern from
tests/test_arb_review_ai.py, per CLAUDE.md.
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
    """A confirmed application_manager user in a fresh org, logged into the test client."""
    from app.models.user import User

    org = make_org("my-apps-ai")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"my-apps-ai-{suffix}@example.com",
        first_name="App",
        last_name="Manager",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="application_manager",
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


def _make_app(db_session, org, **overrides):
    from app.models.application_portfolio import ApplicationComponent

    suffix = uuid.uuid4().hex[:8]
    kwargs = dict(
        name=f"Customer Portal {suffix}",
        description="Public-facing customer self-service portal.",
        lifecycle_status="operational",
        health_status="at_risk",
        business_criticality="High",
        organization_id=org.id,
    )
    kwargs.update(overrides)
    component = ApplicationComponent(**kwargs)
    db_session.add(component)
    db_session.flush()
    return component


def _make_ownership(db_session, org, user, application, **overrides):
    from app.models.application_owner import ApplicationOwner

    kwargs = dict(
        application_id=application.id,
        user_id=user.id,
        organization_id=org.id,
        ownership_type="primary",
    )
    kwargs.update(overrides)
    ownership = ApplicationOwner(**kwargs)
    db_session.add(ownership)
    db_session.flush()
    return ownership


_VALID_LLM_JSON = json.dumps(
    {
        "summary": "The customer portal is operational but showing early signs of strain.",
        "suggested_health_status": "at_risk",
        "suggested_lifecycle_status": "operational",
        "signals": ["No recent health reassessment", "High business criticality with at-risk health"],
        "recommended_actions": ["Schedule a health review", "Confirm the technical owner"],
        "rationale": "Business criticality is high while health is already flagged at-risk.",
    }
)


def _endpoint(app_id):
    return f"/my-applications/api/app/{app_id}/ai-health-assessment"


def test_ai_health_assessment_happy_path(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org

    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.my_applications.health_ai_service as svc_module
    monkeypatch.setattr(
        svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: _VALID_LLM_JSON)
    )

    application = _make_app(db_session, org)
    _make_ownership(db_session, org, user, application)
    _clear_auth_caches()

    resp = client.post(_endpoint(application.id))
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assessment = data["assessment"]
    assert assessment["suggested_health_status"] == "at_risk"
    assert assessment["suggested_lifecycle_status"] == "operational"
    assert assessment["signals"] == [
        "No recent health reassessment",
        "High business criticality with at-risk health",
    ]
    assert assessment["recommended_actions"] == [
        "Schedule a health review",
        "Confirm the technical owner",
    ]

    # Advisory only: nothing was written back to the application.
    db_session.refresh(application)
    assert application.health_status == "at_risk"
    assert application.lifecycle_status == "operational"


def test_ai_health_assessment_llm_failure_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org

    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.my_applications.health_ai_service as svc_module

    def _boom(*a, **k):
        raise RuntimeError("LLM provider unavailable")

    monkeypatch.setattr(svc_module.LLMService, "generate_from_prompt", staticmethod(_boom))

    application = _make_app(db_session, org)
    _make_ownership(db_session, org, user, application)
    _clear_auth_caches()

    resp = client.post(_endpoint(application.id))
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_ai_health_assessment_unparseable_llm_output_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org

    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    import app.modules.my_applications.health_ai_service as svc_module
    monkeypatch.setattr(
        svc_module.LLMService,
        "generate_from_prompt",
        staticmethod(lambda *a, **k: "not json at all"),
    )

    application = _make_app(db_session, org)
    _make_ownership(db_session, org, user, application)
    _clear_auth_caches()

    resp = client.post(_endpoint(application.id))
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_ai_health_assessment_disabled_is_503(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org

    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: False)

    application = _make_app(db_session, org)
    _make_ownership(db_session, org, user, application)
    _clear_auth_caches()

    resp = client.post(_endpoint(application.id))
    assert resp.status_code == 503


def test_ai_health_assessment_not_owned_is_404(db_session, make_org, logged_in_org, client, monkeypatch):
    """An application that exists in the user's org, but has no
    ApplicationOwner row for this user, must 404 exactly like an unknown
    application id -- the whole point of the persona is the owned subset."""
    org, user = logged_in_org

    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    application = _make_app(db_session, org)
    # Deliberately no ApplicationOwner row for this user.
    _clear_auth_caches()

    resp = client.post(_endpoint(application.id))
    assert resp.status_code == 404


def test_ai_health_assessment_unknown_app_is_404(logged_in_org, client, monkeypatch):
    from app.services.feature_flag_service import FeatureFlagService
    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)

    _clear_auth_caches()
    resp = client.post(_endpoint(999999999))
    assert resp.status_code == 404
