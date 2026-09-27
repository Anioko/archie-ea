"""The reproducible half of the adversarial sweep, so it stops being a one-off.

On 31 Aug 2026 an adversarial QA agent attacked this application for 46 minutes
and found, in one run, what 74 gates and 3,400 tests had not: a cross-tenant
counter leak, an ARB decision path with no state machine, a search endpoint that
500'd on every non-empty query, 55 endpoints that 500'd on `page=-1`, 78 routes
rendering a page for an entity that does not exist, and a live call to
api.github.com inside a logged-in request.

That run was a session, not a schedule. Nothing in this repository ran it, so
nothing would catch those defect classes coming back.

This file is the part of it a machine can repeat. The exploratory half — a model
forming hypotheses about what might break and chasing them — cannot be reduced
to assertions and is deliberately NOT claimed here; it stays a periodic,
human-triggered activity. What IS automatable is the regression: every class the
sweep found is now a probe that runs on a schedule.

Marked `adversarial` and executed in a separate CI step after ordinary smoke.
It walks the url_map repeatedly against the isolated test database. Identity-
changing routes require dedicated tests rather than ending a traversal's session.

    SMOKE_AI_PROTOCOL_STUB=1 pytest tests/smoke/test_adversarial_probes.py -m adversarial

The all-features traversal requires the explicit local protocol provider. This
does not qualify external inference: it makes enabled routes reachable without
relaxing the zero-5xx rule. Disabled/providerless contracts run separately.
"""

import json
import os
import re

import pytest

from .conftest import ARCHETYPES, PAGE_TIMEOUT, PASSWORD

pytestmark = [pytest.mark.smoke, pytest.mark.adversarial]

BASELINE_PATH = os.path.join(os.path.dirname(__file__), "adversarial_baseline.json")

# An id no seeded tenant can own. The sweep found 78 routes answering 200 for
# it, two of them synthesising a vendor object and one scoring a governance
# completeness report for a solution that does not exist.
ABSENT_ID = 999999999

# Values that reached PostgreSQL as a negative OFFSET, or ValueError'd out of
# int(), across 230 call sites.
HOSTILE_PARAMS = [
    {"page": "-1"}, {"page": "abc"}, {"page": ""},
    {"limit": "-1"}, {"limit": "abc"}, {"limit": "99999999999999999999"},
    {"per_page": "-1"},
]


def _diagnostic_text(value):
    """Short single-line detail; never dump request/session objects or bodies."""
    text = str(value)
    text = re.sub(r"(?i)([a-z][a-z0-9+.-]*://)[^\s/]*@", r"\1[redacted]@", text)
    text = re.sub(r"\?[^\s'\"<>)]*", "?[redacted]", text)
    # Header-like text can occur inside exception messages. Suppress the whole
    # value rather than trying to guess its cookie/authentication scheme.
    text = re.sub(r"(?im)\b(?:authorization|proxy-authorization|(?:set-)?cookie)\s*[:=][^\r\n]*",
                  "[redacted header]", text)
    text = re.sub(r"(?i)\b(?:password|passwd|token|api[_-]?key|secret)\s*[:=]\s*[^\s,;]+",
                  "[redacted credential]", text)
    text = " ".join(text.split())
    return text if len(text) <= 300 else text[:297] + "..."


def _exception_diagnostic(exc):
    return _diagnostic_text("%s: %s" % (type(exc).__name__, exc))


def _response_diagnostic(response):
    """Only explicit JSON error/message strings from this test-data probe."""
    try:
        payload = response.json()
    except ValueError:
        return ""
    if not isinstance(payload, dict):
        return ""
    detail = "; ".join("%s=%s" % (key, payload[key]) for key in ("error", "message")
                       if isinstance(payload.get(key), str) and payload[key].strip())
    return " (%s)" % _diagnostic_text(detail) if detail else ""


def _load_baseline():
    try:
        with open(BASELINE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _api_session(live_server, email):
    """A signed-in requests session, so probes are cheap (no browser)."""
    import re

    import requests

    session = requests.Session()
    session.verify = False
    page = session.get(live_server + "/account/login", timeout=30)
    payload = {"email": email, "password": PASSWORD}
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page.text or "")
    if match:
        payload["csrf_token"] = match.group(1)
    response = session.post(live_server + "/account/login", data=payload, timeout=30)
    assert "/account/login" not in response.url, "probe could not sign in as %s" % email
    return session


def _keeps_probe_identity(path):
    normalized = path.lower().replace("_", "-")
    return not any(token in normalized for token in (
        "logout", "log-out", "signout", "sign-out", "impersonat", "switch-org",
        "switch-tenant", "switch-user",
    ))


@pytest.fixture(scope='module', autouse=True)
def configured_feature_preflight(ai_protocol_stub, live_server, seeded):
    """Fail missing setup rather than counting disabled features as exercised."""
    assert ai_protocol_stub is not None, 'All-feature probes require SMOKE_AI_PROTOCOL_STUB=1'
    from .ai_protocol_stub import MODEL

    with _api_session(live_server, seeded['emails']['enterprise_architect']) as session:
        health = session.get(live_server + '/ai-chat/api/health/llm', timeout=30)
        assert health.status_code == 200, _response_diagnostic(health)
        assert health.json()['model'] == MODEL
        history = session.get(live_server + '/ai-chat/guide/history', params={
            'page_key': 'applications.detail', 'scope_key': 'applications.detail:32'}, timeout=30)
        assert history.status_code == 200, _response_diagnostic(history)


