"""ARCH-002: a 503 must preserve the requested path instead of dropping the
user at "/". Covers the Flask-level errors/503.html handler in
app/main/errors.py — the Caddy-level branded page in deploy/Caddyfile.proxy
handles the case where the whole process is down and cannot serve this at
all, and is not exercisable from a Flask test client.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def client(app):
    app.testing = True
    return app.test_client()


def test_503_preserves_requested_path(app, client):
    """A route that raises HTTP 503 renders the branded page with the path
    the visitor actually asked for, not a redirect or a blank body."""
    from werkzeug.exceptions import ServiceUnavailable

    endpoint = "test_arch_002_503_probe"
    if endpoint not in app.view_functions:

        @app.route("/__test/arch-002/deep-link", endpoint=endpoint)
        def _probe():  # pragma: no cover - trivial
            raise ServiceUnavailable()

    resp = client.get("/__test/arch-002/deep-link")
    assert resp.status_code == 503
    body = resp.get_data(as_text=True)
    # The exact requested path must appear in the rendered page (as the
    # visible path chip and as the retry link's href) rather than the
    # response silently pointing back at "/".
    assert "/__test/arch-002/deep-link" in body


def test_503_api_path_gets_json_not_html(app, client):
    """An /api/ caller must get JSON on 503 (per the existing 403/404/500
    convention in app/main/errors.py::_api_error) — HTML would fail
    response.json() client-side and turn a real outage into a silent no-op."""
    from werkzeug.exceptions import ServiceUnavailable

    endpoint = "test_arch_002_503_api_probe"
    if endpoint not in app.view_functions:

        @app.route("/api/__test/arch-002/deep-link", endpoint=endpoint)
        def _probe_api():  # pragma: no cover - trivial
            raise ServiceUnavailable()

    resp = client.get("/api/__test/arch-002/deep-link")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data is not None
    assert data["success"] is False
