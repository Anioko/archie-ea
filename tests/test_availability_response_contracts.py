"""Availability and empty-collection response contracts (F500-053).

CI adversarial probes flag 503 responses from three handlers. These tests pin
down unavailable AI conditions, the successful empty framework collection, and
request validation once a feature is enabled.

Scope and boundary doubles (read before trusting a green run)
-------------------------------------------------------------
The real route functions are executed through Flask by registering the real
``unified_ai_chat`` and ``application_mgmt`` blueprints on a bare ``Flask``
app. No application factory, database, Redis, or LLM provider is booted.

Doubles are limited to the boundaries below and are named in each test:

* ``LLMService._get_configured_provider`` is replaced to simulate an
  unconfigured provider (raises ``ValueError``) or a configured one (returns a
  provider/model pair). Nothing here calls an external LLM. A 200 from
  ``/ai-chat/api/health/llm`` under the configured double proves only that the
  handler reports what the resolver returns, not that any provider works.
* ``PageGuideService`` is replaced with an in-memory double for the enabled
  history path; ``current_user`` is replaced with a plain object carrying an
  ``id`` because ``LOGIN_DISABLED`` yields an anonymous user without one.
* ``ElementTemplate.get_frameworks`` is replaced to simulate an empty catalog,
  a populated catalog, and a database error.

Not covered here: real authentication (``LOGIN_DISABLED`` bypasses
``@login_required`` except in guard-specific tests), any
database query, tenant scoping, and browser behaviour. Those remain for the
configured integration run owned by Codex.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask
from flask_login import LoginManager
from sqlalchemy.exc import OperationalError


# ---------------------------------------------------------------------------
# App fixture: real blueprints, no database, no application factory
# ---------------------------------------------------------------------------


def _bare_app(login_disabled: bool) -> Flask:
    from app.application_mgmt import application_mgmt
    from app.modules.ai_chat.routes import unified_ai_chat_bp

    flask_app = Flask(__name__)
    flask_app.config.update(
        TESTING=True,
        SECRET_KEY="availability-contract-tests",
        LOGIN_DISABLED=login_disabled,
    )
    login_manager = LoginManager()
    login_manager.init_app(flask_app)
    # No users exist in this bare app; the loader is required by Flask-Login
    # before it will evaluate an unauthenticated request.
    login_manager.user_loader(lambda _user_id: None)
    flask_app.register_blueprint(unified_ai_chat_bp)
    flask_app.register_blueprint(application_mgmt)
    return flask_app


@pytest.fixture(scope="module")
def bare_app():
    """Real blueprints on a bare Flask app. Auth bypassed via LOGIN_DISABLED."""
    return _bare_app(login_disabled=True)


@pytest.fixture
def client(bare_app):
    return bare_app.test_client()


@pytest.fixture
def llm_unconfigured(monkeypatch):
    """Boundary double: provider resolver raises, as it does with no keys."""
    from app.services.llm_service import LLMService

    def _raise(*_args, **_kwargs):
        raise ValueError("No LLM provider configured (test double)")

    monkeypatch.setattr(LLMService, "_get_configured_provider", staticmethod(_raise))


@pytest.fixture
def llm_configured_double(monkeypatch):
    """Boundary double: resolver reports a provider. No external call is made."""
    from app.services.llm_service import LLMService

    monkeypatch.setattr(
        LLMService,
        "_get_configured_provider",
        staticmethod(lambda *a, **k: ("double-provider", "double-model")),
    )


# ---------------------------------------------------------------------------
# /ai-chat/api/health/llm  (legacy_compat.llm_health)
# ---------------------------------------------------------------------------


def test_llm_health_returns_503_when_provider_unconfigured(client, llm_unconfigured):
    response = client.get("/ai-chat/api/health/llm")

    assert response.status_code == 503
    body = response.get_json()
    assert body["status"] == "unhealthy"
    assert body["error"] == "LLM provider not configured"
    assert "hint" in body
    # Every feature flag falls back to the resolver, so all must report False.
    assert set(body["features"]) == {"chat", "analysis", "import", "impact"}
    assert all(value is False for value in body["features"].values())


def test_llm_health_returns_200_when_resolver_reports_provider(
    client, llm_configured_double
):
    """Handler echoes the resolver result. Does NOT verify any real provider."""
    response = client.get("/ai-chat/api/health/llm")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "healthy"
    assert body["provider"] == "double-provider"
    assert body["model"] == "double-model"
    assert all(value is True for value in body["features"].values())


def test_llm_health_feature_override_does_not_change_llm_configured(
    bare_app, client, llm_unconfigured, monkeypatch
):
    """AI_<FEATURE>_ENABLED overrides per-feature flags but not the top-level
    health verdict, which is driven only by the provider resolver."""
    monkeypatch.setitem(bare_app.config, "AI_CHAT_ENABLED", True)

    response = client.get("/ai-chat/api/health/llm")

    assert response.status_code == 503
    body = response.get_json()
    assert body["features"]["chat"] is True
    assert body["features"]["analysis"] is False


def test_llm_health_requires_login_when_auth_enabled(llm_unconfigured):
    """With LOGIN_DISABLED off, the guard fires before the handler runs."""
    auth_app = _bare_app(login_disabled=False)

    response = auth_app.test_client().get("/ai-chat/api/health/llm")

    assert response.status_code == 401
    assert response.get_json() == {"error": "Unauthorized access"}


# ---------------------------------------------------------------------------
# /ai-chat/guide/history  (page_guide_routes._feature_guard + handler)
# ---------------------------------------------------------------------------


def _enable_page_guide(bare_app, monkeypatch):
    monkeypatch.setitem(bare_app.config, "AI_PAGE_GUIDE_ENABLED", True)


def test_page_guide_history_503_when_flag_off_even_if_llm_configured(
    bare_app, client, llm_configured_double, monkeypatch
):
    monkeypatch.delitem(bare_app.config, "AI_PAGE_GUIDE_ENABLED", raising=False)

    response = client.get(
        "/ai-chat/guide/history?page_key=dashboard.overview&scope_key=global"
    )

    assert response.status_code == 503
    assert response.get_json() == {
        "success": False,
        "error": "service_unavailable",
        "message": "The page guide is not enabled.",
    }


def test_page_guide_history_validates_request_when_enabled_without_llm(
    bare_app, client, llm_unconfigured, monkeypatch
):
    """Saved records require guide policy, not inference configuration.

    Missing context reaches real schema validation without querying any rows;
    the new policy/database suites cover successful scoped read and clear.
    """
    _enable_page_guide(bare_app, monkeypatch)

    response = client.get("/ai-chat/guide/history")

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert set(body["errors"]) == {"page_key", "scope_key"}


def test_page_guide_history_validation_visible_when_enabled_missing_fields(
    bare_app, client, llm_configured_double, monkeypatch
):
    _enable_page_guide(bare_app, monkeypatch)

    response = client.get("/ai-chat/guide/history")

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert set(body["errors"]) == {"page_key", "scope_key"}


def test_page_guide_history_validation_visible_when_enabled_unknown_page(
    bare_app, client, llm_configured_double, monkeypatch
):
    _enable_page_guide(bare_app, monkeypatch)

    response = client.get(
        "/ai-chat/guide/history?page_key=not.a.registered.page&scope_key=global"
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    # validation_error_response uses a different envelope from the schema path.
    assert body["error"]["code"] == "VALIDATION_ERROR"
    messages = [err["message"] for err in body["error"]["details"]]
    assert "Unsupported page guide context" in messages


def test_page_guide_history_200_when_enabled_with_service_double(
    bare_app, client, llm_configured_double, monkeypatch
):
    """Enabled + valid context reaches the service. ``PageGuideService`` and
    ``current_user`` are doubles: no rows are read and no user is logged in."""
    from app.modules.ai_chat.routes import page_guide_routes

    _enable_page_guide(bare_app, monkeypatch)

    calls = []
    real_service = page_guide_routes.PageGuideService

    class _PageGuideServiceDouble:
        # Keep the real enablement check so the guard is still exercised.
        is_enabled = staticmethod(real_service.is_enabled)

        def __init__(self, user_id):
            calls.append(("init", user_id))

        def get_history(self, page_key, scope_key):
            calls.append(("history", page_key, scope_key))
            return [{"role": "assistant", "content": "double-history"}]

    monkeypatch.setattr(page_guide_routes, "PageGuideService", _PageGuideServiceDouble)
    monkeypatch.setattr(page_guide_routes, "current_user", SimpleNamespace(id=4242))

    response = client.get(
        "/ai-chat/guide/history?page_key=dashboard.overview&scope_key=global"
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["page_key"] == "dashboard.overview"
    assert body["scope_key"] == "global"
    assert body["guide_mode"] == "specialized"
    assert body["messages"] == [{"role": "assistant", "content": "double-history"}]
    assert calls == [("init", 4242), ("history", "dashboard.overview", "global")]


# ---------------------------------------------------------------------------
# /dashboard/api/templates/frameworks  (template_api_routes.get_frameworks)
# ---------------------------------------------------------------------------


def _patch_frameworks(monkeypatch, impl):
    from app.models.element_templates import ElementTemplate

    monkeypatch.setattr(ElementTemplate, "get_frameworks", staticmethod(impl))


def test_frameworks_200_empty_array_when_no_active_templates(client, monkeypatch):
    _patch_frameworks(monkeypatch, lambda: [])

    response = client.get("/dashboard/api/templates/frameworks")

    assert response.status_code == 200
    assert response.get_json() == []


def test_frameworks_200_array_when_seeded_double(client, monkeypatch):
    _patch_frameworks(monkeypatch, lambda: ["COBIT", "ITIL", "PCF"])

    response = client.get("/dashboard/api/templates/frameworks")

    assert response.status_code == 200
    assert response.get_json() == ["COBIT", "ITIL", "PCF"]


def test_frameworks_database_error_is_not_masked_as_empty_collection(client, monkeypatch):
    """A backend failure must not look like a successful empty collection.

    The handler has no try/except. The ``application_mgmt`` blueprint's real
    ``DatabaseError`` errorhandler (app/application_mgmt/routes.py) catches it
    and returns JSON 500 for XHR requests."""

    def _boom():
        raise OperationalError("SELECT framework", {}, Exception("connection refused"))

    _patch_frameworks(monkeypatch, _boom)

    response = client.get(
        "/dashboard/api/templates/frameworks",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert response.status_code == 500
    body = response.get_json()
    assert body["success"] is False
    assert "frameworks" not in body
    assert body["error"] == "Database error occurred. Please try again."


def test_frameworks_requires_login_when_auth_enabled():
    auth_app = _bare_app(login_disabled=False)
    response = auth_app.test_client().get(
        "/dashboard/api/templates/frameworks",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert response.status_code == 401
