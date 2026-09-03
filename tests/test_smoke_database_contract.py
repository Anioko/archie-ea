"""Release browser tests must never silently target a fallback database."""

import pytest

from tests.smoke.conftest import _require_explicit_test_database, _select_browser_engine


def test_smoke_database_contract_rejects_missing_explicit_url():
    with pytest.raises(pytest.UsageError, match="TEST_DATABASE_URL"):
        _require_explicit_test_database({})


def test_smoke_database_contract_mirrors_explicit_test_url_to_server():
    env = {"TEST_DATABASE_URL": "postgresql://qa@example/archie_candidate"}

    _require_explicit_test_database(env)

    assert env["DATABASE_URL"] == env["TEST_DATABASE_URL"]


def test_smoke_database_contract_rejects_conflicting_database_urls():
    env = {
        "TEST_DATABASE_URL": "postgresql://qa@example/archie_candidate",
        "DATABASE_URL": "postgresql://qa@example/archie_stale",
    }

    with pytest.raises(pytest.UsageError, match="same database"):
        _require_explicit_test_database(env)


class _PlaywrightEngines:
    chromium = object()
    firefox = object()
    webkit = object()


def test_smoke_browser_contract_selects_requested_engine():
    engines = _PlaywrightEngines()

    selected, name = _select_browser_engine(engines, {"SMOKE_BROWSER": "firefox"})

    assert selected is engines.firefox
    assert name == "firefox"


def test_smoke_browser_contract_rejects_unknown_engine():
    with pytest.raises(pytest.UsageError, match="SMOKE_BROWSER"):
        _select_browser_engine(_PlaywrightEngines(), {"SMOKE_BROWSER": "edge-ish"})
