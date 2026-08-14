"""
Server-side tests for the AI-suggest endpoints wired onto the Stakeholder Map
page (app/templates/stakeholders/map.html):

- POST /api/stakeholders/ai/identify
- POST /api/stakeholders/<id>/ai/engagement-strategy

Both live in app/modules/architecture/routes/stakeholder_map_routes.py and
call app.modules.architecture.services.stakeholder_service.StakeholderService.
The LLM call itself is mocked — these tests assert routing, request
validation, the AI-availability gate, and that a backend failure comes back
as a clean JSON error rather than a 500.

Uses the shared fixtures in tests/conftest.py (db_session rolls back).
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_org(db_session, make_org, client):
    """A confirmed user in a fresh org, logged into the test client.

    See tests/test_bounded_ai_endpoints.py::logged_in_org / _clear_auth_caches
    for why the session cookie alone is not enough under the shared fixtures:
    the tenant-isolation flush listener re-caches an anonymous user on `g`.
    """
    from app.models.user import User

    org = make_org("stakeholder-ai")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"stakeholder-ai-{suffix}@example.com",
        first_name="Stakeholder",
        last_name="Tester",
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
    return org


def _clear_auth_caches():
    """Anything that touches current_user on the shared app context (the
    tenant flush listener does, on every seed) re-caches an anonymous user
    in `g`; call this right before each test-client request."""
    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)


def _make_stakeholder(db_session, org, **overrides):
    from app.models.solution_stakeholder import SolutionStakeholder, StakeholderAttitude

    defaults = dict(
        name="CFO",
        description="Chief Financial Officer, accountable for ROI",
        influence_level=5,
        interest_level=5,
        attitude=StakeholderAttitude.SUPPORTER,
        concerns=["ROI must be positive within 18 months"],
        organization_id=org.id,
    )
    defaults.update(overrides)
    s = SolutionStakeholder(**defaults)
    db_session.add(s)
    db_session.flush()
    return s


# --------------------------------------------------------------------- ai/identify


def test_ai_identify_returns_suggestions_when_mocked(client, logged_in_org, db_session, monkeypatch):
    import app.modules.architecture.services.stakeholder_service as svc_module
    import app.modules.architecture.routes.stakeholder_map_routes as routes_module

    fake_suggestions = [
        {
            "name": "CFO",
            "description": "Chief Financial Officer",
            "type": "Executive Sponsor",
            "role": "CFO",
            "department": "Finance",
            "interest": "ROI within 18 months",
        }
    ]

    def fake_identify(self, business_context):
        assert business_context == "Building a customer portal for EU customers."
        return fake_suggestions

    monkeypatch.setattr(
        svc_module.StakeholderService, "identify_stakeholders_from_context", fake_identify
    )
    monkeypatch.setattr(routes_module.FeatureFlagService, "is_ai_enabled", lambda feature="all": True)

    _clear_auth_caches()
    resp = client.post(
        "/api/stakeholders/ai/identify",
        json={"business_context": "Building a customer portal for EU customers."},
    )
    assert resp.status_code != 401, "login did not take"
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    data = resp.get_json()
    assert data["stakeholders"] == fake_suggestions


def test_ai_identify_requires_business_context(client, logged_in_org, monkeypatch):
    import app.modules.architecture.routes.stakeholder_map_routes as routes_module

    monkeypatch.setattr(routes_module.FeatureFlagService, "is_ai_enabled", lambda feature="all": True)

    _clear_auth_caches()
    resp = client.post("/api/stakeholders/ai/identify", json={"business_context": "   "})
    assert resp.status_code == 400
    assert "business_context" in resp.get_json()["error"]


def test_ai_identify_returns_clean_error_when_backend_raises(client, logged_in_org, monkeypatch):
    import app.modules.architecture.services.stakeholder_service as svc_module
    import app.modules.architecture.routes.stakeholder_map_routes as routes_module

    def fake_identify(self, business_context):
        raise RuntimeError("LLM provider timed out")

    monkeypatch.setattr(
        svc_module.StakeholderService, "identify_stakeholders_from_context", fake_identify
    )
    monkeypatch.setattr(routes_module.FeatureFlagService, "is_ai_enabled", lambda feature="all": True)

    _clear_auth_caches()
    resp = client.post(
        "/api/stakeholders/ai/identify", json={"business_context": "Some real context here"}
    )
    assert resp.status_code == 502
    assert resp.status_code != 500
    body = resp.get_json()
    assert "LLM provider timed out" in body["error"]


def test_ai_identify_returns_503_when_ai_not_configured(client, logged_in_org, monkeypatch):
    import app.modules.architecture.routes.stakeholder_map_routes as routes_module

    monkeypatch.setattr(routes_module.FeatureFlagService, "is_ai_enabled", lambda feature="all": False)

    _clear_auth_caches()
    resp = client.post(
        "/api/stakeholders/ai/identify", json={"business_context": "Some real context here"}
    )
    assert resp.status_code == 503
    body = resp.get_json()
    assert body["error"] == "service_unavailable"


# ------------------------------------------------------------ ai/engagement-strategy


def test_ai_engagement_strategy_returns_json_when_mocked(
    client, logged_in_org, db_session, monkeypatch
):
    import app.modules.architecture.services.stakeholder_service as svc_module
    import app.modules.architecture.routes.stakeholder_map_routes as routes_module

    stakeholder = _make_stakeholder(db_session, logged_in_org)

    fake_strategy = {
        "strategy": "manage_closely",
        "communication_frequency": "weekly",
        "communication_channels": ["Executive briefings"],
        "engagement_actions": ["Involve in key decisions"],
        "escalation_path": "Direct escalation to project sponsor",
    }

    def fake_recommend(self, stakeholder_arg):
        assert stakeholder_arg.id == stakeholder.id
        return fake_strategy

    monkeypatch.setattr(
        svc_module.StakeholderService,
        "recommend_engagement_strategy_for_solution_stakeholder",
        fake_recommend,
    )
    monkeypatch.setattr(routes_module.FeatureFlagService, "is_ai_enabled", lambda feature="all": True)

    _clear_auth_caches()
    resp = client.post(f"/api/stakeholders/{stakeholder.id}/ai/engagement-strategy")
    assert resp.status_code != 401, "login did not take"
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    assert resp.get_json() == fake_strategy


def test_ai_engagement_strategy_returns_clean_error_when_backend_raises(
    client, logged_in_org, db_session, monkeypatch
):
    import app.modules.architecture.services.stakeholder_service as svc_module
    import app.modules.architecture.routes.stakeholder_map_routes as routes_module

    stakeholder = _make_stakeholder(db_session, logged_in_org)

    def fake_recommend(self, stakeholder_arg):
        raise ValueError("could not parse LLM response as JSON")

    monkeypatch.setattr(
        svc_module.StakeholderService,
        "recommend_engagement_strategy_for_solution_stakeholder",
        fake_recommend,
    )
    monkeypatch.setattr(routes_module.FeatureFlagService, "is_ai_enabled", lambda feature="all": True)

    _clear_auth_caches()
    resp = client.post(f"/api/stakeholders/{stakeholder.id}/ai/engagement-strategy")
    assert resp.status_code == 502
    assert resp.status_code != 500
    body = resp.get_json()
    assert "could not parse LLM response as JSON" in body["error"]


def test_ai_engagement_strategy_404_for_unknown_stakeholder(client, logged_in_org, monkeypatch):
    import app.modules.architecture.routes.stakeholder_map_routes as routes_module

    monkeypatch.setattr(routes_module.FeatureFlagService, "is_ai_enabled", lambda feature="all": True)

    _clear_auth_caches()
    resp = client.post("/api/stakeholders/999999999/ai/engagement-strategy")
    assert resp.status_code == 404
