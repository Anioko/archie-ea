"""``@cached`` must not serve one organisation's data to another.

Archie's tenancy is enforced by an ORM event (``do_orm_execute``) that adds
``organization_id = g.current_org_id`` to queries. Two organisations calling the
same function therefore get different rows — but ``cached`` built its key from
the function name and its arguments alone, so both calls hashed to the *same*
key.

For a cached view that takes no arguments the key is a constant. Three such
views exist on the capability surface a business architect works in:

    capability_map:hierarchy   — the whole capability tree, rendered
    capability_map:dashboard   — the capability map
    capability_map:acm_domains — the domain list

The first organisation to request one of them filled the cache with its own
rendered HTML, and for the next five minutes every other organisation was
served that page. Redis is present in the shipped compose file, so this was
live wherever the platform is deployed as documented; with no Redis the cache
degrades to a no-op, which is why it never showed up in local testing.

The fix scopes every key to ``g.current_org_id`` inside ``cached`` itself
rather than at each call site, so a future ``@cached`` cannot leak by omission.

The cache manager is replaced with an in-memory double below. That keeps the
test deterministic and independent of whether Redis happens to be running —
and the defect was never in Redis, it was in the key.
"""

from __future__ import annotations

import pytest

from app.extensions import cache as cache_mod


class _FakeCache:
    """Stands in for CacheManager: always caches, never expires."""

    def __init__(self):
        self.store = {}

    def get(self, key, default=None):
        return self.store.get(key, default)

    def set(self, key, value, ttl=None):
        self.store[key] = value
        return True

    def delete_pattern(self, pattern):
        prefix = pattern.rstrip("*")
        doomed = [k for k in self.store if k.startswith(prefix)]
        for k in doomed:
            del self.store[k]
        return len(doomed)


@pytest.fixture
def fake_cache(monkeypatch):
    fake = _FakeCache()
    monkeypatch.setattr(cache_mod, "cache_manager", fake)
    return fake


def test_tenant_key_follows_the_current_organisation(app, make_org, tenant_ctx):
    org_a = make_org("cache-key-a")
    org_b = make_org("cache-key-b")

    with tenant_ctx(org_a.id):
        key_a = cache_mod.current_tenant_key()
    with tenant_ctx(org_b.id):
        key_b = cache_mod.current_tenant_key()

    assert key_a != key_b
    assert str(org_a.id) in key_a


def test_tenant_key_outside_a_request_is_its_own_bucket(app):
    with app.app_context():
        assert cache_mod.current_tenant_key() == "org:none"


def test_a_zero_argument_cached_view_does_not_cross_tenants(
    app, fake_cache, make_org, tenant_ctx
):
    """The exact shape of the three capability_map views."""
    calls = []

    @cache_mod.cached(ttl=300, key_prefix="capability_map:hierarchy")
    def render_the_tree():
        # Stands in for the ORM read, which the tenant filter would scope.
        from flask import g

        calls.append(g.current_org_id)
        return f"<html>capabilities of org {g.current_org_id}</html>"

    org_a = make_org("cache-tenant-a")
    org_b = make_org("cache-tenant-b")

    with tenant_ctx(org_a.id):
        first = render_the_tree()
    with tenant_ctx(org_b.id):
        second = render_the_tree()

    assert first != second, (
        "org B was served org A's rendered capability tree from the cache — the "
        "key was a constant because the view takes no arguments"
    )
    assert second == f"<html>capabilities of org {org_b.id}</html>"
    assert calls == [org_a.id, org_b.id], "the second tenant never reached the query"
    assert len(fake_cache.store) == 2, "both tenants shared one cache entry"


def test_the_same_tenant_still_gets_a_cache_hit(app, fake_cache, make_org, tenant_ctx):
    """Scoping the key must not turn the cache off."""
    calls = []

    @cache_mod.cached(ttl=300, key_prefix="capability_map:hierarchy")
    def render_the_tree():
        calls.append(1)
        return "same-every-time"

    org = make_org("cache-same-tenant")
    with tenant_ctx(org.id):
        render_the_tree()
        render_the_tree()

    assert len(calls) == 1, "the second call should have been served from cache"


def test_invalidation_clears_only_the_calling_tenant(
    app, fake_cache, make_org, tenant_ctx
):
    @cache_mod.cached(ttl=300, key_prefix="capability_map:hierarchy")
    def render_the_tree():
        from flask import g

        return f"org {g.current_org_id}"

    org_a = make_org("cache-invalidate-a")
    org_b = make_org("cache-invalidate-b")

    with tenant_ctx(org_a.id):
        render_the_tree()
    with tenant_ctx(org_b.id):
        render_the_tree()
    assert len(fake_cache.store) == 2

    with tenant_ctx(org_a.id):
        cache_mod.invalidate_cache("capability_map:hierarchy*")

    remaining = list(fake_cache.store)
    assert len(remaining) == 1
    assert f"org:{org_b.id}" in remaining[0], (
        "invalidating one organisation's entries must not clear another's"
    )
