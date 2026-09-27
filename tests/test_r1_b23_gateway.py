"""R1-B23: Model gateway and AI system register (PR 1).

Tests:
- Gateway records: organisation, provider, model version, prompt version,
  tokens, cost, latency and retention setting in every LLMInteraction.
- Provider register: ModelProvider.is_allowed_for_org resolution.
- Two-org isolation: organisation A's restriction does not affect B.
- Provider restriction enforcement in _call_llm.
- Bypass call sites are identified (no regression test — they are listed in the
  build report; the llm-boundary gate covers the deterministic emitter tree).
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from app import db
from app.models import LLMInteraction


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_providers(db_session):
    """Ensure a clean ModelProvider table before each test."""
    from app.models.model_provider import ModelProvider
    ModelProvider.query.delete()
    db_session.flush()


# ── Gateway recording ────────────────────────────────────────────────────────


class TestGatewayRecords:

    def test_interaction_created_with_gateway_fields(self, db_session, app, make_org):
        """A call through _call_llm records all gateway fields."""
        from app.modules.ai_chat.services.llm_service_impl import LLMService

        org = make_org()

        with app.app_context():
            # Mock the provider call to avoid real API calls
            with patch.object(LLMService, "_call_llm_with_failover") as mock:
                mock.return_value = (
                    "mock response",
                    LLMInteraction(
                        model_name="gpt-4o",
                        provider="openai",
                        prompt="test prompt",
                        response="mock response",
                        token_count_input=50,
                        token_count_output=100,
                        cost=0.002,
                        pipeline_stage_id=1,
                        organization_id=org.id,
                        prompt_version="v1.0",
                        retention_setting="30d",
                    ),
                )

                response, interaction = LLMService._call_llm(
                    prompt="test prompt",
                    model="gpt-4o",
                    provider="openai",
                    pipeline_stage_id=1,
                    prompt_version="v1.0",
                    retention_setting="30d",
                )

        assert interaction is not None
        assert interaction.organization_id == org.id
        assert interaction.model_name == "gpt-4o"
        assert interaction.provider == "openai"
        assert interaction.prompt_version == "v1.0"
        assert interaction.retention_setting == "30d"
        assert interaction.token_count_input == 50
        assert interaction.token_count_output == 100
        assert interaction.cost == 0.002
        assert interaction.latency_ms is not None and interaction.latency_ms >= 0

    def test_org_id_resolved_from_request_context(self, db_session, app, tenant_ctx, make_org):
        """The organisation ID is automatically resolved from g.current_org_id."""
        org = make_org()

        from app.modules.ai_chat.services.llm_service_impl import LLMService
        from flask import g

        with tenant_ctx(org.id):
            assert g.current_org_id == org.id
            resolved = LLMService._resolve_org_id()
            assert resolved == org.id

    def test_org_id_none_outside_request(self, db_session, app):
        """Outside a request context, _resolve_org_id returns None."""
        from app.modules.ai_chat.services.llm_service_impl import LLMService

        # No request context
        resolved = LLMService._resolve_org_id()
        assert resolved is None


# ── Provider register ────────────────────────────────────────────────────────


class TestProviderRegister:

    def test_platform_default_allowed(self, db_session):
        """A platform-default row allows a provider/model_version."""
        from app.models.model_provider import ModelProvider

        row = ModelProvider(
            provider="openai",
            model_version="gpt-4o",
            organization_id=None,
            is_platform_default=True,
            is_allowed=True,
        )
        db_session.add(row)
        db_session.flush()

        assert ModelProvider.is_allowed_for_org("openai", "gpt-4o", None) is True

    def test_platform_default_blocked(self, db_session):
        """A platform-default row can block a provider."""
        from app.models.model_provider import ModelProvider

        row = ModelProvider(
            provider="openai",
            model_version="gpt-4o-mini",
            organization_id=None,
            is_platform_default=True,
            is_allowed=False,
        )
        db_session.add(row)
        db_session.flush()

        assert ModelProvider.is_allowed_for_org("openai", "gpt-4o-mini", None) is False

    def test_org_override_allows_blocked_default(self, db_session, make_org):
        """An org row can explicitly allow what the platform default blocks."""
        from app.models.model_provider import ModelProvider

        org = make_org()

        # Platform blocks it
        db_session.add(ModelProvider(
            provider="openai",
            model_version="gpt-4o-mini",
            organization_id=None,
            is_platform_default=True,
            is_allowed=False,
        ))
        # Org allows it
        db_session.add(ModelProvider(
            provider="openai",
            model_version="gpt-4o-mini",
            organization_id=org.id,
            is_platform_default=False,
            is_allowed=True,
        ))
        db_session.flush()

        assert ModelProvider.is_allowed_for_org("openai", "gpt-4o-mini", org.id) is True

    def test_unknown_provider_allowed_by_default(self, db_session):
        """A provider with no row at all is permitted."""
        from app.models.model_provider import ModelProvider

        assert ModelProvider.is_allowed_for_org("unknown-provider", "v1", 1) is True

    def test_org_restriction_does_not_affect_other_org(self, db_session, make_org):
        """Two-org isolation: org B's block does not affect org A."""
        from app.models.model_provider import ModelProvider

        org_a = make_org("A")
        org_b = make_org("B")

        # Org B blocks openai/gpt-4o
        db_session.add(ModelProvider(
            provider="openai",
            model_version="gpt-4o",
            organization_id=org_b.id,
            is_platform_default=False,
            is_allowed=False,
        ))
        db_session.flush()

        # Org A should still be allowed (no override for A)
        assert ModelProvider.is_allowed_for_org("openai", "gpt-4o", org_a.id) is True
        # Org B should be blocked
        assert ModelProvider.is_allowed_for_org("openai", "gpt-4o", org_b.id) is False

    def test_platform_defaults_class_method(self, db_session, make_org):
        """platform_defaults() returns only platform rows."""
        from app.models.model_provider import ModelProvider

        org = make_org()

        db_session.add(ModelProvider(
            provider="openai", model_version="gpt-4o",
            organization_id=None, is_platform_default=True, is_allowed=True,
        ))
        db_session.add(ModelProvider(
            provider="openai", model_version="gpt-4o-mini",
            organization_id=None, is_platform_default=True, is_allowed=True,
        ))
        db_session.add(ModelProvider(
            provider="openai", model_version="gpt-4o",
            organization_id=org.id, is_platform_default=False, is_allowed=False,
        ))
        db_session.flush()

        defaults = ModelProvider.platform_defaults()
        assert len(defaults) == 2
        for d in defaults:
            assert d.organization_id is None
            assert d.is_platform_default is True

    def test_org_overrides_class_method(self, db_session, make_org):
        """org_overrides() returns only rows for that org."""
        from app.models.model_provider import ModelProvider

        org_a = make_org("A")
        org_b = make_org("B")

        db_session.add(ModelProvider(
            provider="openai", model_version="gpt-4o",
            organization_id=org_a.id, is_platform_default=False, is_allowed=False,
        ))
        db_session.add(ModelProvider(
            provider="anthropic", model_version="claude-opus-5",
            organization_id=org_b.id, is_platform_default=False, is_allowed=False,
        ))
        db_session.flush()

        assert len(ModelProvider.org_overrides(org_a.id)) == 1
        assert len(ModelProvider.org_overrides(org_b.id)) == 1
        assert len(ModelProvider.org_overrides(99999)) == 0


