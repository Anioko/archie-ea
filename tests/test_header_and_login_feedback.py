"""Global header cleanup + duplicate login confirmation (shell-overhaul Wave 1, Task 4).

Two defects found by design review:

1. The global header (`components/admin_header.html`, on every authenticated
   page via `layouts/admin_base.html`) rendered an LLM provider selector
   (`components/llm_selector.html`, id ``llm-selector-navbar``) whose options
   ("OpenAI (GPT-4, GPT-3.5)", "DeepSeek", ...) come from
   `/api/v1/llm/available` — a list of *configured* providers that has nothing
   to do with what a page like `/dashboard/overview` is showing. Model choice
   belongs inside the AI Chat surface's own Settings, where it already lives
   (`app/templates/ai_chat/index.html`'s `#model-selector`, populated by
   `ArchieChat.transport.loadModels()` in `app/static/js/ai_chat/app.js`) —
   the fix is simply to stop rendering the selector in the global header.

2. Logging in flashes ``"You are now logged in. Welcome back!"`` with category
   ``"success"`` (`app/modules/account/routes/account_routes.py`). The landing
   page after login, `layouts/admin_base.html`, included BOTH
   `partials/_flashes.html` (an inline banner reading
   ``get_flashed_messages()``) AND `components/toast-container.html` (a script
   that also reads ``get_flashed_messages(with_categories=True)`` and raises a
   `Platform.toast`) — the same flash rendered twice, once as a banner and
   once as a toast. The fix keeps the toast (per DESIGN.md: user-facing
   notifications go through `Platform.toast`) and removes the inline banner
   include from `admin_base.html`.

Follows the ``client.get(...)`` + session-login pattern already proven in
``tests/test_sidebar_render.py`` / ``tests/test_remaining_500_routes.py``.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _login(client, user_id):
    """Standard Flask-Login test-client pattern (see test_sidebar_render.py)."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True

    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


def _make_user(db_session, make_org, label, password="Sup3rSecret!23"):
    from app.models.user import User

    org = make_org(f"header-{label}")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"header-{label}-{suffix}@example.com",
        first_name="Header",
        last_name="Tester",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    user.password = password
    db_session.add(user)
    db_session.flush()
    return user, password


def test_dashboard_header_has_no_model_provider_selector(app, db_session, make_org):
    """The global header must not surface LLM provider choice — that belongs
    in AI Chat's own Settings, not on every page in the app."""
    user, _ = _make_user(db_session, make_org, "dash")
    client = app.test_client()
    _login(client, user.id)

    resp = client.get("/dashboard/overview")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]
    html = resp.get_data(as_text=True)

    assert "GPT-4" not in html, "global header still leaks LLM provider names"
    assert "GPT-3.5" not in html, "global header still leaks LLM provider names"
    assert "llm-selector-navbar" not in html, (
        "global header still renders the LLM provider-selector component "
        "(components/llm_selector.html, selector_id='llm-selector-navbar')"
    )


def test_login_success_message_appears_at_most_once(app, db_session, make_org):
    """A single sign-in must produce a single success confirmation, not an
    inline banner AND a toast both saying the same thing."""
    user, password = _make_user(db_session, make_org, "login")
    client = app.test_client()

    resp = client.post(
        "/account/login",
        data={"email": user.email, "password": password, "submit": "Log in"},
        follow_redirects=True,
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]
    html = resp.get_data(as_text=True)

    assert html.count("You are now logged in. Welcome back!") <= 1, (
        "login success message rendered more than once — an inline banner "
        "and a toast both show the same flash"
    )


def test_ai_chat_settings_still_exposes_model_choice(app, db_session, make_org):
    """Model choice must still live somewhere reachable — AI Chat's Settings
    dropdown, driven by the existing provider registry."""
    user, _ = _make_user(db_session, make_org, "chat")
    client = app.test_client()
    _login(client, user.id)

    resp = client.get("/ai-chat")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]
    html = resp.get_data(as_text=True)

    assert 'id="model-selector"' in html, (
        "AI Chat Settings no longer exposes a model selector"
    )
