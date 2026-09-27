"""Provider register (ModelProvider) tests.

Tests:
- Platform-default rows are available to all organisations
- Organisation can restrict a provider without affecting another org
- ModelProvider CRUD operations
"""

from __future__ import annotations

import pytest


class TestModelProviderModel:
    """ModelProvider table stores platform defaults + per-org overrides."""

    def test_platform_default_no_org_id(self, db_session):
        """A platform-default row has organization_id=NULL."""
        from app.models.model_provider import ModelProvider

        mp = ModelProvider(
            provider="openai",
            model_version="gpt-4o",
            is_platform_default=True,
            organization_id=None,
        )
        db_session.add(mp)
        db_session.flush()

        saved = db_session.get(ModelProvider, mp.id)
        assert saved.organization_id is None
        assert saved.is_platform_default is True
        assert saved.is_allowed is True

    def test_per_org_restrict_row(self, db_session, make_org):
        """An organisation can set is_allowed=False to restrict a provider."""
        from app.models.model_provider import ModelProvider

        org = make_org("restrictor")
        mp = ModelProvider(
            provider="openai",
            model_version="gpt-4o",
            organization_id=org.id,
            is_platform_default=False,
            is_allowed=False,
        )
        db_session.add(mp)
        db_session.flush()

        saved = db_session.get(ModelProvider, mp.id)
        assert saved.organization_id == org.id
        assert saved.is_allowed is False
        assert saved.is_platform_default is False

    def test_per_org_allow_row(self, db_session, make_org):
        """An organisation can add a non-platform provider as allowed."""
        from app.models.model_provider import ModelProvider

        org = make_org("allower")
        mp = ModelProvider(
            provider="custom-llm",
            model_version="custom-model-v1",
            organization_id=org.id,
            is_platform_default=False,
            is_allowed=True,
        )
        db_session.add(mp)
        db_session.flush()

        saved = db_session.get(ModelProvider, mp.id)
        assert saved.organization_id == org.id
        assert saved.is_allowed is True

    def test_unique_constraint(self, db_session, make_org):
        """Same provider+model_version+org_id cannot be duplicated."""
        from app.models.model_provider import ModelProvider
        from sqlalchemy.exc import IntegrityError

        org = make_org("unique-test")
        mp1 = ModelProvider(
            provider="openai", model_version="gpt-4o",
            organization_id=org.id, is_platform_default=False,
        )
        db_session.add(mp1)
        db_session.flush()

        mp2 = ModelProvider(
            provider="openai", model_version="gpt-4o",
            organization_id=org.id, is_platform_default=False,
        )
        db_session.add(mp2)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_same_provider_different_orgs_no_conflict(self, db_session, make_org):
        """Two orgs can each have their own row for the same provider."""
        from app.models.model_provider import ModelProvider

        org_a = make_org("mp-a")
        org_b = make_org("mp-b")

        for org in (org_a, org_b):
            mp = ModelProvider(
                provider="openai", model_version="gpt-4o",
                organization_id=org.id, is_platform_default=False,
            )
            db_session.add(mp)
        db_session.flush()

        count = db_session.query(ModelProvider).filter(
            ModelProvider.provider == "openai",
            ModelProvider.model_version == "gpt-4o",
        ).count()
        assert count == 2


class TestTwoOrgProviderRegister:
    """Provider register isolation between organisations."""

    def test_platform_provider_visible_across_orgs(self, db_session, make_org):
        """Platform-default rows (org=NULL) are visible to all organisations."""
        from app.models.model_provider import ModelProvider

        # Platform row
        db_session.add(ModelProvider(
            provider="openai", model_version="gpt-4o",
            is_platform_default=True, organization_id=None,
        ))
        db_session.flush()

        # Both orgs see the platform row
        platform_rows = (
            db_session.query(ModelProvider)
            .filter(ModelProvider.organization_id.is_(None))
            .count()
        )
        assert platform_rows >= 1

    def test_org_a_restriction_does_not_block_org_b(self, db_session, make_org):
        """Org A restricting a provider does not affect Org B."""
        from app.models.model_provider import ModelProvider

        platform = make_org("platform-holder")
        org_a = make_org("restrict-a")
        org_b = make_org("restrict-b")

        # Platform allows openai/gpt-4o
        db_session.add(ModelProvider(
            provider="openai", model_version="gpt-4o",
            is_platform_default=True, organization_id=None,
        ))

        # Org A restricts it
        db_session.add(ModelProvider(
            provider="openai", model_version="gpt-4o",
            organization_id=org_a.id,
            is_platform_default=False, is_allowed=False,
        ))
        db_session.flush()

        # Org A should see the restriction
        a_restrictions = (
            db_session.query(ModelProvider)
            .filter(
                ModelProvider.organization_id == org_a.id,
                ModelProvider.is_allowed == False,
            )
            .count()
        )
        assert a_restrictions >= 1

        # Org B should NOT have the restriction
        b_restrictions = (
            db_session.query(ModelProvider)
            .filter(
                ModelProvider.organization_id == org_b.id,
                ModelProvider.is_allowed == False,
            )
            .count()
        )
        assert b_restrictions == 0

        # Org B still sees platform defaults
        b_platform = (
            db_session.query(ModelProvider)
            .filter(
                ModelProvider.organization_id.is_(None),
                ModelProvider.is_platform_default == True,
                ModelProvider.is_allowed == True,
            )
            .count()
        )
        # Zero because no org B row exists, but the platform row is there
        # Note: platform rows have no org so they're visible to everyone
        assert b_platform >= 1

    def test_query_visible_providers_for_org(self, db_session, make_org):
        """Query that returns all allowed providers for an org, including platform defaults."""
        from app.models.model_provider import ModelProvider

        org = make_org("query-test")

        # Platform rows
        db_session.add(ModelProvider(
            provider="openai", model_version="gpt-4o",
            is_platform_default=True, organization_id=None,
        ))
        db_session.add(ModelProvider(
            provider="anthropic", model_version="claude-opus-5",
            is_platform_default=True, organization_id=None,
        ))

        # Org-specific allow for a non-platform provider
        db_session.add(ModelProvider(
            provider="custom-llm", model_version="v1",
            organization_id=org.id,
            is_platform_default=False, is_allowed=True,
        ))
        db_session.flush()

        # Visible to org: platform defaults (org=NULL, is_allowed=True) + org-specific allowed rows
        visible = (
            db_session.query(ModelProvider)
            .filter(
                ModelProvider.is_allowed == True,
                (
                    (ModelProvider.organization_id.is_(None)) |
                    (ModelProvider.organization_id == org.id)
                ),
            )
            .all()
        )
        provider_models = {(p.provider, p.model_version) for p in visible}
        assert ("openai", "gpt-4o") in provider_models
        assert ("anthropic", "claude-opus-5") in provider_models
        assert ("custom-llm", "v1") in provider_models