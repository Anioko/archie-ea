"""Cross-tenant LLM key isolation for the application pattern classifier's
executor thread.

``_llm_classify_batch`` (app/services/application_pattern_classifier_service.py)
hands the LLM call off to a dedicated thread pool because the request thread
must not block on it. That worker thread has no Flask request context of its
own, so app/middleware/tenant_context.py never runs its before_request hook to
set ``g.current_org_id`` there. Without an explicit fix,
app/middleware/tenant_isolation.py's ``do_orm_execute`` treats an absent
``g.current_org_id`` as "no tenant filter" (by design, for CLI/system paths),
so ``APISettings.query.filter_by(enabled=True)`` inside the worker thread would
return EVERY organization's enabled API keys, not just the requesting org's -
letting one tenant's classify call be billed to another tenant's provider
account.

The fix mirrors app/modules/ai_chat/routes/chat_core.py's run_agent(): capture
``g.current_org_id`` on the request thread before submitting to the executor,
then set it again inside the worker's app context. tests/test_ai_chat_tenancy.py
takes the same "assert on source + assert on the live worker" approach this
file follows, for the same reason: the worker executes on a genuinely different
thread, so a test that wrote seed rows via the shared ``db_session`` fixture's
connection would not see them there (that connection/session binding is
per-thread), making a real end-to-end DB round trip through the pool flaky by
construction rather than a faithful reproduction of the bug.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures("db_session")

ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER_SRC = ROOT / "app/services/application_pattern_classifier_service.py"


def test_org_id_is_captured_on_request_thread_before_submit():
    """The tenant must be read on the request thread, before handoff to the
    executor - reading it inside the worker would already be too late,
    because the worker has no before_request handler and g.current_org_id
    would simply be absent there.
    """
    source = CLASSIFIER_SRC.read_text(encoding="utf-8")

    assert "current_org_id as _current_org_id" in source, (
        "_llm_classify_batch no longer imports the tenant helper"
    )

    batch_fn = source.split("def _llm_classify_batch(", 1)
    assert len(batch_fn) == 2, "_llm_classify_batch no longer exists"
    body = batch_fn[1]

    capture = body.find("org_id = _current_org_id()")
    submit = body.find("_llm_classify_executor.submit(")
    assert capture != -1, (
        "the tenant is no longer captured on the request thread inside "
        "_llm_classify_batch; the worker thread would run unscoped"
    )
    assert submit != -1, "executor submit call no longer present"
    assert capture < submit, (
        "org_id must be captured before the executor submit call, while "
        "still on the request thread"
    )


def test_worker_sets_g_current_org_id_before_the_llm_call():
    """Inside the worker, g.current_org_id must be (re)established before
    generate_from_prompt runs - that call chain is what queries
    APISettings.
    """
    source = CLASSIFIER_SRC.read_text(encoding="utf-8")

    worker_fn = source.split("def _call_generate_from_prompt_in_app_context(", 1)
    assert len(worker_fn) == 2, "_call_generate_from_prompt_in_app_context no longer exists"
    body = worker_fn[1]

    assign = body.find("g.current_org_id = org_id")
    call = body.find("LLMService.generate_from_prompt(")
    assert assign != -1, (
        "the worker no longer sets g.current_org_id; every TenantMixin SELECT "
        "made while generating (including the APISettings key lookup) would "
        "run unfiltered across every organisation"
    )
    assert call != -1, "generate_from_prompt call no longer present"
    assert assign < call, (
        "g.current_org_id is set after the LLM call - the key lookup inside "
        "it would already have run unscoped"
    )


def test_classify_batch_worker_thread_observes_the_requesting_org(app, tenant_ctx, monkeypatch):
    """End-to-end through the real executor thread pool (not just source
    inspection): the worker that actually executes the LLM call must see the
    SAME org id the request thread was scoped to.

    Uses in-memory ApplicationComponent instances (never added to a session)
    because _llm_classify_batch only reads plain attributes off them - this
    keeps the test from depending on cross-thread DB session sharing, which
    does not hold for the shared ``db_session`` fixture (see module docstring).
    """
    from app.models.application_portfolio import ApplicationComponent
    from app.services import application_pattern_classifier_service as svc

    comp = ApplicationComponent(id=999001, name="Org-scoped Test App", organization_id=42)

    observed = {}

    def _fake_generate_from_prompt(prompt, use_cache=True, timeout=None):
        from flask import g

        observed["current_org_id"] = getattr(g, "current_org_id", "MISSING")
        # Fail fast so nothing attempts a real network call; the batch falls
        # back to rule-based classification, which is fine for this test -
        # we only care what the worker observed before it failed.
        raise RuntimeError("stub - no real LLM call in this test")

    monkeypatch.setattr(
        "app.services.llm_service.LLMService.generate_from_prompt",
        staticmethod(_fake_generate_from_prompt),
    )

    with tenant_ctx(4242):
        results = svc._llm_classify_batch([comp])

    assert observed["current_org_id"] == 4242, (
        "the classify worker thread ran with a different (or absent) tenant "
        "than the requesting org - this is the cross-tenant LLM key exposure"
    )
    assert results[0]["source"] == "rule_fallback"


def test_api_settings_is_tenant_scoped():
    """Why the miss was a credential leak and not only a data leak."""
    from app.models.mixins.core import TenantMixin
    from app.models.models import APISettings

    assert issubclass(APISettings, TenantMixin), (
        "APISettings is no longer tenant-scoped; if that is deliberate, the "
        "cross-tenant API-key concern in the classifier needs revisiting"
    )
