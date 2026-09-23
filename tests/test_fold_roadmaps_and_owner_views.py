"""Redirects for the folded ArchiMate Roadmap, Product Roadmap and My
Applications Roadmap Impact pages.

The two roadmap pages point at the single Roadmaps page (main.capability_roadmap);
My Applications Roadmap Impact points at the My Applications dashboard
(my_applications.dashboard). This pins each redirect, each canonical still
rendering, and all three old endpoints staying out of the directory and every
persona's sidebar zones.

My Applications Health is not folded here: it renders a "Not assessed" list with
per-application links into each edit form (tests/test_my_applications_ownership_numbers.py,
tests/test_my_applications_health_ai.py), and nothing on the dashboard reproduces
that list, so redirecting it would remove working, tested functionality with
nothing in its place. It keeps rendering its own page.
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


def test_my_applications_roadmap_redirects_to_dashboard(app, client, login_as, db_session, org):
    # requires_application_owner only admits application_manager (or platform
    # admin), unlike the roadmap pages above which any enterprise role reaches.
    user = _make_user(db_session, org, enterprise_role="application_manager")
    login_as(client, user)

    response = client.get("/my-applications/roadmap")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/my-applications/#roadmap")


def test_my_applications_dashboard_renders(app, client, login_as, db_session, org):
    user = _make_user(db_session, org, enterprise_role="application_manager")
    login_as(client, user)

    response = client.get("/my-applications/")

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
    assert "my_applications.roadmap_impact" not in endpoints


def test_folded_endpoints_absent_from_every_persona_zone():
    from app.utils.role_access import SIDEBAR_ZONES

    zone_endpoints = set()
    for zones in SIDEBAR_ZONES.values():
        for zone in zones:
            for link in zone["links"]:
                zone_endpoints.add(link["endpoint"])

    assert "main.archimate_roadmap" not in zone_endpoints
    assert "roadmap_outcome.product_roadmap_page" not in zone_endpoints
    assert "my_applications.roadmap_impact" not in zone_endpoints
