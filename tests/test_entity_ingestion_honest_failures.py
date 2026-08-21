"""M-03 / I-01: the platform's two entity-ingestion paths (Entity Matching
Assistant chat, and document upload) must never hand back a generic "Sorry, I
encountered an error" / "An internal error occurred" when the real cause is
knowable server-side.

Root causes found by direct reproduction (Flask test client, no LLM configured
in this environment):

- M-03: ``POST /ai-chat/entity-matching`` had no POST handler at all — only a
  GET view existed (app/modules/ai_chat/routes/chat_views.py::entity_matching_view).
  Every chat submit therefore 405'd; the front end's ``response.json()`` threw on
  the HTML error page, and its catch block showed the generic apology
  regardless of what was typed. Confirmed via test client: pre-fix, POST
  returned 405 with an HTML body. There was also a second, independent bug one
  layer down: ChatEntityMatchingService called
  ``MultiDomainChatService.process_message(..., template_name=..., context_data=...)``,
  but that method's real parameters are ``template=`` / ``context=`` — a
  TypeError on every single call, which is why production (which *does* have
  an LLM configured) still errored on every input.

- I-01: ``POST /ai-chat/upload-document`` collapsed every failure — including
  the entirely expected "no LLM provider configured" case — into a bare
  ``{"error": "An internal error occurred"}, 500``. Confirmed via test client
  with no LLM configured: pre-fix this was a 500 with a message giving no hint
  the fix is "configure a provider or use simple parsing".

These tests pin the honest-failure contract in this (LLM-less) test
environment: a named 503 rather than an opaque 500. They do not exercise a
successful extraction — that needs a real LLM call, out of scope for a
database-only test environment — but the routing/plumbing bugs above are
proven fixed because a real code path is reached instead of 405/TypeError.
"""

from __future__ import annotations

import io
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


def _make_user(db_session, make_org, label):
    from app.models.user import User

    org = make_org(f"ingestion-{label}")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"ingestion-{label}-{suffix}@example.com",
        first_name="Ingestion",
        last_name="Test",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    user.password = "Sup3rSecret!23"
    db_session.add(user)
    db_session.flush()
    return user.id, org


def _force_no_llm_provider(monkeypatch):
    """Make the no-provider branch deterministic and fail on any model call."""
    from app.modules.ai_chat.services.llm_service_impl import LLMService

    def _no_provider(*_args, **_kwargs):
        raise ValueError("No LLM provider configured")

    def _llm_must_not_be_called(*_args, **_kwargs):
        raise AssertionError("LLM work ran despite no configured provider")

    monkeypatch.setattr(LLMService, "_get_configured_provider", staticmethod(_no_provider))
    monkeypatch.setattr(LLMService, "_call_llm", staticmethod(_llm_must_not_be_called))


def test_entity_matching_post_route_exists_and_is_not_405(app, db_session, make_org):
    """M-03: the chat UI POSTs to /ai-chat/entity-matching on every message.
    Before the fix, no view function handled POST on this URL and Flask
    returned 405 Method Not Allowed with an HTML body — the front end's
    response.json() call on that body is what threw and produced the generic
    "Sorry, I encountered an error" apology. A 405 here would mean the fix
    regressed."""
    user_id, _ = _make_user(db_session, make_org, "route")
    client = app.test_client()
    _login(client, user_id)

    resp = client.post(
        "/ai-chat/entity-matching",
        json={
            "document_text": "Analytics Engine and Data Integration Platform",
            "user_persona": "enterprise_architect",
            "domain": "architecture",
            "chat_history": [],
        },
    )

    assert resp.status_code != 405, (
        "POST /ai-chat/entity-matching returned 405 — the route regressed to "
        "only handling GET"
    )
    # JSON body either way (success or an honest failure) — never the
    # Werkzeug HTML 405 page the old bug produced.
    assert resp.is_json, resp.get_data(as_text=True)[:500]


def test_entity_matching_honest_failure_names_llm_not_configured(
    app, db_session, make_org, monkeypatch
):
    """With no LLM provider configured in this test environment, the route
    must say so explicitly (503 + LLM_NOT_CONFIGURED) rather than collapsing
    into a generic 500 apology or a silent "0 matches" success — the actual
    QA-observed symptom was success:false with a useless error, or (after the
    template_name= / context_data= TypeError fix alone) a silent success with
    zero everything and no explanation."""
    user_id, _ = _make_user(db_session, make_org, "honest")
    _force_no_llm_provider(monkeypatch)
    client = app.test_client()
    _login(client, user_id)

    resp = client.post(
        "/ai-chat/entity-matching",
        json={
            "document_text": "Analytics Engine and Data Integration Platform",
            "user_persona": "enterprise_architect",
            "domain": "architecture",
            "chat_history": [],
        },
    )

    body = resp.get_json()
    assert body is not None, resp.get_data(as_text=True)[:500]

    assert resp.status_code == 503, resp.get_data(as_text=True)[:1000]
    assert body.get("success") is False
    assert body.get("code") == "LLM_NOT_CONFIGURED"
    assert "sorry" not in body.get("error", "").lower()
    assert "internal error occurred" not in body.get("error", "").lower()


def test_upload_document_honest_failure_names_llm_not_configured(
    app, db_session, make_org, monkeypatch
):
    """I-01: with no LLM provider configured, document upload must return a
    503 naming the real cause, not the generic {"error": "An internal error
    occurred"}, 500 the QA register observed."""
    user_id, _ = _make_user(db_session, make_org, "upload")
    _force_no_llm_provider(monkeypatch)
    client = app.test_client()
    _login(client, user_id)

    data = {
        "file": (
            io.BytesIO(b"Analytics Engine and Data Integration Platform are core systems."),
            "test.txt",
        ),
        "analysis_context": "general",
        "preview_only": "true",
    }
    resp = client.post(
        "/ai-chat/upload-document", data=data, content_type="multipart/form-data"
    )

    body = resp.get_json()
    assert body is not None, resp.get_data(as_text=True)[:500]

    assert resp.status_code == 503, resp.get_data(as_text=True)[:1000]
    assert body.get("success") is False
    assert body.get("code") == "LLM_NOT_CONFIGURED"
    assert body.get("error") != "An internal error occurred"


def test_upload_document_missing_file_still_returns_400(app, db_session, make_org):
    """Sanity check the honest-failure change did not disturb ordinary
    validation, which must still 400 before any LLM/provider code runs."""
    user_id, _ = _make_user(db_session, make_org, "novalidation")
    client = app.test_client()
    _login(client, user_id)

    resp = client.post("/ai-chat/upload-document", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
