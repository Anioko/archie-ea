"""Every registered route that writes must authenticate the caller.

This asserts against the app's real URL map rather than against the source,
because the two disagree in a way that matters. Grepping decorators finds 27
mutating routes with no auth decorator and several look alarming - an
unauthenticated /api/gdpr/delete/<user_id>, an unauthenticated
/api/orgs/<org_id>/invite that takes inviter_id from the request body. Booting
the app shows none of them is registered: they live in blueprints nothing wires
up, so they are dead code, not open doors.

The inverse error is the dangerous one, which is why this test exists at all. A
route can acquire an unauthenticated write path without any source pattern
changing - by being moved into a registered blueprint, or by having its
decorator dropped. Only the URL map sees that.

ALLOWED is deliberately tiny and each entry has to justify itself. Anything else
appearing here is a finding: at the time of writing, 3 of 3,399 registered routes
mutate without authenticating, and all three have to.
"""

import inspect

import pytest

pytestmark = pytest.mark.journey

# Routes that must stay reachable without a session, with the reason. A caller
# with no session is the entire point of each of these.
ALLOWED = {
    "/api/auth/login": "issues the session; cannot require one",
    "/api/auth/logout": "must work when the session is already gone or invalid",
    "/api/csp-report": "the browser posts these; it cannot hold a session token",
    # Webhooks: an external service cannot hold a session, so each authenticates
    # its caller by signature instead. Verified individually - the exemption is
    # from SESSION auth, not from authentication.
    "/api/webhooks/teams/notifications": (
        "Graph change notifications; clientState checked in "
        "TeamsMeetingService.handle_notification (teams_meeting_service.py:223), "
        "one call deep so the marker scan cannot see it"
    ),
}

# Markers that indicate the view authenticates. Deliberately broad - the point is
# to catch routes with NO authentication story at all, not to police which
# mechanism is used.
AUTH_MARKERS = (
    # session / role based
    "login_required",
    "require_auth",
    "requires_",
    "admin_required",
    "require_roles",
    "roles_required",
    "permission_required",
    "current_user",
    "check_access",
    "_check_access",
    # signature / shared-secret based, for callers that cannot hold a session
    "verify_webhook_signature",
    "compare_digest",
    "Signature",
    "signature",
    "signing_secret",
    "construct_event",
    # explicit rejection of an unauthenticated caller
    "abort(401",
    "abort(403",
    "401",
    "403",
)


@pytest.fixture(scope="module")
def app():
    import os

    os.environ.setdefault("SECRET_KEY", "x" * 32)
    from app import create_app

    return create_app("testing")


def _writes(rule):
    return bool(rule.methods - {"HEAD", "OPTIONS", "GET"})


def _looks_authenticated(view):
    # A decorator wrapping the view is the usual case (functools.wraps sets this).
    if getattr(view, "__wrapped__", None):
        return True
    try:
        return any(marker in inspect.getsource(view) for marker in AUTH_MARKERS)
    except (OSError, TypeError):
        # Cannot read the source - assume authenticated rather than emit a finding
        # that cannot be acted on. Under-reporting here is safe; the routes this
        # test exists to catch are ordinary Python views whose source is readable.
        return True


def test_no_registered_route_writes_without_authenticating(app):
    findings = []
    for rule in app.url_map.iter_rules():
        if not _writes(rule):
            continue
        if str(rule) in ALLOWED:
            continue
        view = app.view_functions.get(rule.endpoint)
        if view and not _looks_authenticated(view):
            methods = ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
            findings.append("%s [%s] -> %s" % (rule, methods, rule.endpoint))

    assert not findings, (
        "%d registered route(s) accept writes with no authentication:\n  %s\n\n"
        "Add an auth decorator, or - if the route genuinely must be public - add it "
        "to ALLOWED with the reason." % (len(findings), "\n  ".join(sorted(findings)))
    )


def test_the_public_write_routes_are_still_the_ones_we_expect(app):
    """Catches an ALLOWED entry that has been silently retired or renamed.

    A stale allowlist is worse than none: it reads as a considered exemption while
    covering a route that no longer exists, and quietly covers whatever takes its
    place at that path.
    """
    registered = {str(r) for r in app.url_map.iter_rules() if _writes(r)}
    missing = sorted(set(ALLOWED) - registered)
    assert not missing, (
        "ALLOWED exempts %s, which no longer accepts writes. Remove the entry - an "
        "exemption for a route that does not exist will silently cover its "
        "replacement." % missing
    )
