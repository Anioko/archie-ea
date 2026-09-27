"""Hotfix regression: @cached() must not serve one org's response to another.

Standalone (no Wave-2 deps) so it applies on the production lineage. Exercises
the decorator's key derivation and the fail-closed bypass directly against a
dict-backed fake cache, driving g.current_org_id the way a request would.
"""
from types import SimpleNamespace

import pytest
from flask import Flask, g

from app.extensions.cache import cached


class _FakeCache:
    """Mimics CacheManager's get(key, default)/set(key, value, ttl) surface."""

    def __init__(self):
        self.store = {}

    def get(self, key, default=None):
        return self.store.get(key, default)

    def set(self, key, value, ttl=None):
        self.store[key] = value


@pytest.fixture
def app_and_cache(monkeypatch):
    app = Flask(__name__)
    fake = _FakeCache()
    import app.extensions.cache as cache_mod

    # The decorator reads the module-level `cache_manager` singleton.
    monkeypatch.setattr(cache_mod, "cache_manager", fake)
    return app, fake


def test_two_orgs_do_not_share_a_cached_response(app_and_cache):
    app, fake = app_and_cache
    calls = []

    @cached(ttl=300, key_prefix="t:hier", key_func=lambda: getattr(g, "current_org_id", None))
    def view():
        calls.append(g.current_org_id)
        return f"payload-for-org-{g.current_org_id}"

    with app.test_request_context():
        g.current_org_id = 1
        assert view() == "payload-for-org-1"
    with app.test_request_context():
        g.current_org_id = 2
        assert view() == "payload-for-org-2"  # must NOT be org 1's cached payload
    with app.test_request_context():
        g.current_org_id = 1
        assert view() == "payload-for-org-1"  # org 1 served from its own key

    assert calls == [1, 2]  # org 1's second call was a cache hit, not a recompute


def test_missing_org_context_bypasses_cache_fail_closed(app_and_cache):
    app, fake = app_and_cache
    calls = []

    @cached(ttl=300, key_prefix="t:hier", key_func=lambda: getattr(g, "current_org_id", None))
    def view():
        calls.append(1)
        return "unscoped"

    with app.test_request_context():
        g.current_org_id = None
        view()
        view()

    # No key_func value -> no caching -> function runs every time, nothing stored.
    assert len(calls) == 2
    assert fake.store == {}
