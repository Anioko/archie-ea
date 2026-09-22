"""Redirects for the folded ArchiMate Roadmap and Product Roadmap pages.

Both pages now point at the single Roadmaps page (main.capability_roadmap); this
pins the redirect, the canonical still rendering, and both old endpoints staying
out of the directory and every persona's sidebar zones.
"""

from __future__ import annotations

import pytest

from tests.test_modules_directory import _make_user


@pytest.fixture
def org(make_org):
    return make_org("fold-roadmaps")


def test_archimate_roadmap_redirects_to_capability_roadmap(app, client, login_as, db_session, org):
    user = _make_user(db_session, org, enterprise_role="enterprise_architect")
    login_as(client, user)

    response = client.get("/archimate-roadmap")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/capability-roadmap")


def test_product_roadmap_redirects_to_capability_roadmap(app, client, login_as, db_session, org):
    user = _make_user(db_session, org, enterprise_role="enterprise_architect")
    login_as(client, user)

    response = client.get("/product-roadmap")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/capability-roadmap")


def test_capability_roadmap_renders(app, client, login_as, db_session, org):
    user = _make_user(db_session, org, enterprise_role="enterprise_architect")
    login_as(client, user)

    response = client.get("/capability-roadmap")

    assert response.status_code == 200


def test_folded_endpoints_absent_from_visible_module_links(app, client, login_as, db_session, org):
    from flask_login import login_user

    from app.modules.modules_directory.routes import visible_module_links

    user = _make_user(db_session, org, enterprise_role="enterprise_architect")
    login_as(client, user)

    with app.test_request_context("/"):
        login_user(user)
        endpoints = {link["endpoint"] for link in visible_module_links()}

    assert "main.archimate_roadmap" not in endpoints
    assert "roadmap_outcome.product_roadmap_page" not in endpoints


def test_folded_endpoints_absent_from_every_persona_zone():
    from app.utils.role_access import SIDEBAR_ZONES

    zone_endpoints = set()
    for zones in SIDEBAR_ZONES.values():
        for zone in zones:
            for link in zone["links"]:
                zone_endpoints.add(link["endpoint"])

    assert "main.archimate_roadmap" not in zone_endpoints
    assert "roadmap_outcome.product_roadmap_page" not in zone_endpoints
