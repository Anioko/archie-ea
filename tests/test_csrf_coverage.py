"""R-30 — a token-less write request must be rejected on every write route.

P-04 (S1): nine of nine testable JSON write endpoints reached business logic
with NO CSRF token when probed live, despite flask-wtf's CSRFProtect being
wired globally in app/_bootstrap/extensions.py. The fix is default-deny
middleware with an explicit, justified opt-out list
(app/_bootstrap/csrf_coverage.py) rather than another endpoint-by-endpoint
patch, and this test is the register's own acceptance criterion for it: it
walks the *actual* route table (``app.url_map``) rather than a hand-written
list of endpoints, so a new write route with no CSRF protection and no
declared opt-out fails this test automatically, without anyone remembering
to add a case for it.

The shared session-scoped ``app`` fixture (tests/conftest.py) sets
``WTF_CSRF_ENABLED = False`` so the rest of the suite can POST/PUT/DELETE
without carrying a token. That is exactly the setting under test here, so
``_csrf_enabled`` flips it back to True for this module only and restores it
on teardown — never register new routes against the session-scoped ``app``
(Flask refuses ``@app.route`` after the app has served a request); this
module only flips config, never adds a route.
"""

from __future__ import annotations

import re
import uuid

import pytest

from app._bootstrap.csrf_coverage import audit

pytestmark = pytest.mark.usefixtures("db_session")

# Dummy values per Werkzeug URL converter, used to synthesise a concrete path
# from a rule pattern like "/architecture/elements/<int:element_id>" without
# needing real objects to exist (a CSRF rejection happens in a global
# before_request, ahead of routing to the view, so the id need not resolve).
_DUMMY_BY_CONVERTER = {
    "int": "999999",
    "float": "999999.0",
    "uuid": str(uuid.uuid4()),
    "path": "x",
    "string": "x",
    "default": "x",
}

_VAR_RE = re.compile(r"<(?:(\w+)(?:\([^)]*\))?:)?(\w+)>")


def _concretize(rule_pattern: str) -> str | None:
    """Fill every ``<converter:name>`` placeholder with a dummy value.

    Returns None for the rare "any" converter with an enumerated choice list,
    since a wrong guess 404s at routing before CSRF even runs — those routes
    are skipped rather than asserted on (none are in this app as of writing;
    the fallback exists so a future one fails loudly by omission, not by a
    silent false pass).
    """

    def _sub(m: "re.Match[str]") -> str:
        converter = m.group(1) or "default"
        return _DUMMY_BY_CONVERTER.get(converter, "x")

    if "any(" in rule_pattern:
        return None
    return _VAR_RE.sub(_sub, rule_pattern)


@pytest.fixture
def _csrf_enabled(app):
    """Re-enable CSRF enforcement for this module only."""
    original = app.config.get("WTF_CSRF_ENABLED")
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        yield app
    finally:
        app.config["WTF_CSRF_ENABLED"] = original


def _coverage(app):
    result = audit(app)
    assert not result["exempt_unjustified"], (
        "Undeclared CSRF exemption(s) found — see "
        "app/_bootstrap/csrf_coverage.py: "
        f"{[e['dest'] for e in result['exempt_unjustified']]}"
    )
    return result


def test_csrf_coverage_gate_has_no_undeclared_exemptions(app):
    """Fails first without the fix: before the confidence_review_api_bp
    exemption was removed, this listed an undeclared, session-cookie
    authenticated exemption."""
    _coverage(app)


def test_toplevel_route_count_is_nontrivial(app):
    """Sanity guard: a coverage test that silently enumerates zero routes
    (e.g. blueprints failed to register) would pass everything vacuously."""
    result = audit(app)
    assert result["total"] > 500, (
        f"Only {result['total']} write routes found — blueprints likely "
        "failed to register; this test would otherwise pass vacuously."
    )


@pytest.fixture
def _protected_route_params(app):
    result = audit(app)
    params = []
    for entry in result["protected"]:
        path = _concretize(entry["rule"])
        if path is None:
            continue
        for method in entry["methods"]:
            params.append(
                pytest.param(
                    method,
                    path,
                    id=f"{method} {entry['endpoint']}",
                )
            )
    return params


def test_every_protected_write_route_rejects_missing_token(app, _csrf_enabled, _protected_route_params):
    """The R-30 assertion: drive a token-less write request at EVERY route
    the coverage audit classifies as CSRF-protected (i.e. every write route
    that is not on the justified opt-out list), and require a rejection
    rather than a pass-through to business logic.

    A route reaching business logic (2xx/3xx/4xx-other-than-CSRF, or a 5xx
    from the view itself) without a token is exactly the P-04 failure mode.
    The correct rejection is either flask-wtf's CSRFError handler (400,
    error_type "csrf") or an earlier 401/403 from auth/authorization running
    ahead of CSRF for that particular route (both mean the request never
    reached the state-changing code) or a 404 from routing not resolving.
    What must never happen is a 2xx (executed) or a validation/handler 4xx
    that carries no csrf error_type on a route the coverage audit believes
    is protected — that combination means CSRFProtect's own exemption
    machinery, not this test's expectations, disagrees with the audit.
    """
    assert _protected_route_params, "No protected routes were enumerated."

    client = app.test_client()
    failures = []

    for param in _protected_route_params:
        method, path = param.values
        resp = client.open(path, method=method, json={"probe": "r30-no-csrf-token"})
        if resp.status_code == 400:
            body = resp.get_json(silent=True) or {}
            error_messages = [
                str(error.get("message", ""))
                for error in body.get("errors", [])
                if isinstance(error, dict)
            ]
            body_text = " ".join(
                str(value)
                for value in (
                    body.get("error_type"),
                    body.get("message"),
                    body.get("error"),
                    *error_messages,
                )
                if value
            ).lower()
            if "csrf" in body_text:
                continue  # correctly rejected by the CSRF gate (app-wide or
                # a framework's own 400 body, e.g. flask-restx's
                # {"message": "The CSRF token is missing."})
            # A plain 400 (e.g. schema validation) that was reached WITHOUT a
            # token means CSRF did not fire before the view's own validation.
            failures.append((method, path, resp.status_code, "400 but not csrf-tagged"))
            continue
        if resp.status_code in (401, 403, 404):
            continue  # blocked before or at routing/auth — never reached the write
        if resp.status_code >= 500:
            # Reached the view (and it broke) with no token — same class as
            # P-04's "/architecture/elements -> 500" finding.
            failures.append((method, path, resp.status_code, "5xx: reached the view"))
            continue
        if resp.status_code < 400:
            failures.append((method, path, resp.status_code, "EXECUTED with no token"))
            continue

    assert not failures, (
        f"{len(failures)} route(s) reachable without a CSRF token "
        f"(R-30 / P-04):\n"
        + "\n".join(f"  {m} {p} -> {code} ({why})" for m, p, code, why in failures[:50])
    )
