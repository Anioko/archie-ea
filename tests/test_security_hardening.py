"""Regressions for security defects found in the production-readiness audit.

Each test pins a specific defect that was live in the tree. None of them needs a
database - they exercise pure functions and config classes - so they run in the
plain `pytest -q` job rather than only under the smoke harness.
"""

from __future__ import annotations

import hmac
import hashlib

import pytest


# --------------------------------------------------------------------------
# Open redirect on the post-login `next` parameter
# --------------------------------------------------------------------------

SAFE = ["/", "/dashboard", "/applications/42", "/a/b?c=d", "/x#frag"]

UNSAFE = [
    None,
    "",
    "   ",
    # The bypass that was live: both login views rejected "//" and "://" but not
    # a backslash, and browsers normalise "/\" to "//".
    "/\\evil.com",
    "\\/evil.com",
    "/\\\\evil.com",
    "//evil.com",
    "///evil.com",
    "https://evil.com",
    "http://evil.com",
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    # Not rooted - could be read relative to an unexpected base.
    "evil.com",
    "dashboard",
]


@pytest.mark.parametrize("value", SAFE)
def test_relative_paths_are_allowed(value):
    from app.utils.safe_redirect import is_safe_next_url, safe_next_url

    assert is_safe_next_url(value) is True, value
    assert safe_next_url(value, "/fallback") == value


@pytest.mark.parametrize("value", UNSAFE)
def test_off_site_and_malformed_targets_are_rejected(value):
    from app.utils.safe_redirect import is_safe_next_url, safe_next_url

    assert is_safe_next_url(value) is False, "%r must not be redirected to" % (value,)
    assert safe_next_url(value, "/fallback") == "/fallback"


def test_both_login_views_use_the_shared_validator():
    """Neither copy may reintroduce its own inline check."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for rel in (
        "app/modules/account/v2/routes/account_routes.py",
        "app/modules/account/routes/account_routes.py",
    ):
        text = (root / rel).read_text(encoding="utf-8")
        assert "safe_next_url" in text, "%s no longer uses the shared validator" % rel
        assert 'next_url.startswith("//")' not in text, (
            "%s reintroduced the inline check that "
            "/\\evil.com bypasses" % rel
        )


# --------------------------------------------------------------------------
# Jira webhook signature verification
# --------------------------------------------------------------------------

def test_jira_webhook_fails_closed_without_a_secret():
    """An unset secret must mean 'reject', never 'trust every caller'.

    POST /webhooks/jira is unauthenticated and csrf-exempt, and its handler
    writes KanbanCard rows outside a request-scoped tenant context, so this
    signature check is the only thing standing between the internet and every
    organisation's kanban board.
    """
    from app.modules.integrations.jira.jira_webhook_handler import _verify_signature

    body = b'{"issue": {"key": "ABC-1"}}'
    assert _verify_signature(body, "", "") is False
    assert _verify_signature(body, "deadbeef", "") is False
    assert _verify_signature(body, "deadbeef", None) is False


def test_jira_webhook_accepts_a_correct_signature_and_rejects_a_wrong_one():
    from app.modules.integrations.jira.jira_webhook_handler import _verify_signature

    body = b'{"issue": {"key": "ABC-1"}}'
    secret = "s3cret"
    good = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    # Flip the last character to something it definitely is not - appending a
    # fixed digit is a no-op whenever the digest already ends in that digit.
    wrong = good[:-1] + ("1" if good[-1] != "1" else "2")
    assert wrong != good

    assert _verify_signature(body, good, secret) is True
    assert _verify_signature(body, wrong, secret) is False
    assert _verify_signature(body, "", secret) is False
    assert _verify_signature(b"tampered", good, secret) is False


def test_jira_webhook_secret_is_declared_in_config():
    """The handler read this key before anything defined it, so it was always ''."""
    from config import Config

    assert hasattr(Config, "JIRA_WEBHOOK_SECRET")


# --------------------------------------------------------------------------
# Production cookie flags
# --------------------------------------------------------------------------

def test_production_cookies_are_secure_by_default(monkeypatch):
    """These derived from PREFERRED_URL_SCHEME, which ProductionConfig never set."""
    for var in (
        "SESSION_COOKIE_SECURE",
        "REMEMBER_COOKIE_SECURE",
        "PREFERRED_URL_SCHEME",
    ):
        monkeypatch.delenv(var, raising=False)

    import importlib

    import config as config_module

    importlib.reload(config_module)

    prod = config_module.ProductionConfig
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.REMEMBER_COOKIE_SECURE is True
    assert prod.SESSION_COOKIE_HTTPONLY is True
    assert prod.REMEMBER_COOKIE_HTTPONLY is True
    assert prod.SESSION_COOKIE_SAMESITE == "Lax"
    assert prod.REMEMBER_COOKIE_SAMESITE == "Lax"


# --------------------------------------------------------------------------
# Stored XSS in the traceability chain
# --------------------------------------------------------------------------

def test_traceability_chain_serialises_with_tojson_not_json_dumps():
    """json.dumps does not escape '<' or '/', so a solution named
    '</script><script>...' broke out of the surrounding <script> block."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    template = root / "app/templates/archimate/traceability_chain.html"
    text = template.read_text(encoding="utf-8")

    assert "element_solutions_json|safe" not in text
    assert "element_solutions_json | safe" not in text
    assert "(element_solutions_json or {}) | tojson" in text

    route = root / "app/modules/architecture/routes/archimate_routes.py"
    route_text = route.read_text(encoding="utf-8")
    assert "element_solutions_json = json.dumps({" not in route_text, (
        "the payload must reach the template as a dict so |tojson can escape it"
    )
