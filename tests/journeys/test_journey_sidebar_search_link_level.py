"""Journey: the sidebar's "Search navigation..." box returns individual pages, each labelled with its zone,
matches either spelling of a variant word, and never lists a page the persona cannot open.

The box previously gave results the module catalogue but matched whole zones (a hit on one label
kept every link in that zone) and had no spelling tolerance. The requirement is link-level results,
en-GB/en-US equivalence, and an honest empty state with a way out (global search, or /modules/) when
nothing matches.

This file covers the server contract (/api/sidebar/search's zone attribution and spelling-blind matching);
tests/journeys/test_journey_sidebar_search_rendered.py covers the rendered box in a real browser.
"""
import json

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey


def _persona(app, enterprise_role):
    from app import db

    with app.app_context():
        org_id = make_org(db, "SidebarSearchLink")
        return make_user(db, org_id, "u", enterprise_role, role_name="Architect")


def _modules(client, q):
    response = client.get("/api/sidebar/search", query_string={"q": q})
    assert response.status_code == 200, response.data[:200]
    return [r for r in json.loads(response.data)["results"] if r["type"] == "module"]


def test_impact_analysis_is_found_by_name_and_opens_the_right_page(app, client):
    login(client, _persona(app, "solution_architect"))
    hits = _modules(client, "impact")
    assert any(h["name"] == "Impact Analysis" and h["url"] == "/strategic/impact-analysis" for h in hits), hits


def test_a_hit_carries_the_persona_own_zone_name(app, client):
    login(client, _persona(app, "solution_architect"))
    hits = _modules(client, "vendor")
    matched = [h for h in hits if h["name"] == "Vendors"]
    assert matched, hits
    assert matched[0]["zone"] in ("Library", "My work", "Home", "Governance", "Admin"), matched[0]


def test_a_hit_outside_the_persona_own_zones_is_labelled_all_modules(app, client):
    """Duplicate Detection is not in a solution architect's own zones, only reachable via /modules/."""
    login(client, _persona(app, "solution_architect"))
    hits = _modules(client, "duplicate")
    assert hits, "expected at least one module hit for 'duplicate'"
    assert all(h["zone"] == "All modules" for h in hits), hits


@pytest.mark.parametrize("query,expected_name", [("license", "Licences"), ("licence", "Licences")])
def test_either_spelling_finds_the_same_page(app, client, query, expected_name):
    login(client, _persona(app, "procurement"))
    hits = _modules(client, query)
    assert any(h["name"] == expected_name for h in hits), (query, hits)


def test_a_module_the_persona_cannot_open_is_never_offered(app, client):
    """Organisations is guarded by platform_admin_required; it must not be a search hit for an architect."""
    login(client, _persona(app, "solution_architect"))
    assert not [h for h in _modules(client, "organizations") if "/admin/" in h["url"]]


def test_every_module_result_has_every_field_the_client_renders(app, client):
    login(client, _persona(app, "solution_architect"))
    hits = _modules(client, "impact")
    assert hits
    for hit in hits:
        assert set(hit) >= {"type", "id", "name", "url", "zone"}
        assert hit["name"] and hit["url"] and hit["zone"]
