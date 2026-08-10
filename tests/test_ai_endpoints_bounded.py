"""Regression tests for Task 4 (P0 wave): AI-backed endpoints that blocked a
worker indefinitely.

WHAT WAS BROKEN
----------------
``GET /api/ea-workflows/sa/application-patterns`` (app/api/sa_phase_c_routes.py)
called ``ApplicationPatternClassifierService.classify_portfolio()``, which
routes through ``LLMService.generate_from_prompt()``. The DeepSeek provider's
OpenAI-compatible client (app/modules/ai_chat/services/llm_service_impl.py
``_call_deepseek``) had no request timeout at all, so a stalled connection
hung the request — and the worker — forever. Even a provider with a timeout
could still exceed a sane response budget once retries and cross-provider
failover are counted. The fix adds a hard ``LLM_CLASSIFY_TIMEOUT_SECONDS``
ceiling around the whole call in ``application_pattern_classifier_service.py``
and requires a timeout to propagate as an error rather than being silently
swallowed into the rule-based fallback (which would return a fabricated-looking
200).

``GET /dashboard/api/applications/merging/candidates``
(app/api/application_merging_routes.py) ran an O(n^2) similarity comparison
(``ApplicationMatchingService.find_merge_candidates``) over every active
application — 10+ minutes in-request on the 920-app QA portfolio. The fix caps
the comparison set to ``MAX_MERGE_CANDIDATE_APPLICATIONS`` and reports the cap
explicitly via ``truncated`` / ``total_active_applications`` in the response,
per the repo's no-silent-caps rule.

Follows the pattern in tests/test_adm_phase_viewpoints.py: shared fixtures from
tests/conftest.py, and the ``_login`` helper from
tests/test_ba_tenant_and_authz.py::_login (pytest-flask reuses one request
context across client calls, so Flask-Login's g-cache must be cleared).
"""

from __future__ import annotations

import time
import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True

    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


def _make_apps(db_session, org, count, prefix):
    from app.models.application_portfolio import ApplicationComponent

    apps = []
    for i in range(count):
        row = ApplicationComponent(
            name=f"{prefix} App {i}",
            organization_id=org.id,
            lifecycle_status="active",
        )
        db_session.add(row)
        apps.append(row)
    db_session.flush()
    return apps


def _make_logged_in_client(app, db_session, make_org, label="ai-bounded", app_count=0):
    """Create an org, a user in it, and (optionally) app_count applications, then
    log in and return a client.

    IMPORTANT: every row must be created and flushed *before* ``_login()`` runs.
    ``client.session_transaction()`` issues its own internal request, whose
    teardown can rebind the global ``db.session`` away from the transactional
    connection ``db_session`` configured — any ``flush()`` issued afterwards
    risks landing on a different connection than the one ``current_user``
    resolution will read from on the next real request, which manifests as a
    401 "Authentication required" that has nothing to do with authentication.
    (Reproduced directly: creating apps after login intermittently orphaned the
    just-created user from the login-time session.) Mirrors the ordering in
    tests/test_adm_phase_viewpoints.py::_make_logged_in_client.
    """
    from app.models.user import User

    org = make_org(label)

    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"{label}-{suffix}@example.com",
        first_name="AI",
        last_name="Bounded",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="procurement",
    )
    db_session.add(user)
    db_session.flush()

    apps = _make_apps(db_session, org, app_count, label) if app_count else []

    client = app.test_client()
    _login(client, user.id)
    return client, org, apps


# --------------------------------------------------------------------------
# application-patterns: outbound LLM call must time out, not hang
# --------------------------------------------------------------------------