# ── Provider restriction enforcement ─────────────────────────────────────────


class TestProviderRestrictionEnforcement:

    def test_call_blocked_when_provider_not_allowed(self, db_session, app, make_org):
        """_call_llm raises ValueError when the org's provider register blocks it."""
        from app.models.model_provider import ModelProvider
        from app.modules.ai_chat.services.llm_service_impl import LLMService

        org = make_org()
        db_session.add(ModelProvider(
            provider="openai",
            model_version="gpt-4o",
            organization_id=org.id,
            is_platform_default=False,
            is_allowed=False,
        ))
        db_session.flush()

        with app.app_context(), pytest.raises(ValueError, match="not allowed"):
            # Patch resolve_org_id to return our org
            with patch.object(LLMService, "_resolve_org_id", return_value=org.id):
                LLMService._call_llm(
                    prompt="test",
                    model="gpt-4o",
                    provider="openai",
                )

    def test_call_allowed_when_provider_is_allowed(self, db_session, app, make_org):
        """_call_llm proceeds when the provider register allows it."""
        from app.models.model_provider import ModelProvider
        from app.modules.ai_chat.services.llm_service_impl import LLMService

        org = make_org()
        db_session.add(ModelProvider(
            provider="openai",
            model_version="gpt-4o",
            organization_id=org.id,
            is_platform_default=False,
            is_allowed=True,
        ))
        db_session.flush()

        with app.app_context():
            with patch.object(LLMService, "_resolve_org_id", return_value=org.id):
                with patch.object(LLMService, "_call_llm_with_failover") as mock:
                    mock.return_value = (
                        "ok",
                        LLMInteraction(
                            model_name="gpt-4o",
                            provider="openai",
                            prompt="test",
                            response="ok",
                            token_count_input=10,
                            token_count_output=10,
                            cost=0.001,
                            organization_id=org.id,
                        ),
                    )
                    response, interaction = LLMService._call_llm(
                        prompt="test",
                        model="gpt-4o",
                        provider="openai",
                        pipeline_stage_id=1,
                    )

        assert response == "ok"

    def test_interaction_persisted_in_database(self, db_session, app, make_org):
        """A successful call through the gateway persists the LLMInteraction."""
        from app.models.model_provider import ModelProvider
        from app.modules.ai_chat.services.llm_service_impl import LLMService

        org = make_org()
        # Ensure the provider is allowed
        db_session.add(ModelProvider(
            provider="openai",
            model_version="gpt-4o",
            organization_id=None,
            is_platform_default=True,
            is_allowed=True,
        ))
        db_session.flush()

        interaction_id = None
        with app.app_context():
            with patch.object(LLMService, "_resolve_org_id", return_value=org.id):
                with patch.object(LLMService, "_call_llm_with_failover") as mock:
                    mock.return_value = (
                        "persistence test",
                        LLMInteraction(
                            model_name="gpt-4o",
                            provider="openai",
                            prompt="persist me",
                            response="persistence test",
                            token_count_input=10,
                            token_count_output=10,
                            cost=0.001,
                            organization_id=org.id,
                            prompt_version="v1",
                            retention_setting="30d",
                        ),
                    )
                    response, interaction = LLMService._call_llm(
                        prompt="persist me",
                        model="gpt-4o",
                        provider="openai",
                        prompt_version="v1",
                        retention_setting="30d",
                    )

            interaction_id = interaction.id

        # Verify it's queryable from a fresh session
        assert interaction_id is not None
        fetched = db.session.get(LLMInteraction, interaction_id)
        assert fetched is not None
        assert fetched.organization_id == org.id
        assert fetched.model_name == "gpt-4o"
        assert fetched.provider == "openai"
        assert fetched.prompt_version == "v1"
        assert fetched.retention_setting == "30d"
        assert fetched.latency_ms is not None and fetched.latency_ms >= 0