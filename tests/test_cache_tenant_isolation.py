"""A cache in front of a tenant-scoped query must be keyed by the tenant.

Two module-level caches were found unkeyed on 30 Aug 2026. Both sat in front of
queries that were correctly tenant-scoped, and both threw that scoping away:

* ``capability_health_service._health_metrics_cache`` was a single tuple shared
  by the whole process. Its value carries ``health_by_capability`` -- every
  capability's name, id, domain and score -- so for 60 seconds after any tenant
  loaded /strategic/capability-health, every other tenant was served that
  tenant's capability names and scores.

* ``multi_domain_chat_service._RAG_CONTEXT_CACHE`` was keyed by business domain
  alone. Its value carries architecture principles, PRIOR ARB DECISION TITLES
  and reference architectures, and it is injected into the AI system prompt --
  so one tenant's governance history reached another tenant's assistant, to
  answer from and cite.

Neither required any action by the receiving user: the data simply appeared.
That is why these are regression tests rather than a note. The first was found
by a test written for something else that could not get a clean result between
two organisations; without a test, nothing would have noticed either.
"""

import uuid

import pytest


def _make_org(db, label):
    from app.models.organization import Organization

    suffix = uuid.uuid4().hex[:8]
    org = Organization(name="%s %s" % (label, suffix),
                       slug="%s-%s" % (label.lower(), suffix))
    db.session.add(org)
    db.session.flush()
    return org


def test_capability_health_is_not_served_across_tenants(app):
    """Org B must never be handed org A's capabilities by the cache."""
    from flask import g

    from app import db
    from app.models.business_capabilities import BusinessCapability
    from app.modules.capabilities.services.capability_health_service import (
        CapabilityHealthService,
    )

    with app.app_context():
        org_a = _make_org(db, "LeakA")
        org_b = _make_org(db, "LeakB")
        private_to_a = "Private to A %s" % uuid.uuid4().hex[:8]
        db.session.add(BusinessCapability(
            name=private_to_a, organization_id=org_a.id,
            current_maturity_level=1, target_maturity_level=5,
        ))
        db.session.add(BusinessCapability(
            name="Owned by B %s" % uuid.uuid4().hex[:8], organization_id=org_b.id,
        ))
        db.session.commit()

        # A reads first, populating the cache.
        g.current_org_id = org_a.id
        seen_by_a = [
            h["name"] for h in
            CapabilityHealthService().get_capability_health_metrics()["health_by_capability"]
        ]
        assert private_to_a in seen_by_a

        # B reads within the 60s TTL.
        g.current_org_id = org_b.id
        seen_by_b = [
            h["name"] for h in
            CapabilityHealthService().get_capability_health_metrics()["health_by_capability"]
        ]

        assert private_to_a not in seen_by_b, (
            "org B was served org A's capability %r from the shared cache"
            % private_to_a
        )

        db.session.rollback()


def test_the_rag_context_cache_is_keyed_by_tenant(app):
    """Its value reaches the AI system prompt, so a shared key is a shared prompt."""
    from flask import g

    from app.modules.ai_chat.services import multi_domain_chat_service as mdcs

    mdcs._RAG_CONTEXT_CACHE.clear()

    with app.test_request_context("/"):
        g.current_org_id = 424242
        service = mdcs.MultiDomainChatService.__new__(mdcs.MultiDomainChatService)
        mdcs.MultiDomainChatService._get_rag_context(service, "finance")

        assert mdcs._RAG_CONTEXT_CACHE, "nothing was cached; the test proves nothing"
        for key in mdcs._RAG_CONTEXT_CACHE:
            assert isinstance(key, tuple) and key[0] == 424242, (
                "RAG context cached under %r -- a key without the organisation is "
                "shared with every other tenant" % (key,)
            )

    mdcs._RAG_CONTEXT_CACHE.clear()


def test_neither_cache_stores_anything_without_a_tenant(app):
    """Outside a request there is no owner, and an unowned entry is the bug."""
    from app.modules.ai_chat.services import multi_domain_chat_service as mdcs

    mdcs._RAG_CONTEXT_CACHE.clear()
    with app.app_context():
        service = mdcs.MultiDomainChatService.__new__(mdcs.MultiDomainChatService)
        mdcs.MultiDomainChatService._get_rag_context(service, "finance")

    assert not mdcs._RAG_CONTEXT_CACHE, (
        "an entry was cached with no tenant context; it would be served to the "
        "next tenant that asks"
    )