def test_application_patterns_times_out_on_hanging_llm_client(
    app, db_session, make_org, monkeypatch
):
    """A stalled/slow LLM client must not hang the request — the endpoint must
    return a JSON error with a 5xx status within the configured bound."""
    import app.services.application_pattern_classifier_service as classifier_mod
    from app.modules.ai_chat.services import llm_service_impl as llm_impl

    client, org, _apps = _make_logged_in_client(
        app, db_session, make_org, "patterns", app_count=1
    )

    def _hanging_generate_from_prompt(prompt, *args, **kwargs):
        # Simulate a client with no/ineffective timeout that stalls well beyond
        # the bound the classifier enforces.
        time.sleep(2.0)
        return "[]"

    # Tiny bound so the test doesn't itself wait 2s+ for the timeout to fire.
    monkeypatch.setattr(classifier_mod, "LLM_CLASSIFY_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(
        llm_impl.LLMService,
        "generate_from_prompt",
        staticmethod(_hanging_generate_from_prompt),
    )

    start = time.time()
    resp = client.get("/api/ea-workflows/sa/application-patterns")
    elapsed = time.time() - start

    assert resp.status_code >= 500, (
        f"expected a 5xx timeout response, got {resp.status_code}: "
        f"{resp.get_data(as_text=True)[:500]}"
    )
    assert resp.status_code < 600
    # Must return promptly (bounded by LLM_CLASSIFY_TIMEOUT_SECONDS), not hang
    # for the full 2s the mocked client is stalling.
    assert elapsed < 2.0, f"endpoint did not respect the timeout bound, took {elapsed:.2f}s"

    body = resp.get_json()
    assert body is not None
    assert "error" in body
    # Never fabricate classification data for a call that timed out.
    assert "patterns" not in body


def test_application_patterns_succeeds_when_llm_responds_in_time(
    app, db_session, make_org, monkeypatch
):
    """Sanity check: a well-behaved (fast) LLM call still returns 200 with
    real data — the timeout bound must not fire on normal-latency calls."""
    import app.services.application_pattern_classifier_service as classifier_mod
    from app.modules.ai_chat.services import llm_service_impl as llm_impl

    client, org, apps = _make_logged_in_client(
        app, db_session, make_org, "patterns-ok", app_count=1
    )

    def _fast_generate_from_prompt(prompt, *args, **kwargs):
        return (
            '[{"id": %d, "arch_pattern": "monolith", "confidence": 0.9, '
            '"reasoning": "test"}]' % apps[0].id
        )

    monkeypatch.setattr(classifier_mod, "LLM_CLASSIFY_TIMEOUT_SECONDS", 5)
    monkeypatch.setattr(
        llm_impl.LLMService,
        "generate_from_prompt",
        staticmethod(_fast_generate_from_prompt),
    )

    resp = client.get("/api/ea-workflows/sa/application-patterns")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    body = resp.get_json()
    assert "patterns" in body
    assert body["patterns"]["classified"] == 1


# --------------------------------------------------------------------------
# merging/candidates: O(n^2) comparison set must be bounded, with a flag
# --------------------------------------------------------------------------


def test_merge_candidates_bounds_comparison_set_and_flags_truncation(
    app, db_session, make_org, monkeypatch
):
    """When the active portfolio exceeds the comparison cap, the endpoint must
    still respond quickly and must say so explicitly (no silent truncation)."""
    import app.api.application_merging_routes as merging_mod

    client, org, _apps = _make_logged_in_client(
        app, db_session, make_org, "merging-big", app_count=5
    )
    # Small cap so the test doesn't need hundreds of rows to exercise truncation.
    monkeypatch.setattr(merging_mod, "MAX_MERGE_CANDIDATE_APPLICATIONS", 2)

    start = time.time()
    resp = client.get("/dashboard/api/applications/merging/candidates")
    elapsed = time.time() - start

    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    assert elapsed < 5.0, f"merge candidates endpoint took too long: {elapsed:.2f}s"

    body = resp.get_json()
    assert body["success"] is True
    assert body["truncated"] is True
    assert body["total_active_applications"] == 5
    assert body["total_analyzed"] == 2
    assert "truncation_note" in body
    assert body["truncation_note"]


def test_merge_candidates_not_truncated_within_cap(app, db_session, make_org, monkeypatch):
    """Below the cap, the endpoint must report truncated: false — the flag is
    meaningful, not always-on."""
    import app.api.application_merging_routes as merging_mod

    client, org, _apps = _make_logged_in_client(
        app, db_session, make_org, "merging-small", app_count=3
    )
    monkeypatch.setattr(merging_mod, "MAX_MERGE_CANDIDATE_APPLICATIONS", 10)

    resp = client.get("/dashboard/api/applications/merging/candidates")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]

    body = resp.get_json()
    assert body["success"] is True
    assert body["truncated"] is False
    assert body["total_active_applications"] == 3
    assert body["total_analyzed"] == 3
    assert "truncation_note" not in body
