"""ARCH-050: /architecture/element/<id> must 404 for invalid/non-existent ids.

Before the fix, ``archimate_crud``'s browsing routes were registered as a bare
``/<layer>/<element_type>`` pair under the ``/architecture`` prefix — an
unconstrained two-segment catch-all. That silently absorbed
``/architecture/element/99999999`` (layer="element", element_type="99999999")
and every other typo/garbage id, since neither segment was validated as a real
layer before the handler ran a lookup and, on a miss, flashed a warning and
redirected to the elements dashboard — which renders 200. Sibling routes like
``/solutions/<id>`` correctly 404 on a bad id; this one never did.

The fix restricts ``<layer>`` to ``any(<LAYER_CONFIG keys>)`` via
``_LAYER_URL_PATTERN``, so a first segment of "element" (not a real layer) no
longer matches these routes at all and falls through to Flask's own routing
404, which is handled by the branded ``errors/404.html`` (see
``app/utils/error_handlers.py::handle_404``).

Uses the shared ``app`` fixture's test client to exercise real Werkzeug URL
routing — no probe route is registered (see tests/test_error_handlers.py for
why that would break other tests sharing the session-scoped ``app`` fixture).
"""

from __future__ import annotations

import pytest


NOT_FOUND_INPUTS = [
    "99999999",  # oversized / non-existent numeric id
    "-1",  # negative
    "0",  # zero
    "abc",  # non-numeric
    "1'or'1",  # injection-shaped, non-numeric
]


@pytest.mark.parametrize("bad_id", NOT_FOUND_INPUTS)
def test_element_route_404s_on_bad_id(app, bad_id):
    client = app.test_client()
    resp = client.get(f"/architecture/element/{bad_id}")
    assert resp.status_code == 404, (
        f"/architecture/element/{bad_id} returned {resp.status_code}, expected 404 "
        f"(body starts: {resp.get_data(as_text=True)[:200]!r})"
    )


def test_element_route_404_page_is_branded_with_catalogue_link(app):
    """The 404 page must not be a bare Werkzeug default — it should offer a
    route back to the catalogue, per ARCH-050's acceptance criteria."""
    client = app.test_client()
    resp = client.get("/architecture/element/99999999")
    assert resp.status_code == 404
    body = resp.get_data(as_text=True)
    assert "404" in body
    # errors/404.html renders an actual navigational link, not just text.
    assert "href=" in body


def test_sibling_valid_layer_route_still_reachable(app):
    """Guard against over-restricting: a genuine by-layer browsing URL using a
    real LAYER_CONFIG key must still route (may 302 to login, never 404)."""
    client = app.test_client()
    resp = client.get("/architecture/application/ApplicationComponent")
    assert resp.status_code != 404
