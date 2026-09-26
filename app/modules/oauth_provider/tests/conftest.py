import itertools
import os
import uuid

import pytest

os.environ.setdefault("MCP_ENABLED", "true")
os.environ.setdefault("PUBLIC_BASE_URL", "https://mcp-test.example")

_unique_counter = itertools.count()


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}-{next(_unique_counter)}"


@pytest.fixture
def app():
    """A fresh app (and app context) per test.

    Function-scoped rather than session-scoped: Flask-SQLAlchemy's scoped
    session is keyed by app-context id, so sharing one app context across
    the whole test session meant one long-lived identity map — an object
    committed/deleted by one test could later show up detached or expired
    in a completely unrelated test. A fresh app per test sidesteps that
    entire class of ordering bugs at the cost of a slightly slower suite.
    """
    from app import create_app, db

    app = create_app("testing")
    app.config["MCP_ENABLED"] = True
    app.config["PUBLIC_BASE_URL"] = "https://mcp-test.example"
    app.config["SERVER_NAME"] = "mcp-test.example"
    # The registration rate limiter is a process-wide singleton keyed by
    # remote address; most tests hit /oauth/register from the same test
    # client "IP" many times. Disable it here and re-enable + reset it in
    # the one test that specifically exercises the 429 path.
    app.config["RATE_LIMITING_ENABLED"] = False

    # Test-only: keeping one app context open for the whole test (below)
    # means Flask's own RequestContext.push() reuses it for every test-client
    # call instead of pushing a fresh one (Flask only pushes a new app
    # context when none for this app is already active) — so flask.g, and
    # anything cached on it (Flask-Login's loaded user, g.oauth_token,
    # g.current_org_id), leaks from one request to the next *within a test*.
    # A real server never holds a context open across requests, so this
    # leakage is a test-harness artifact, not app behaviour — reset the
    # identity-relevant g keys before every request so each call resolves
    # current_user fresh, same as it would with one context per request.
    from flask import g

    def _reset_request_scoped_g():
        # Clear everything, not just the keys *we* know about: any library
        # (Flask-WTF's CSRF token cache included) that caches per-request
        # state on g would otherwise leak it across requests here too.
        g.__dict__.clear()

    app.before_request_funcs.setdefault(None, []).insert(0, _reset_request_scoped_g)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


@pytest.fixture
def db_session(app):
    from app import db

    yield db.session
    db.session.rollback()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def organization(db_session):
    from app.models.organization import Organization

    org = Organization(name="Test Org", slug=_unique("test-org-oauth"))
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def user(db_session, organization):
    from app.models.user import Role, User

    role = Role.query.filter_by(name="User").first()
    if role is None:
        role = Role(name="User", permissions=0x01, index="main", default=True)
        db_session.add(role)
        db_session.flush()

    u = User(
        first_name="Test",
        last_name="User",
        email=_unique("mcp-consent-test") + "@example.com",
        password="Password123!",
        confirmed=True,
        organization_id=organization.id,
        role_id=role.id,
    )
    db_session.add(u)
    db_session.commit()
    return u


def _csrf_token_from_page(html: bytes) -> str:
    import re

    match = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', html)
    return match.group(1).decode() if match else ""


@pytest.fixture
def logged_in_client(app, user):
    """A browser-session client, independent of the `client` fixture.

    Kept separate so a test can hold a logged-in session (for /oauth/authorize
    and consent) and a plain, cookie-less client (for /oauth/token, /oauth/revoke,
    and bearer-authenticated /mcp calls) at the same time without one leaking
    into the other's Set-Cookie / session state.
    """
    browser = app.test_client()
    login_page = browser.get("/account/login")
    csrf_token = _csrf_token_from_page(login_page.data)
    resp = browser.post("/account/login", data={
        "email": user.email, "password": "Password123!", "csrf_token": csrf_token,
    })
    assert resp.status_code in (200, 302), f"test login failed: {resp.status_code} {resp.data[:300]!r}"
    return browser


@pytest.fixture
def oauth_client(db_session):
    from app.modules.oauth_provider.models import OAuthClient

    return OAuthClient.register(
        client_name="Test Assistant",
        redirect_uris=["http://127.0.0.1:9999/callback"],
    )
