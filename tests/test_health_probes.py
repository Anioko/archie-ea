"""Contract tests for the live health probes.

The app has two live, unauthenticated health endpoints: the inline ``/health``
(``app/_bootstrap/routes.py``'s ``global_health_check``) and
``/health/db`` (``app/routes/health_routes.py``'s ``health.health_db``). Until
now neither had a test asserting its anonymous JSON contract; the closest
coverage read `/health` only as a side effect of unrelated checks (session-idle
behaviour, CSRF exemption) or a single ``checks.llm_providers`` field.

These three tests carry over the assertions the now-retired
``app/modules/monitoring`` health tests made that the live surface still
satisfies (see the bucket's disposition record): an anonymous JSON body with a
top-level status, a database check, and no redirect to login.
"""

from __future__ import annotations


def test_health_anonymous_json_contract(client):
    """GET /health: anonymous JSON with status/success and a database check."""
    resp = client.get("/health")

    assert resp.status_code in (200, 503)
    body = resp.get_json()
    assert body is not None
    assert body["status"] in ("healthy", "unhealthy")
    assert isinstance(body["success"], bool)
    assert "database" in body["checks"]
    assert "status" in body["checks"]["database"]

    if resp.status_code == 200:
        assert body["success"] is True
        assert body["status"] == "healthy"
    else:
        assert body["success"] is False
        assert body["status"] == "unhealthy"


def test_health_db_anonymous_json_contract(client):
    """GET /health/db: anonymous JSON with status/database, consistent with the code."""
    resp = client.get("/health/db")

    assert resp.status_code in (200, 503)
    body = resp.get_json()
    assert body is not None
    assert body["status"] in ("ok", "error")
    assert body["database"] in ("connected", "unreachable")

    if resp.status_code == 200:
        assert body["status"] == "ok"
        assert body["database"] == "connected"
    else:
        assert body["status"] == "error"
        assert body["database"] == "unreachable"


def test_health_does_not_redirect_anonymous_client(client):
    """GET /health never bounces an anonymous caller to a login page."""
    resp = client.get("/health")

    assert resp.status_code < 300 or resp.status_code >= 400
    assert "Location" not in resp.headers
