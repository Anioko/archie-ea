"""Provider restriction enforcement in the gateway.

Tests:
- ModelProvider.is_allowed_for_org resolution (platform default, org override)
- Provider restriction enforced in _call_llm raises ValueError
- Allowed provider proceeds through the gateway
- Interaction persisted with latency
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app import db
from app.models import LLMInteraction


class TestIsAllowedForOrg:
    """ModelProvider.is_allowed_for_org resolution logic."""

    def test_platform_default_allowed(self, db_session):
        """Platform-default allowed row permits the provider."""
        from app.models.model_provider import ModelProvider

        db_session.add(ModelProvider(
            provider="anthropic", model_version="claude-opus-5",
            organization_id=None, is_platform_default=True, is_allowed=True,
        ))
        db_session.flush()

        assert ModelProvider.is_allowed_for_org("anthropic", "claude-opus-5", None) is True

    def test_platform_default_blocked(self, db_session):
        """Platform-default blocked row denies the provider organisation-wide."""
        from app.models.model_provider import ModelProvider

        db_session.add(ModelProvider(
            provider="deepseek", model_version="deepseek-chat",
            organization_id=None, is_platform_default=True, is_allowed=False,
        ))
        db_session.flush()

        assert ModelProvider.is_allowed_for_org("deepseek", "deepseek-chat", None) is False

    def test_org_override_allows_blocked_platform(self, db_session, make_org):
        """Org override can re-allow what platform default blocks."""
        from app.models.model_provider import ModelProvider

        org = make_org("override")
        db_session.add(ModelProvider(
            provider="deepseek", model_version="deepseek-chat",
            organization_id=None, is_platform_default=True, is_allowed=False,
        ))
        db_session.add(ModelProvider(
            provider="deepseek", model_version="deepseek-chat",
            organization_id=org.id, is_platform_default=False, is_allowed=True,
        ))
        db_session.flush()

        assert ModelProvider.is_allowed_for_org("deepseek", "deepseek-chat", org.id) is True

    def test_org_override_blocks_allowed_platform(self, db_session, make_org):
        """Org override can block what platform default allows."""
        from app.models.model_provider import ModelProvider

        org = make_org("blocker")
        db_session.add(ModelProvider(
            provider="openai", model_version="gpt-4o",
            organization_id=None, is_platform_default=True, is_allowed=True,
        ))
        db_session.add(ModelProvider(
            provider="openai", model_version="gpt-4o",
            organization_id=org.id, is_platform_default=False, is_allowed=False,
        ))
        db_session.flush()

        assert ModelProvider.is_allowed_for_org("openai", "gpt-4o", org.id) is False
        assert ModelProvider.is_allowed_for_org("openai", "gpt-4o", None) is True

    def test_unknown_provider_allowed_by_default(self, db_session):
        """A provider with no register entry is permitted."""
        from app.models.model_provider import ModelProvider

        assert ModelProvider.is_allowed_for_org("nonexistent-provider", "v1", 1) is True

    def test_org_b_not_affected_by_org_a_block(self, db_session, make_org):
        """Org A's restriction does not affect org B's resolution."""
        from app.models.model_provider import ModelProvider

        org_a = make_org("a")
        org_b = make_org("b")

        db_session.add(ModelProvider(
            provider="openai", model_version="gpt-4o",
            organization_id=org_a.id, is_platform_default=False, is_allowed=False,
        ))
        db_session.flush()

        assert ModelProvider.is_allowed_for_org("openai", "gpt-4o", org_a.id) is False
        assert ModelProvider.is_allowed_for_org("openai", "gpt-4o", org_b.id) is True
        assert ModelProvider.is_allowed_for_org("openai", "gpt-4o", None) is True


class TestProviderRestrictionEnforcement:
    """Gateway enforces the provider register in _call_llm."""

    def test_call_blocked_when_provider_not_allowed(self, db_session, app, make_org):
        """_call_llm raises ValueError when the org restricts the provider."""
        from app.models.model_provider import ModelProvider
        from app.modules.ai_chat.services.llm_service_impl import LLMService

        org = make_org("restricted")
        db_session.add(ModelProvider(
            provider="openai", model_version="gpt-4o",
            organization_id=org.id, is_platform_default=False, is_allowed=False,
        ))
        db_session.flush()

        with app.app_context(), pytest.raises(ValueError, match="not allowed"):
            with patch.object(LLMService, "_resolve_org_id", return_value=org.id):
                LLMService._call_llm(prompt="test", model="gpt-4o", provider="openai")

    def test_call_allowed_when_no_register_entry(self, db_session, app, make_org):
        """_call_llm proceeds when there is no register entry (default allowed)."""
        from app.modules.ai_chat.services.llm_service_impl import LLMService

        org = make_org("unrestricted")
        with app.app_context():
            with patch.object(LLMService, "_resolve_org_id", return_value=org.id):
                with patch.object(LLMService, "_call_llm_with_failover") as mock:
                    mock.return_value = (
                        "ok",
                        LLMInteraction(
                            model_name="gpt-4o", provider="openai",
                            prompt="test", response="ok",
                            token_count_input=5, token_count_output=5, cost=0.001,
                            organization_id=org.id,
                        ),
                    )
                    response, interaction = LLMService._call_llm(
                        prompt="test", model="gpt-4o", provider="openai",
                    )

        assert response == "ok"

    def test_interaction_persisted_with_latency(self, db_session, app, make_org):
        """A successful call through the gateway persists the LLMInteraction with latency."""
        from app.models.model_provider import ModelProvider
        from app.modules.ai_chat.services.llm_service_impl import LLMService

        org = make_org("latency-test")
        db_session.add(ModelProvider(
            provider="openai", model_version="gpt-4o",
            organization_id=None, is_platform_default=True, is_allowed=True,
        ))
        db_session.flush()

        interaction_id = None
        with app.app_context():
            with patch.object(LLMService, "_resolve_org_id", return_value=org.id):
                with patch.object(LLMService, "_call_llm_with_failover") as mock:
                    mock.return_value = (
                        "latency test",
                        LLMInteraction(
                            model_name="gpt-4o", provider="openai",
                            prompt="latency", response="latency test",
                            token_count_input=10, token_count_output=10, cost=0.001,
                            organization_id=org.id,
                            prompt_version="v1", retention_setting="30d",
                        ),
                    )
                    response, interaction = LLMService._call_llm(
                        prompt="latency", model="gpt-4o", provider="openai",
                        prompt_version="v1", retention_setting="30d",
                    )
            interaction_id = interaction.id

        assert interaction_id is not None
        fetched = db.session.get(LLMInteraction, interaction_id)
        assert fetched is not None
        assert fetched.organization_id == org.id
        assert fetched.model_name == "gpt-4o"
        assert fetched.provider == "openai"
        assert fetched.prompt_version == "v1"
        assert fetched.retention_setting == "30d"
        assert fetched.latency_ms is not None and fetched.latency_ms >= 0