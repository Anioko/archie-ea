"""Design-review wiring: AI endpoints that existed but had no UI caller.

Part 1 — the applications list page (app/templates/applications/list_simple.html)
gets an "AI Map" toolbar action that calls the existing
POST /applications/api/comprehensive-auto-map (preview) and
POST /applications/api/comprehensive-auto-map/accept endpoints
(app/modules/applications/routes/auto_mapping_routes.py), previously only ever
called from the import modal.

Part 2 — the ArchiMate dashboard (app/templates/archimate_crud/dashboard.html)
gets a "Generate with AI" action that calls the existing
POST /architecture/<layer>/<element_type>/ai-generate endpoint
(app/modules/architecture/routes/archimate_crud/routes.py), which previously
had no caller anywhere in the codebase.

Uses the shared fixtures in tests/conftest.py (db_session rolls back). Login
pattern and _clear_auth_caches copied from tests/test_bounded_ai_endpoints.py.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_org(db_session, make_org, client):
    """A confirmed user in a fresh org, logged into the test client."""
    from app.models.user import User

    org = make_org("ai-wiring")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"ai-wiring-{suffix}@example.com",
        first_name="AIWiring",
        last_name="Tester",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    db_session.add(user)
    db_session.flush()
    db_session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True

    _clear_auth_caches()
    return org


def _clear_auth_caches():
    """Anything that touches current_user on the shared app context re-caches
    an anonymous user in `g`; call this right before each test-client request."""
    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)


# --------------------------------------------------------------- Part 1: apps


def test_applications_list_has_ai_map_control(client, logged_in_org):
    _clear_auth_caches()
    response = client.get("/applications/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'data-testid="btn-ai-map"' in body
    assert 'data-testid="ai-map-modal"' in body


def test_comprehensive_auto_map_with_llm_mocked_returns_non_500(
    client, logged_in_org, monkeypatch
):
    import app.modules.ai_chat.services.llm_service_impl as llm_impl
    import app.services.ai_import_service as ai_import_service_module

    monkeypatch.setattr(llm_impl.LLMService, "is_available", staticmethod(lambda: True))
    monkeypatch.setattr(
        llm_impl.LLMService,
        "configuration_status",
        staticmethod(lambda: {"ready": True}),
    )

    class _FakeAIImportService:
        def bulk_ai_analyze(self, max_applications=50, confidence_threshold=0.7):
            return {
                "total_analyzed": 0,
                "capability_mappings_found": 0,
                "process_mappings_found": 0,
                "archimate_elements_generated": 0,
                "high_confidence_mappings": 0,
                "applications": [],
                "processing_stats": {"avg_processing_time_ms": 0, "ai_models_used": []},
                "vendor_stats": {},
            }

        def create_ai_mappings(self, **kwargs):
            return {
                "capability_mappings_created": 0,
                "process_mappings_created": 0,
                "archimate_elements_created": 0,
                "errors": [],
            }

    monkeypatch.setattr(
        ai_import_service_module,
        "get_ai_import_service",
        lambda: _FakeAIImportService(),
    )

    _clear_auth_caches()
    response = client.post(
        "/applications/api/comprehensive-auto-map",
        json={
            "max_applications": 5,
            "map_capabilities": True,
            "map_processes": True,
            "auto_create": False,
        },
    )
    assert response.status_code != 500
    data = response.get_json()
    assert data is not None
    assert data.get("success") is True


def test_accept_auto_map_results_with_empty_preview_returns_non_500(
    client, logged_in_org
):
    _clear_auth_caches()
    response = client.post(
        "/applications/api/comprehensive-auto-map/accept",
        json={"applications": [], "confidence_threshold": 0.7},
    )
    assert response.status_code != 500
    data = response.get_json()
    assert data is not None
    assert data.get("success") is True


# ------------------------------------------------------------ Part 2: archimate


def test_archimate_dashboard_has_ai_generate_control(client, logged_in_org):
    _clear_auth_caches()
    response = client.get("/architecture/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'data-testid="btn-ai-generate-element"' in body
    assert 'data-testid="ai-generate-modal"' in body


def test_ai_generate_endpoint_with_llm_mocked_returns_non_500(
    client, logged_in_org, monkeypatch
):
    import app.modules.architecture.routes.archimate_crud.routes as archimate_routes

    def fake_generate_element(self, layer, element_type, prompt, context=None):
        return {
            "success": True,
            "element": {
                "name": "Generated Driver",
                "description": "A generated description.",
                "attributes": {},
            },
            "raw_response": "{}",
        }

    monkeypatch.setattr(
        archimate_routes.AIGenerationService, "generate_element", fake_generate_element
    )

    _clear_auth_caches()
    response = client.post(
        "/architecture/motivation/Driver/ai-generate",
        json={"prompt": "Comply with the new data residency regulation", "context": {}},
    )
    assert response.status_code != 500
    data = response.get_json()
    assert data is not None
    assert data.get("success") is True
    assert data["data"]["element"]["name"] == "Generated Driver"


def test_ai_generate_endpoint_missing_prompt_is_a_400_not_500(client, logged_in_org):
    _clear_auth_caches()
    response = client.post(
        "/architecture/motivation/Driver/ai-generate",
        json={"prompt": "", "context": {}},
    )
    assert response.status_code == 400


# --------------------------------------------------------- Part 3: gap detection

# Part 3 — the rationalization dashboard
# (app/templates/applications/rationalization/dashboard.html, served by
# GET /applications/rationalization, unified_applications.rationalization_dashboard)
# gets an "AI Gap Analysis" panel that lazy-loads the four existing, previously
# uncalled GET endpoints on app/modules/ai_chat/routes/ai_gap_detection_routes.py
# (blueprint url_prefix="/api/ai-gap-detection"): /summary, /critical-gaps,
# /rationalization, /vendor-lifecycle.


def test_rationalization_dashboard_has_ai_gap_panel(client, logged_in_org):
    _clear_auth_caches()
    response = client.get("/applications/rationalization")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'data-testid="ai-gap-panel"' in body
    assert "/api/ai-gap-detection/summary" in body
    assert "/api/ai-gap-detection/critical-gaps" in body
    assert "/api/ai-gap-detection/rationalization" in body
    assert "/api/ai-gap-detection/vendor-lifecycle" in body
