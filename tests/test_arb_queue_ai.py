"""Regression tests for the ARB queue clerk AI endpoints.

The reviewer side already got an AI pre-brief per review
(tests/test_arb_review_ai.py). The board-secretary side had nothing: no
help triaging the raw pending queue, no agenda draft for an upcoming
session, no minutes draft from decisions already recorded. This pins the
three new endpoints:

- POST /arb/api/queue/ai-triage
- POST /arb/api/sessions/<id>/ai-agenda
- POST /arb/api/sessions/<id>/ai-minutes-draft

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
    """A confirmed user in a fresh org, logged into the test client."""
    from app.models.user import User

    org = make_org("arb-queue-ai")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"arb-queue-ai-{suffix}@example.com",
        first_name="ARB",
        last_name="Secretary",
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
        priority="high",
        submitter_id=user.id,
        organization_id=org.id,
    )
    kwargs.update(overrides)
    review = ARBReviewItem(**kwargs)
    db_session.add(review)
    db_session.flush()
    return review


def _make_session(db_session, org, user, **overrides):
    from app.models.architecture_review_board import ArchitectureReviewBoard
    from datetime import datetime

    suffix = uuid.uuid4().hex[:8]
    kwargs = dict(
        board_number=f"ARB-{suffix}",
        name="Q3 Architecture Review Board",
        scheduled_date=datetime.utcnow(),
        chair_id=user.id,
        organization_id=org.id,
    )
    kwargs.update(overrides)
    session = ArchitectureReviewBoard(**kwargs)
    db_session.add(session)
    db_session.flush()
    return session


def _enable_ai(monkeypatch):
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: True)


def _disable_ai(monkeypatch):
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(FeatureFlagService, "is_ai_enabled", lambda feature: False)


def _mock_llm(monkeypatch, value_or_fn):
    import app.modules.architecture.services.arb_queue_ai_service as svc_module

    if callable(value_or_fn) and not isinstance(value_or_fn, str):
        monkeypatch.setattr(svc_module.LLMService, "generate_from_prompt", staticmethod(value_or_fn))
    else:
        monkeypatch.setattr(
            svc_module.LLMService, "generate_from_prompt", staticmethod(lambda *a, **k: value_or_fn)
        )


# ---------------------------------------------------------------------------
# 1. Queue triage
# ---------------------------------------------------------------------------


def test_queue_triage_happy_path(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _enable_ai(monkeypatch)

    review = _make_review(db_session, org, user, status="submitted")

    triage_json = json.dumps(
        {
            "summary": "One item awaiting review.",
            "items": [
                {
                    "review_number": review.review_number,
                    "title": review.title,
                    "complexity": "standard",
                    "reason": "Straightforward platform consolidation.",
                }
            ],
            "suggested_order": [review.review_number],
        }
    )
    _mock_llm(monkeypatch, triage_json)
    _clear_auth_caches()

    resp = client.post("/arb/api/queue/ai-triage")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    triage = data["triage"]
    assert triage["items"][0]["review_number"] == review.review_number
    assert triage["items"][0]["complexity"] == "standard"
    assert triage["suggested_order"] == [review.review_number]

    # Advisory only: review row unchanged.
    db_session.refresh(review)
    assert review.status == "submitted"


def test_queue_triage_empty_queue_returns_null_without_llm_call(
    db_session, make_org, logged_in_org, client, monkeypatch
):
    _enable_ai(monkeypatch)

    called = {"n": 0}

    def _boom(*a, **k):
        called["n"] += 1
        raise AssertionError("LLM should not be called for an empty queue")

    _mock_llm(monkeypatch, _boom)
    _clear_auth_caches()

    resp = client.post("/arb/api/queue/ai-triage")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["triage"] is None
    assert data["message"] == "No pending reviews"
    assert called["n"] == 0


def test_queue_triage_llm_failure_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _enable_ai(monkeypatch)
    _make_review(db_session, org, user, status="submitted")

    def _boom(*a, **k):
        raise RuntimeError("LLM provider unavailable")

    _mock_llm(monkeypatch, _boom)
    _clear_auth_caches()

    resp = client.post("/arb/api/queue/ai-triage")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_queue_triage_unparseable_llm_output_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _enable_ai(monkeypatch)
    _make_review(db_session, org, user, status="submitted")

    _mock_llm(monkeypatch, "not json at all")
    _clear_auth_caches()

    resp = client.post("/arb/api/queue/ai-triage")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_queue_triage_drops_invented_review_number(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _enable_ai(monkeypatch)
    review = _make_review(db_session, org, user, status="submitted")

    triage_json = json.dumps(
        {
            "summary": "Two items.",
            "items": [
                {
                    "review_number": review.review_number,
                    "title": review.title,
                    "complexity": "standard",
                    "reason": "Real review.",
                },
                {
                    "review_number": "REV-9999-999",
                    "title": "An invented review",
                    "complexity": "contentious",
                    "reason": "Hallucinated.",
                },
            ],
            "suggested_order": [review.review_number, "REV-9999-999"],
        }
    )
    _mock_llm(monkeypatch, triage_json)
    _clear_auth_caches()

    resp = client.post("/arb/api/queue/ai-triage")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    triage = resp.get_json()["triage"]
    review_numbers = [item["review_number"] for item in triage["items"]]
    assert review_numbers == [review.review_number]
    assert triage["suggested_order"] == [review.review_number]


def test_queue_triage_disabled_is_503(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _disable_ai(monkeypatch)
    _make_review(db_session, org, user, status="submitted")
    _clear_auth_caches()

    resp = client.post("/arb/api/queue/ai-triage")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# 2. Session agenda draft
# ---------------------------------------------------------------------------


def test_session_agenda_happy_path(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _enable_ai(monkeypatch)

    session = _make_session(db_session, org, user)
    review = _make_review(db_session, org, user, status="submitted", arb_session_id=session.id)

    agenda_json = json.dumps(
        {
            "summary": "One item on the agenda.",
            "items": [
                {
                    "review_number": review.review_number,
                    "suggested_minutes": 15,
                    "focus": "Discuss data migration risk.",
                }
            ],
            "sequencing_rationale": "Only one item, straightforward.",
        }
    )
    _mock_llm(monkeypatch, agenda_json)
    _clear_auth_caches()

    resp = client.post(f"/arb/api/sessions/{session.id}/ai-agenda")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    agenda = resp.get_json()["agenda"]
    assert agenda["items"][0]["review_number"] == review.review_number
    assert agenda["items"][0]["suggested_minutes"] == 15

    # Advisory only: session row unchanged.
    db_session.refresh(session)
    assert session.agenda is None


def test_session_agenda_unknown_session_is_404(logged_in_org, client, monkeypatch):
    _enable_ai(monkeypatch)
    _clear_auth_caches()
    resp = client.post("/arb/api/sessions/999999999/ai-agenda")
    assert resp.status_code == 404


def test_session_agenda_llm_failure_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _enable_ai(monkeypatch)
    session = _make_session(db_session, org, user)
    _make_review(db_session, org, user, status="submitted", arb_session_id=session.id)

    def _boom(*a, **k):
        raise RuntimeError("LLM provider unavailable")

    _mock_llm(monkeypatch, _boom)
    _clear_auth_caches()

    resp = client.post(f"/arb/api/sessions/{session.id}/ai-agenda")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_session_agenda_unparseable_llm_output_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _enable_ai(monkeypatch)
    session = _make_session(db_session, org, user)
    _make_review(db_session, org, user, status="submitted", arb_session_id=session.id)

    _mock_llm(monkeypatch, "not json at all")
    _clear_auth_caches()

    resp = client.post(f"/arb/api/sessions/{session.id}/ai-agenda")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_session_agenda_drops_invented_review_number(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _enable_ai(monkeypatch)
    session = _make_session(db_session, org, user)
    review = _make_review(db_session, org, user, status="submitted", arb_session_id=session.id)

    agenda_json = json.dumps(
        {
            "summary": "Agenda.",
            "items": [
                {"review_number": review.review_number, "suggested_minutes": 10, "focus": "Real item."},
                {"review_number": "REV-9999-999", "suggested_minutes": 20, "focus": "Hallucinated item."},
            ],
            "sequencing_rationale": "Ordered by risk.",
        }
    )
    _mock_llm(monkeypatch, agenda_json)
    _clear_auth_caches()

    resp = client.post(f"/arb/api/sessions/{session.id}/ai-agenda")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    agenda = resp.get_json()["agenda"]
    review_numbers = [item["review_number"] for item in agenda["items"]]
    assert review_numbers == [review.review_number]


def test_session_agenda_disabled_is_503(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _disable_ai(monkeypatch)
    session = _make_session(db_session, org, user)
    _clear_auth_caches()

    resp = client.post(f"/arb/api/sessions/{session.id}/ai-agenda")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# 3. Session minutes draft
# ---------------------------------------------------------------------------


def test_session_minutes_happy_path(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _enable_ai(monkeypatch)

    session = _make_session(db_session, org, user)
    review = _make_review(
        db_session,
        org,
        user,
        status="submitted",
        arb_session_id=session.id,
        decision="approved_with_conditions",
        decision_rationale="Sound approach.",
        conditions=["Provide a rollback plan"],
    )

    minutes_json = json.dumps(
        {
            "summary": "One item decided.",
            "decisions": [
                {
                    "review_number": review.review_number,
                    "disposition": "approved_with_conditions",
                    "conditions": ["Provide a rollback plan before go-live"],
                }
            ],
            "actions": ["Submitter to provide rollback plan"],
        }
    )
    _mock_llm(monkeypatch, minutes_json)
    _clear_auth_caches()

    resp = client.post(f"/arb/api/sessions/{session.id}/ai-minutes-draft")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    minutes = resp.get_json()["minutes"]
    assert minutes["decisions"][0]["review_number"] == review.review_number
    assert minutes["decisions"][0]["disposition"] == "approved_with_conditions"

    # Advisory only: session minutes column unchanged.
    db_session.refresh(session)
    assert session.minutes is None


def test_session_minutes_no_recorded_decisions_is_409(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _enable_ai(monkeypatch)
    session = _make_session(db_session, org, user)
    _make_review(db_session, org, user, status="submitted", arb_session_id=session.id, decision=None)

    called = {"n": 0}

    def _boom(*a, **k):
        called["n"] += 1
        raise AssertionError("LLM should not be called with no recorded decisions")

    _mock_llm(monkeypatch, _boom)
    _clear_auth_caches()

    resp = client.post(f"/arb/api/sessions/{session.id}/ai-minutes-draft")
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "No recorded decisions to draft minutes from"
    assert called["n"] == 0


def test_session_minutes_unknown_session_is_404(logged_in_org, client, monkeypatch):
    _enable_ai(monkeypatch)
    _clear_auth_caches()
    resp = client.post("/arb/api/sessions/999999999/ai-minutes-draft")
    assert resp.status_code == 404


def test_session_minutes_llm_failure_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _enable_ai(monkeypatch)
    session = _make_session(db_session, org, user)
    _make_review(db_session, org, user, status="submitted", arb_session_id=session.id, decision="approved")

    def _boom(*a, **k):
        raise RuntimeError("LLM provider unavailable")

    _mock_llm(monkeypatch, _boom)
    _clear_auth_caches()

    resp = client.post(f"/arb/api/sessions/{session.id}/ai-minutes-draft")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_session_minutes_unparseable_llm_output_is_502(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _enable_ai(monkeypatch)
    session = _make_session(db_session, org, user)
    _make_review(db_session, org, user, status="submitted", arb_session_id=session.id, decision="rejected")

    _mock_llm(monkeypatch, "not json at all")
    _clear_auth_caches()

    resp = client.post(f"/arb/api/sessions/{session.id}/ai-minutes-draft")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_session_minutes_drops_invented_review_number(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _enable_ai(monkeypatch)
    session = _make_session(db_session, org, user)
    review = _make_review(
        db_session, org, user, status="submitted", arb_session_id=session.id, decision="approved"
    )

    minutes_json = json.dumps(
        {
            "summary": "Decisions.",
            "decisions": [
                {"review_number": review.review_number, "disposition": "approved", "conditions": []},
                {"review_number": "REV-9999-999", "disposition": "rejected", "conditions": []},
            ],
            "actions": [],
        }
    )
    _mock_llm(monkeypatch, minutes_json)
    _clear_auth_caches()

    resp = client.post(f"/arb/api/sessions/{session.id}/ai-minutes-draft")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    minutes = resp.get_json()["minutes"]
    review_numbers = [d["review_number"] for d in minutes["decisions"]]
    assert review_numbers == [review.review_number]


def test_session_minutes_disabled_is_503(db_session, make_org, logged_in_org, client, monkeypatch):
    org, user = logged_in_org
    _disable_ai(monkeypatch)
    session = _make_session(db_session, org, user)
    _make_review(db_session, org, user, status="submitted", arb_session_id=session.id, decision="approved")
    _clear_auth_caches()

    resp = client.post(f"/arb/api/sessions/{session.id}/ai-minutes-draft")
    assert resp.status_code == 503
