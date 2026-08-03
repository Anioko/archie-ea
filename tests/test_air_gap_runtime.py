"""Air-gap runtime behaviour: the app must work with outbound network denied.

The `air-gap` static gate proves no template *references* an external asset. It
cannot prove the application *behaves* when egress is blocked — a server-side
`requests.get` to an LLM provider, a font fetch during PDF rendering, or an SDK
phoning home at import time would all pass that gate and still hang a page behind
a corporate proxy.

This suite blocks every non-loopback TCP connection for the duration of a request
and then exercises the primary persona routes. Loopback stays open because
PostgreSQL and Redis are legitimately local; the boundary being enforced is
"leaves this host", which is exactly the boundary an enterprise network enforces.

A page that renders (or redirects) under those conditions is genuinely usable
offline. A page that raises `EgressBlocked` has a real outbound dependency, and the
assertion message names the address it tried to reach.
"""

from __future__ import annotations

import socket

import pytest

# Routes that make up the primary personas' day-to-day surface. A 500 on any of
# these is a broken product on an air-gapped network.
PERSONA_ROUTES = [
    "/dashboard/health",
    "/applications/",
    "/capability-map/",
    "/business-case/",
    "/value-streams/",
    "/organization/",
    "/business-model/",
    "/arb/reviews",
    "/strategic/impact-analysis",
]


class EgressBlocked(RuntimeError):
    """Raised when code under test attempts to reach a non-loopback address."""


def _is_loopback(address) -> bool:
    if not isinstance(address, tuple) or not address:
        return True  # unix sockets and the like are not egress
    host = address[0]
    return host in ("127.0.0.1", "::1", "localhost", "", None)


@pytest.fixture
def block_egress(monkeypatch):
    """Deny every non-loopback TCP connection, recording what was attempted.

    Patched at ``socket.socket.connect`` so it covers requests, urllib, httpx and
    any vendored SDK uniformly — anything short of a raw syscall.
    """
    attempts: list = []
    real_connect = socket.socket.connect

    def guarded_connect(self, address, *args, **kwargs):
        if _is_loopback(address):
            return real_connect(self, address, *args, **kwargs)
        attempts.append(address)
        raise EgressBlocked(f"outbound connection to {address!r} blocked")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    return attempts


# NB: the session-scoped `app` fixture from conftest.py is used deliberately.
# Defining a module-scoped one here shadowed it and broke conftest's session-scoped
# `_schema`, which depends on `app` — pytest refuses to hand a session-scoped
# fixture something with a narrower lifetime.


@pytest.fixture
def authed_client(app, db_session, make_org):
    """A logged-in client, so routes render rather than redirecting to login."""
    from app.models.user import User

    org = make_org("airgap")
    user = User(
        email=f"airgap-{org.slug}@example.com",
        first_name="Air",
        last_name="Gap",
        confirmed=True,
    )
    user.organization_id = org.id
    db_session.add(user)
    db_session.flush()

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True
    return client


def test_egress_guard_actually_blocks(block_egress):
    """The guard must work, or every other test here is vacuous."""
    with pytest.raises(EgressBlocked):
        socket.create_connection(("example.com", 80), timeout=5)
    assert block_egress, "the blocked attempt should have been recorded"


def test_loopback_still_permitted(block_egress):
    """Local services must remain reachable — this is air-gap, not no-network."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    try:
        client = socket.create_connection(server.getsockname(), timeout=5)
        client.close()
    finally:
        server.close()
    assert not block_egress, f"loopback was wrongly blocked: {block_egress}"


@pytest.mark.parametrize("route", PERSONA_ROUTES)
def test_persona_route_renders_without_egress(authed_client, block_egress, route):
    """Each primary route must not 500, and must not attempt to leave the host."""
    try:
        response = authed_client.get(route, follow_redirects=False)
    except EgressBlocked as exc:
        pytest.fail(
            f"{route} attempted an outbound connection while rendering: {exc}. "
            "It has a server-side external dependency and will hang or fail behind "
            "a corporate proxy."
        )

    assert response.status_code < 500, (
        f"{route} returned {response.status_code} with egress blocked. "
        f"Outbound attempts recorded: {block_egress or 'none'}"
    )
    assert not block_egress, (
        f"{route} rendered but attempted outbound connections to {block_egress}. "
        "Vendor the dependency or make the call optional."
    )
