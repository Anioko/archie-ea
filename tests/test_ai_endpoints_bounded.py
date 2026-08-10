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

FIX-REPORT ADDENDUM (post-review)
----------------------------------
A review of the first pass found a spec gap and two Important defects, all
fixed here and covered by the tests added at the bottom of this file:

1. SPEC GAP — only DeepSeek got a client-level timeout; OpenAI (90s),
   Anthropic (85s), OpenRouter (10s/80s) stayed above the brief's ``<=60s``
   ceiling on this path. Fixed by threading an optional ``timeout`` override
   through ``generate_from_prompt`` -> ``_call_llm`` ->
   ``_call_llm_with_failover`` -> every per-provider ``_call_*`` function in
   llm_service_impl.py, defaulting to each provider's previous value when
   unset (so every OTHER caller is unaffected), and having the classifier
   pass ``timeout=LLM_CLASSIFY_TIMEOUT_SECONDS`` (60s) explicitly.
2. IMPORTANT — the background ``ThreadPoolExecutor`` call ran with no Flask
   app context, so a call that completed *after* its request had already
   timed out (504 returned) would raise inside ``_call_llm``'s db.session
   writes (interaction logging / cache write) with nothing ever observing
   it. Fixed by wrapping the submitted callable in
   ``app.app_context()`` (app captured via
   ``current_app._get_current_object()`` at submit time) and attaching
   ``future.add_done_callback(_log_orphaned_future_exception)`` so any
   exception from the orphaned call is logged instead of silently dropped.
3. IMPORTANT — the merge-candidates truncation note said "re-run to cover
   the rest", but the cap was ``order_by(id).limit(200)`` with no offset:
   re-running returned the identical lowest-id window forever, and any app
   past the 200th-lowest id was permanently invisible to merge detection.
   Fixed by adding an ``offset`` query parameter (``order_by(id).offset(...)
   .limit(...)``) plus ``next_offset``/``offset`` in the response, and
   rewriting the note to say plainly that windows don't cross-compare
   (a duplicate pair split across two windows still won't be found) and how
   to page through with ``offset`` to reach every application.
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
    # The note must not claim a plain re-run covers more ground than a
    # deterministic order_by(id).limit(cap) can (Important 2) — it must
    # instead point at the actual mechanism (offset) that does.
    assert "offset" in body["truncation_note"]
    assert body["offset"] == 0
    assert body["next_offset"] == 2


def test_merge_candidates_offset_pages_through_the_portfolio(
    app, db_session, make_org, monkeypatch
):
    """Important 2 regression: re-running with the reported next_offset must
    reach applications past the first window — the old deterministic
    order_by(id).limit(cap) with no offset made anything past the cap
    permanently invisible no matter how many times the endpoint was called."""
    import app.api.application_merging_routes as merging_mod

    client, org, apps = _make_logged_in_client(
        app, db_session, make_org, "merging-paged", app_count=5
    )
    monkeypatch.setattr(merging_mod, "MAX_MERGE_CANDIDATE_APPLICATIONS", 2)

    first = client.get("/dashboard/api/applications/merging/candidates").get_json()
    assert first["offset"] == 0
    assert first["next_offset"] == 2

    second = client.get(
        f"/dashboard/api/applications/merging/candidates?offset={first['next_offset']}"
    ).get_json()
    assert second["offset"] == 2
    assert second["total_analyzed"] == 2
    assert second["next_offset"] == 4

    third = client.get(
        f"/dashboard/api/applications/merging/candidates?offset={second['next_offset']}"
    ).get_json()
    assert third["offset"] == 4
    assert third["total_analyzed"] == 1  # last app, window shorter than the cap
    assert third["next_offset"] is None  # no more pages — the portfolio is covered

    # Every one of the 5 seeded apps' ids appeared in exactly one window's
    # sorted order across the three calls (offsets 0, 2, 4 covering a 5-row,
    # cap-2 portfolio) — i.e. no app is permanently stuck outside every window.
    total_analyzed_across_pages = (
        first["total_analyzed"] + second["total_analyzed"] + third["total_analyzed"]
    )
    assert total_analyzed_across_pages == len(apps) == 5


# --------------------------------------------------------------------------
# Important 1: the executor thread must have a Flask app context, and an
# exception from an orphaned (post-timeout) call must be logged, not dropped
# --------------------------------------------------------------------------


def test_classify_batch_runs_generate_from_prompt_inside_app_context(
    app, db_session, make_org
):
    """Regression for Important 1: the background call used to run with no
    Flask context at all. If that regresses, LLMService.generate_from_prompt
    (or whatever it calls) touching current_app/db.session raises inside the
    executor thread — which the mock below simulates by asserting
    has_app_context() itself, rather than relying on an incidental db write
    to surface the bug."""
    from flask import has_app_context

    from app.services.application_pattern_classifier_service import (
        ApplicationPatternClassifierService,
    )
    from app.modules.ai_chat.services import llm_service_impl as llm_impl

    client, org, apps = _make_logged_in_client(
        app, db_session, make_org, "patterns-ctx", app_count=1
    )

    seen_has_app_context = {}

    def _context_asserting_generate(prompt, *args, **kwargs):
        seen_has_app_context["value"] = has_app_context()
        if not has_app_context():
            # What would actually happen without the app.app_context() wrap:
            raise RuntimeError("Working outside of application context.")
        return (
            '[{"id": %d, "arch_pattern": "microservice", "confidence": 0.9, '
            '"reasoning": "test"}]' % apps[0].id
        )

    import unittest.mock as mock

    with mock.patch.object(
        llm_impl.LLMService, "generate_from_prompt", staticmethod(_context_asserting_generate)
    ):
        resp = client.get("/api/ea-workflows/sa/application-patterns")

    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    assert seen_has_app_context.get("value") is True
    body = resp.get_json()
    # If the executor thread had no app context, generate_from_prompt would
    # have raised, and the (non-timeout) broad except in _llm_classify_batch
    # would have silently substituted rule-based data — this app has no
    # signal that would rule-classify as "microservice", so seeing that
    # pattern here proves the LLM path actually ran, not the fallback.
    assert body["patterns"]["by_pattern"].get("microservice") == 1


def test_orphaned_future_exception_is_logged_not_dropped(caplog):
    """Unit test for the done-callback itself (Important 1): an exception
    raised by an abandoned background call must be logged — previously
    nothing ever called .result()/.exception() on it again, so it vanished
    silently (the "73 catch blocks that told nobody" anti-pattern)."""
    import concurrent.futures
    import logging

    from app.services import application_pattern_classifier_service as classifier_mod

    def _boom():
        raise ValueError("orphaned call failed after its request timed out")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_boom)
        concurrent.futures.wait([future])
        with caplog.at_level(logging.ERROR, logger=classifier_mod.__name__):
            classifier_mod._log_orphaned_future_exception(future)

    assert any(
        "Orphaned application-pattern LLM call failed" in record.message
        for record in caplog.records
    ), "expected the orphaned future's exception to be logged"


def test_orphaned_future_callback_silent_on_success(caplog):
    """The done-callback must not log anything for a future that completed
    normally — it only exists to surface failures nobody else observes."""
    import concurrent.futures
    import logging

    from app.services import application_pattern_classifier_service as classifier_mod

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(lambda: "ok")
        concurrent.futures.wait([future])
        with caplog.at_level(logging.ERROR, logger=classifier_mod.__name__):
            classifier_mod._log_orphaned_future_exception(future)

    assert not any(
        "Orphaned application-pattern LLM call failed" in record.message
        for record in caplog.records
    )


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
    assert body["offset"] == 0
    assert body["next_offset"] is None
