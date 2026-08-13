"""Bounded-work regression tests for the two endpoints that hung workers.

Design-review P0 wave, Task 4:

- GET /api/ea-workflows/sa/application-patterns issued one LLM call per
  batch of 50 apps, sequentially, in-request — 920 apps stalled a crawl for
  10+ minutes twice. The service now takes a wall-clock budget; apps not
  reached in time fall to the deterministic rule engine, every record is
  labelled with its engine, and the aggregate reports the split.

- GET /dashboard/api/applications/merging/candidates ran an O(n²)
  SequenceMatcher pair scan over the whole portfolio in-request. The route
  now caps the comparison set and the scan's wall clock, and the response
  carries an explicit ``truncated`` flag — a silently partial duplicate
  analysis reads as "no further duplicates exist".

Uses the shared fixtures in tests/conftest.py (db_session rolls back).
"""

from __future__ import annotations

import time
import uuid

import pytest


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_org(db_session, make_org, client):
    """A confirmed user in a fresh org, logged into the test client.

    Clears the flask-login/tenant caches on the shared app context — see
    tests/test_ba_tenant_and_authz.py::_login for why the cookie alone is
    not enough under these fixtures.
    """
    from app.models.user import User

    org = make_org("bounded-ai")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"bounded-{suffix}@example.com",
        first_name="Bounded",
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

    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)
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


def _make_apps(db_session, org, count):
    from app.models.application_portfolio import ApplicationComponent

    suffix = uuid.uuid4().hex[:6]
    apps = [
        ApplicationComponent(
            name=f"Bounded App {suffix} {i}",
            organization_id=org.id,
            lifecycle_status="active",
        )
        for i in range(count)
    ]
    db_session.add_all(apps)
    db_session.flush()
    return apps


# ---------------------------------------------------------------- classifier


def test_classifier_time_budget_stops_llm_and_says_so(
    db_session, tenant_ctx, make_org, monkeypatch
):
    """A slow LLM must not be called past the budget; the rest is labelled
    rules and llm_truncated is reported."""
    import app.services.application_pattern_classifier_service as svc_module

    org = make_org("classifier")
    apps = _make_apps(db_session, org, 3)

    calls = []

    def slow_llm_batch(batch):
        calls.append(len(batch))
        time.sleep(0.2)
        return [
            {"id": a.id, "arch_pattern": "saas", "confidence": 0.9, "source": "llm"}
            for a in batch
        ]

    monkeypatch.setattr(svc_module, "_llm_classify_batch", slow_llm_batch)

    with tenant_ctx(org.id):
        svc = svc_module.ApplicationPatternClassifierService()
        records = svc.classify_applications(
            app_ids=[a.id for a in apps],
            batch_size=1,
            time_budget_seconds=0.1,
        )

    assert len(records) == len(apps)
    assert svc.llm_truncated is True
    assert len(calls) < len(apps), "LLM kept being called after the budget"
    sources = {r["source"] for r in records}
    assert "rules" in sources, "post-budget apps must be labelled rule-based"
    assert all(r["source"] in ("llm", "rules") for r in records)


def test_application_patterns_endpoint_responds_and_reports_split(
    client, logged_in_org, db_session, monkeypatch
):
    import app.services.application_pattern_classifier_service as svc_module

    _make_apps(db_session, logged_in_org, 2)

    def fake_llm_batch(batch):
        return [
            {"id": a.id, "arch_pattern": "monolith", "confidence": 0.8, "source": "llm"}
            for a in batch
        ]

    monkeypatch.setattr(svc_module, "_llm_classify_batch", fake_llm_batch)

    _clear_auth_caches()
    response = client.get("/api/ea-workflows/sa/application-patterns")
    assert response.status_code != 401, "login did not take"
    assert response.status_code == 200, response.get_data(as_text=True)[:500]
    patterns = response.get_json()["patterns"]
    assert "by_source" in patterns
    assert "llm_truncated" in patterns
    assert patterns["classified"] >= 2


# ------------------------------------------------------------------- merging


def test_merge_candidates_bounded_and_flagged(client, logged_in_org, db_session):
    _make_apps(db_session, logged_in_org, 5)

    _clear_auth_caches()
    response = client.get(
        "/dashboard/api/applications/merging/candidates?max_apps=2"
    )
    assert response.status_code != 401, "login did not take"
    assert response.status_code == 200, response.get_data(as_text=True)[:500]
    data = response.get_json()
    assert data["truncated"] is True
    assert data["total_analyzed"] == 2
    assert data["total_applications"] >= 5


def test_merge_candidates_unbounded_small_portfolio_not_flagged(
    client, logged_in_org, db_session
):
    _make_apps(db_session, logged_in_org, 3)

    _clear_auth_caches()
    response = client.get("/dashboard/api/applications/merging/candidates")
    assert response.status_code == 200, response.get_data(as_text=True)[:500]
    data = response.get_json()
    assert data["truncated"] is False
    assert data["total_analyzed"] == data["total_applications"]


def test_pair_scan_time_budget_sets_truncated():
    """The service-level wall-clock bound trips and is visible to callers."""
    from app.modules.applications.services.application_merging_service import (
        ApplicationMatchingService,
        MergeConfig,
    )

    class FakeApp:
        def __init__(self, i):
            self.id = i
            # Distinct enough that no pair crosses the 0.99 threshold — the
            # test exercises the budget, not candidate construction.
            self.name = uuid.uuid4().hex
            self.description = uuid.uuid4().hex * 20

    service = ApplicationMatchingService(MergeConfig(similarity_threshold=0.99))
    apps = [FakeApp(i) for i in range(80)]
    service.find_merge_candidates(apps, time_budget_seconds=0.0)
    assert service.truncated is True

    service.find_merge_candidates(apps[:3], time_budget_seconds=30)
    assert service.truncated is False
