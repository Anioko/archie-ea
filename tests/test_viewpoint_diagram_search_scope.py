"""viewpoint_diagram_data() must scope the diagram to a search term.

Live-reported bug: "Diagram View" on the Architecture Elements page ignored
the page's own search box entirely -- it always requested
/api/archimate/viewpoints/<key>/diagram with only limit/layer, so searching
for a specific element and opening the diagram showed an arbitrary unordered
slice of unrelated elements (including test/seed junk) with almost no
relationships among them, not the searched element and what it actually
connects to.

Fix: loadDiagram() now passes the search term through as `search`, and the
backend scopes to matching elements plus their real one-hop relationship
neighbors.
"""
from __future__ import annotations

import uuid

import pytest

from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
from app.models.user import User

pytestmark = pytest.mark.usefixtures("db_session")


def _make_user(db_session, make_org):
    org = make_org("diagramscope")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"diagramscope-{suffix}@example.com",
        first_name="Diagram",
        last_name="Scope",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    user.password = "Sup3rSecret!23"
    db_session.add(user)
    db_session.flush()
    return org, user


def test_search_scopes_to_matched_element_and_its_real_neighbor(
    app, db_session, make_org, client, login_as
):
    org, user = _make_user(db_session, make_org)
    login_as(client, user)

    with app.test_request_context():
        from flask import g
        g.current_org_id = org.id

        target = ArchiMateElement(name="Design partners", type="Stakeholder", layer="motivation")
        neighbor = ArchiMateElement(name="Partner Onboarding Process", type="BusinessProcess", layer="business")
        unrelated = ArchiMateElement(name="Unrelated Load Balancer", type="Node", layer="technology")
        db_session.add_all([target, neighbor, unrelated])
        db_session.flush()

        rel = ArchiMateRelationship(source_id=neighbor.id, target_id=target.id, type="Serving")
        db_session.add(rel)
        db_session.flush()

        target_id, neighbor_id, unrelated_id, rel_id = target.id, neighbor.id, unrelated.id, rel.id

    resp = client.get(
        "/api/archimate/viewpoints/layered/diagram?limit=30&search=Design%20partners"
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True

    element_ids = {e["id"] for e in data["elements"]}
    assert target_id in element_ids, "the searched element itself must be in the diagram"
    assert neighbor_id in element_ids, "a real one-hop relationship neighbor must be included"
    assert unrelated_id not in element_ids, "an unrelated element must NOT be pulled in just to pad the count"

    rel_ids = {r["id"] for r in data["relationships"]}
    assert rel_id in rel_ids, "the real relationship between the matched element and its neighbor must render"


def test_no_search_still_returns_a_deterministic_ordered_set(
    app, db_session, make_org, client, login_as
):
    """Without a search term, behavior is unchanged except elements are now
    ordered by name (was: no ORDER BY, effectively arbitrary DB order)."""
    org, user = _make_user(db_session, make_org)
    login_as(client, user)

    with app.test_request_context():
        from flask import g
        g.current_org_id = org.id
        b = ArchiMateElement(name="B Element", type="Stakeholder", layer="motivation")
        a = ArchiMateElement(name="A Element", type="Stakeholder", layer="motivation")
        db_session.add_all([b, a])
        db_session.flush()

    resp = client.get("/api/archimate/viewpoints/layered/diagram?limit=30")
    assert resp.status_code == 200
    data = resp.get_json()
    names = [e["name"] for e in data["elements"] if e["name"] in ("A Element", "B Element")]
    assert names == ["A Element", "B Element"], "elements should be name-ordered, not DB-order-dependent"