def _rules():
    """The url_map, built once. The smoke harness exposes a live server but
    no app object, and importing the factory here is cheaper than adding a
    fixture that every other smoke test would pay for."""
    from app import create_app

    application = create_app("testing")
    return [rule for rule in application.url_map.iter_rules()
            if _keeps_probe_identity(str(rule))]


def _int_arg_routes(rules):
    """Every GET rule taking a single integer path argument."""
    routes = []
    for rule in rules:
        if "GET" not in (rule.methods or set()):
            continue
        int_args = [a for a in rule.arguments
                    if "int:%s" % a in str(rule) or "<int:" in str(rule)]
        if len(rule.arguments) == 1 and int_args:
            routes.append(rule)
    return routes


def test_a_nonexistent_entity_is_never_rendered_as_a_real_one(live_server, seeded):
    """78 routes used to answer 200 for id 999999999.

    A 200 here is the fabrication rule at its worst: the user is shown a page
    for a record that does not exist, sometimes with a score computed over
    nothing, and cannot tell it apart from a real one.
    """
    session = _api_session(live_server, seeded["emails"]["platform_admin"])
    offenders = []
    for rule in _int_arg_routes(_rules()):
        arg = next(iter(rule.arguments))
        path = str(rule).replace("<int:%s>" % arg, str(ABSENT_ID))
        try:
            response = session.get(live_server + path, timeout=20,
                                   allow_redirects=False)
        except Exception as exc:
            offenders.append("%s -> request failed (%s)" % (path, _exception_diagnostic(exc)))
            continue
        if 200 <= response.status_code < 300:
            offenders.append("%s -> %d" % (path, response.status_code))

    allowed = _load_baseline().get("phantom_entities", 0)
    assert len(offenders) <= allowed, (
        "%d routes render a page for an entity that does not exist "
        "(baseline %d):\n  %s"
        % (len(offenders), allowed, "\n  ".join(sorted(offenders)[:25]))
    )


def test_hostile_pagination_never_reaches_a_500(live_server, seeded):
    """`?page=-1` used to arrive at PostgreSQL as a negative OFFSET."""
    session = _api_session(live_server, seeded["emails"]["platform_admin"])
    probes = [str(r) for r in _rules()
              if "GET" in (r.methods or set()) and not r.arguments
              and not str(r).startswith("/static")]

    offenders = []
    for path in probes:
        for params in HOSTILE_PARAMS:
            try:
                response = session.get(live_server + path, params=params,
                                       timeout=20, allow_redirects=False)
            except Exception as exc:
                offenders.append("%s %s -> request failed (%s)" % (path, params, _exception_diagnostic(exc)))
                continue
            # 501 excluded for the same reason as the persona probe: "Not
            # Implemented" is a deliberate statement that a feature does not
            # exist (the SAML callback is a documented stub), not a failure
            # under hostile input.
            if response.status_code >= 500 and response.status_code != 501:
                offenders.append("%s %s -> %d%s"
                                 % (path, params, response.status_code, _response_diagnostic(response)))
                break  # one report per route is enough to act on

    allowed = _load_baseline().get("hostile_pagination", 0)
    assert len(offenders) <= allowed, (
        "%d routes 500 on malformed pagination (baseline %d):\n  %s"
        % (len(offenders), allowed, "\n  ".join(sorted(offenders)[:25]))
    )


@pytest.mark.parametrize("archetype", ARCHETYPES)
def test_no_persona_can_reach_a_5xx_on_their_own_pages(archetype, live_server, seeded):
    """A plain GET, as the persona, must never be a server error.

    The sweep found exactly one 500 across 1,108 routes and two tenants, which
    is genuinely good — this exists so it stays that way.
    """
    session = _api_session(live_server, seeded["emails"][archetype])
    paths = [str(r) for r in _rules()
             if "GET" in (r.methods or set()) and not r.arguments
             and not str(r).startswith("/static")]

    offenders = []
    for path in paths:
        try:
            response = session.get(live_server + path, timeout=25,
                                   allow_redirects=False)
        except Exception as exc:
            offenders.append("%s -> request failed (%s)" % (path, _exception_diagnostic(exc)))
            continue
        # 501 is excluded deliberately, and only 501. "Not Implemented" is
        # never an accident -- it is a server stating that a feature does not
        # exist, which is the honest answer rather than a failure. The SAML
        # callback returns it because SSO is a documented stub. Counting an
        # honest 501 as a server error is how a gate earns a reputation for
        # crying wolf and stops being read.
        if response.status_code >= 500 and response.status_code != 501:
            offenders.append("%s -> %d%s" % (path, response.status_code, _response_diagnostic(response)))

    allowed = _load_baseline().get("persona_5xx", {}).get(archetype, 0)
    assert len(offenders) <= allowed, (
        "%s hits %d server errors on plain GETs (baseline %d):\n  %s"
        % (archetype, len(offenders), allowed, "\n  ".join(sorted(offenders)[:20]))
    )
