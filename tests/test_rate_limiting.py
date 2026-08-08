"""The rate limiter is brute-force protection, so it needs its own coverage.

`TestingConfig.RATE_LIMITING_ENABLED = False` switches app-level throttling off
for the suite — /account/login is capped at 10 POSTs per minute keyed on IP, and
every smoke test signs in from 127.0.0.1, so the suite was refusing its own
logins and failing 31 tests that had nothing to do with rate limiting.

Turning a security control off for the tests is only defensible if the control is
tested directly. That is what this file is. It exercises `RateLimiter` itself,
below the Flask config switch, so it holds regardless of that flag.
"""

import pytest

from app.services.rate_limiter import RateLimiter


@pytest.fixture
def limiter():
    return RateLimiter()


def test_requests_under_the_limit_are_allowed(limiter):
    for i in range(5):
        allowed, retry_after = limiter.check_rate_limit("k", limit=5, window_seconds=60)
        assert allowed is True, f"request {i + 1} of 5 was refused"
        assert retry_after is None


def test_the_request_over_the_limit_is_refused(limiter):
    for _ in range(5):
        limiter.check_rate_limit("k", limit=5, window_seconds=60)

    allowed, retry_after = limiter.check_rate_limit("k", limit=5, window_seconds=60)
    assert allowed is False, "the 6th request against a limit of 5 was allowed"
    assert isinstance(retry_after, (int, float)) and retry_after > 0, (
        "a refusal must say when to retry, or the caller can only spin"
    )


def test_keys_are_independent(limiter):
    """Two users, or two endpoints, must not consume each other's budget.

    The decorator keys on user-or-IP *plus* endpoint precisely so one throttled
    route cannot lock a user out of every other rate-limited route.
    """
    for _ in range(5):
        limiter.check_rate_limit("user:1:login", limit=5, window_seconds=60)

    allowed, _ = limiter.check_rate_limit("user:2:login", limit=5, window_seconds=60)
    assert allowed is True, "one key's exhaustion refused a different key"

    allowed, _ = limiter.check_rate_limit("user:1:search", limit=5, window_seconds=60)
    assert allowed is True, "exhausting one endpoint refused a different endpoint"


def test_the_budget_refills_as_the_window_passes(limiter):
    """A refusal must be temporary, or one burst locks a user out forever.

    It is a token bucket refilling on elapsed time, so the honest way to test
    this without sleeping is to rewind the bucket's own clock.
    """
    for _ in range(5):
        limiter.check_rate_limit("k", limit=5, window_seconds=60)
    allowed, _ = limiter.check_rate_limit("k", limit=5, window_seconds=60)
    assert allowed is False, "the limit did not apply within the window"

    # Age the bucket by a full window: the tokens should be back.
    limiter._buckets["k"]["last_update"] -= 60

    allowed, _ = limiter.check_rate_limit("k", limit=5, window_seconds=60)
    assert allowed is True, (
        "the budget did not refill after a full window — a single burst would "
        "lock the key out permanently"
    )


def test_the_login_route_is_still_decorated():
    """The config switch must not become an excuse to drop the decorator.

    Disabling throttling under test is a testing decision; the production route
    still has to carry the control.
    """
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "app/modules/account/routes/account_routes.py"
    text = src.read_text(encoding="utf-8")
    assert '@rate_limit(10, "1m"' in text, (
        "the login route lost its brute-force protection"
    )
    assert 'methods=("POST",)' in text, (
        "the login limit must scope to POST, or page loads consume the budget"
    )


def test_testing_config_disables_app_level_throttling():
    """Pin the switch, so re-enabling it re-breaks the suite visibly."""
    from config import TestingConfig

    assert TestingConfig.RATE_LIMITING_ENABLED is False
