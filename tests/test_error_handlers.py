"""ARCH-002: a 503 must preserve the requested path instead of dropping the
user at "/". Covers the Flask-level errors/503.html handler in
app/main/errors.py — the Caddy-level branded page in deploy/Caddyfile.proxy
handles the case where the whole process is down and cannot serve this at
all, and is not exercisable from a Flask test client.

These tests drive the registered error handler through
``app.handle_http_exception`` inside a request context rather than declaring a
probe route. The ``app`` fixture is session-scoped, and Flask refuses
``@app.route`` once the application has served its first request — so a
route-registering version of this test passes alone and fails as soon as any
other test file runs first. Dispatching the exception directly exercises the
same handler, template and request path without mutating the shared app.
"""

from __future__ import annotations

from werkzeug.exceptions import ServiceUnavailable


def _render_503(app, path):
    """Return the response the registered 503 handler produces for ``path``."""
    with app.test_request_context(path):
        return app.make_response(app.handle_http_exception(ServiceUnavailable()))


def test_503_preserves_requested_path(app):
    """A 503 renders the branded page carrying the path the visitor actually
    asked for, rather than redirecting or blanking the body."""
    resp = _render_503(app, "/__test/arch-002/deep-link")

    assert resp.status_code == 503
    body = resp.get_data(as_text=True)
    # The exact requested path must appear in the rendered page (as the
    # visible path chip and as the retry link's href) rather than the
    # response silently pointing back at "/".
    assert "/__test/arch-002/deep-link" in body


def test_503_api_path_gets_json_not_html(app):
    """An /api/ caller must get JSON on 503 (per the existing 403/404/500
    convention in app/main/errors.py::_api_error) — HTML would fail
    response.json() client-side and turn a real outage into a silent no-op."""
    resp = _render_503(app, "/api/__test/arch-002/deep-link")

    assert resp.status_code == 503
    assert resp.mimetype == "application/json"
    data = resp.get_json()
    assert data is not None
    assert data["success"] is False
