"""Test that the AI Data Architect persona works end-to-end.

Regression test for the P0 bug where sending a message with persona="data_architect"
returned HTTP 400 because the persona's default_domain ("data_architecture") was not
in the VALID_CHAT_DOMAINS schema list.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_user_id(db_session, make_org, client):
    """Create a user logged in to a test org."""
    from app.models.user import User

    org = make_org("data-arch-test")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"data-arch-{suffix}@example.com",
        first_name="Data",
        last_name="Architect",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="data_architect",
    )
    db_session.add(user)
    db_session.flush()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True

    # Clear cached user in g — see test_ai_chat_stream_errors.py for details
    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)
    return user.id


@pytest.fixture
def ai_enabled(monkeypatch):
    """Enable AI chat so routes execute."""
    from app.services.feature_flag_service import FeatureFlagService

    monkeypatch.setattr(
        FeatureFlagService, "is_ai_enabled", staticmethod(lambda *_a, **_k: True)
    )


def test_data_architect_persona_accepts_default_domain(
    client, logged_in_user_id, ai_enabled, monkeypatch
):
    """The data_architect persona has default_domain='data_architecture'.

    That domain must be in the VALID_CHAT_DOMAINS schema so messages with
    this persona do not return 400 Bad Request.
    """
    # Mock AgentRunner to avoid actual LLM calls
    class MockRunner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, *args, **kwargs):
            return {
                "response": "Data layer looks clean.",
                "actions_taken": [],
                "pending_approvals": [],
            }

    import app.modules.ai_chat.services.agent_runner as agent_runner_module

    monkeypatch.setattr(agent_runner_module, "AgentRunner", MockRunner)

    # Send a message as the data_architect persona (without specifying domain)
    # The persona's default_domain will be set by the UI/service
    response = client.post(
        "/ai-chat/message",
        json={
            "message": "Review my data layer for canonical entities and lineage gaps",
            "persona": "data_architect",
            "domain": "data_architecture",  # This should be a valid domain now
        },
    )

    # Must NOT be 400 Bad Request (which would indicate schema validation failure)
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. "
        f"Response: {response.get_json()}"
    )

    data = response.get_json()
    assert data.get("success") is True, (
        f"Response not successful. Data: {data}"
    )
    assert "Data layer" in data.get("response", ""), (
        f"No response text. Data: {data}"
    )


def test_data_architect_persona_default_domain_is_data_architecture(app):
    """Verify the data_architect persona has the correct default_domain."""
    from app.modules.ai_chat.services.multi_domain_chat_service import PERSONA_CONFIGS

    config = PERSONA_CONFIGS.get("data_architect")
    assert config is not None, "data_architect persona not found in PERSONA_CONFIGS"
    assert config.get("default_domain") == "data_architecture", (
        f"data_architect default_domain is {config.get('default_domain')}, "
        "expected 'data_architecture'"
    )


def test_data_architecture_is_valid_chat_domain(app):
    """Verify data_architecture is in the VALID_CHAT_DOMAINS schema."""
    from app.schemas.api_schemas import VALID_CHAT_DOMAINS

    assert "data_architecture" in VALID_CHAT_DOMAINS, (
        f"data_architecture not in VALID_CHAT_DOMAINS. Available: {VALID_CHAT_DOMAINS}"
    )
