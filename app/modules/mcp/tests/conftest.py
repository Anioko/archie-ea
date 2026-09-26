import itertools
import os
import uuid
from urllib.parse import parse_qs, urlsplit

import pytest

os.environ.setdefault("MCP_ENABLED", "true")
os.environ.setdefault("PUBLIC_BASE_URL", "https://mcp-test.example")

_unique_counter = itertools.count()


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}-{next(_unique_counter)}"


def _csrf_token_from_page(html: bytes) -> str:
    import re

    match = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', html)
    return match.group(1).decode() if match else ""


REDIRECT_URI = "http://127.0.0.1:9999/callback"
RESOURCE = "https://mcp-test.example/mcp"


@pytest.fixture
def app():
    """A fresh app per test — see app/modules/oauth_provider/tests/conftest.py
    for why this is function-scoped rather than session-scoped."""
    from app import create_app, db

    app = create_app("testing")
    app.config["MCP_ENABLED"] = True
    app.config["PUBLIC_BASE_URL"] = "https://mcp-test.example"
    app.config["SERVER_NAME"] = "mcp-test.example"
    app.config["RATE_LIMITING_ENABLED"] = False

    # Test-only fix for a test-harness artifact — see the identical comment
    # in app/modules/oauth_provider/tests/conftest.py for why this is needed:
    # holding one app context open for the whole test means flask.g (and
    # Flask-Login's cached user) leaks between test-client requests within
    # the same test, which a real per-request context never would.
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

    org = Organization(name="Test Org", slug=_unique("test-org-mcp"))
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
        first_name="Test", last_name="User", email=_unique("mcp-tool-test") + "@example.com",
        password="Password123!", confirmed=True,
        organization_id=organization.id, role_id=role.id,
    )
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def logged_in_client(app, user):
    """An independent browser-session client — see the oauth_provider conftest
    for why this must not be the same object as the plain `client` fixture."""
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
        client_name="Test Assistant", redirect_uris=[REDIRECT_URI],
    )


@pytest.fixture
def access_token(logged_in_client, client, oauth_client):
    """A real access token, minted through the full authorize+token flow."""
    logged_in_client.get("/oauth/authorize", query_string={
        "response_type": "code", "client_id": oauth_client.client_id,
        "redirect_uri": REDIRECT_URI, "scope": "mcp:read", "state": "s", "resource": RESOURCE,
    })
    resp = logged_in_client.post("/oauth/authorize", data={"decision": "allow"})
    code = parse_qs(urlsplit(resp.headers["Location"]).query)["code"][0]
    tokens = client.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": REDIRECT_URI, "client_id": oauth_client.client_id,
        "resource": RESOURCE,
    }).get_json()
    return tokens["access_token"]


@pytest.fixture
def mcp_headers(access_token):
    return {"Authorization": f"Bearer {access_token}", "Mcp-Protocol-Version": "2025-06-18"}


@pytest.fixture
def element(db_session, organization):
    from app.models.archimate_core import ArchiMateElement

    el = ArchiMateElement(
        name="Test Component", type="ApplicationComponent", layer="application",
        description="A fixture element", organization_id=organization.id,
    )
    db_session.add(el)
    db_session.commit()
    return el
