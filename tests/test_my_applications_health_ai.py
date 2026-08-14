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


def test_health_overview_renders_all_status_sections(db_session, make_org, logged_in_org, client):
    """health_overview.html reads top-level `critical`/`at_risk`/`healthy`/`unknown`
    vars, but the route only ever passed `by_health` (a dict keyed by status) -- so
    every category section was permanently empty regardless of what applications
    the user owned. Owning at least one app per status must make that app's name
    show up in the rendered page."""
    org, user = logged_in_org

    critical_app = _make_app(db_session, org, name=f"Critical App {uuid.uuid4().hex[:8]}", health_status="critical")
    at_risk_app = _make_app(db_session, org, name=f"AtRisk App {uuid.uuid4().hex[:8]}", health_status="at_risk")
    healthy_app = _make_app(db_session, org, name=f"Healthy App {uuid.uuid4().hex[:8]}", health_status="healthy")

    for a in (critical_app, at_risk_app, healthy_app):
        _make_ownership(db_session, org, user, a)
    _clear_auth_caches()

    resp = client.get("/my-applications/health")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert critical_app.name in html
    assert at_risk_app.name in html
    assert healthy_app.name in html


# ---------------------------------------------------------------------------
# GET /my-applications/app/<id>/edit with ?suggest_health=&suggest_lifecycle=
#
# The AI health assessment's "Apply suggestion" link lands here. This must
# only affect what the form pre-selects -- never mutate the session-attached
# ApplicationComponent, or any later commit in the same request would
# persist an AI suggestion nobody reviewed or submitted.
# ---------------------------------------------------------------------------


def _edit_url(app_id, **params):
    from urllib.parse import urlencode

    url = f"/my-applications/app/{app_id}/edit"
    if params:
        url += "?" + urlencode(params)
    return url


def test_app_edit_get_with_suggestion_params_does_not_dirty_db_row(
    db_session, make_org, logged_in_org, client
):
    """A GET with suggest_health/suggest_lifecycle must not change the
    stored row at all -- not even after the request completes."""
    org, user = logged_in_org

    application = _make_app(
        db_session, org, health_status="healthy", lifecycle_status="planning"
    )
    _make_ownership(db_session, org, user, application)
    _clear_auth_caches()

    resp = client.get(
        _edit_url(application.id, suggest_health="critical", suggest_lifecycle="deprecated")
    )
    assert resp.status_code == 200

    db_session.refresh(application)
    assert application.health_status == "healthy"
    assert application.lifecycle_status == "planning"


def test_app_edit_get_with_suggestion_params_preselects_suggested_value(
    db_session, make_org, logged_in_org, client
):
    """The rendered form must preselect the suggested value even though the
    stored row is untouched -- confirming the template, not the model, now
    carries the prefill."""
    org, user = logged_in_org

    application = _make_app(
        db_session, org, health_status="healthy", lifecycle_status="planning"
    )
    _make_ownership(db_session, org, user, application)
    _clear_auth_caches()

    resp = client.get(
        _edit_url(application.id, suggest_health="critical", suggest_lifecycle="deprecated")
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    import re

    health_select = re.search(r'<select id="health_status".*?</select>', html, re.DOTALL).group(0)
    assert '<option value="critical" selected>' in health_select

    lifecycle_select = re.search(
        r'<select id="lifecycle_status".*?</select>', html, re.DOTALL
    ).group(0)
    assert '<option value="deprecated" selected>' in lifecycle_select


def test_app_edit_get_with_out_of_vocabulary_suggestion_is_ignored(
    db_session, make_org, logged_in_org, client
):
    """A stale link or hand-edited URL naming a value outside the pinned
    vocabulary must fall back to the stored value, silently."""
    org, user = logged_in_org

    application = _make_app(
        db_session, org, health_status="healthy", lifecycle_status="planning"
    )
    _make_ownership(db_session, org, user, application)
    _clear_auth_caches()

    resp = client.get(_edit_url(application.id, suggest_health="not_a_real_status"))
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    import re

    health_select = re.search(r'<select id="health_status".*?</select>', html, re.DOTALL).group(0)
    assert '<option value="healthy" selected>' in health_select

    db_session.refresh(application)
    assert application.health_status == "healthy"
