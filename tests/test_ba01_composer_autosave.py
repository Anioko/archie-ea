"""BA-01 — composer autosave must not be able to fail permanently.

`PUT /archimate/api/saved-viewpoints/<id>` ended in a bare `db.session.commit()`.
Two payloads the composer routinely produces raised an unhandled IntegrityError:

* a duplicate `element_id` (two canvas cells referencing the same element, which
  is normal on an AI-generated diagram) violated `uq_diagram_element`;
* an `element_id` with no `archimate_elements` row violated the FK.

Both 500'd, and because autosave retried the identical payload the diagram was
never persisted at all — the user's reported "Auto-save failed after multiple
attempts".

These tests pin the contract: duplicates collapse to one row at the LAST
position, unknown or cross-org ids are refused with a named 400 (never a 500),
the session survives a rejection, and the happy path still round-trips.
"""

from __future__ import annotations

import pytest

from app import db
from app.models.archimate_core import (
    ArchiMateElement,
    ArchiMateRelationship,
    SavedDiagram,
    SavedDiagramElement,
    SavedDiagramRelationship,
)

URL = "/archimate/api/saved-viewpoints/{}"


def _element(org, name):
    el = ArchiMateElement(
        name=name,
        type="ApplicationComponent",
        layer="application",
        organization_id=org.id,
    )
    db.session.add(el)
    return el


def _user(org, label):
    from app.models.user import User

    user = User(
        email=f"ba01-{label}-{org.id}@example.com",
        first_name="BA",
        last_name="One",
        organization_id=org.id,
        # A user without this is bounced to /account/unconfirmed by a
        # before_request hook, so every API call would 302 instead of running.
        confirmed=True,
    )
    user.password = "TestPass123!"
    db.session.add(user)
    return user


@pytest.fixture
def scene(db_session, make_org):
    """One org with a diagram, three elements, one relationship, and a user."""
    org = make_org("ba01")
    els = [_element(org, f"BA01 Element {i}") for i in range(3)]
    diagram = SavedDiagram(name="BA01 Diagram", organization_id=org.id)
    db.session.add(diagram)
    user = _user(org, "owner")
    db.session.flush()
    rel = ArchiMateRelationship(
        type="association",
        source_id=els[0].id,
        target_id=els[1].id,
        organization_id=org.id,
    )
    db.session.add(rel)
    db.session.flush()
    return {
        "org": org,
        "diagram": diagram,
        "elements": els,
        "relationship": rel,
        "user": user,
    }


def test_duplicate_element_id_saves_one_row_at_the_last_position(
    scene, client, login_as
):
    """Two cells for one element must collapse, not 500 the autosave."""
    diagram = scene["diagram"]
    dup = scene["elements"][0].id
    login_as(client, scene["user"])

    resp = client.put(
        URL.format(diagram.id),
        json={
            "name": "Autosaved",
            "elements": [
                {"element_id": dup, "x": 10, "y": 10},
                {"element_id": dup, "x": 400, "y": 200},
            ],
            "relationships": [],
        },
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["element_count"] == 1

    rows = SavedDiagramElement.query.filter_by(diagram_id=diagram.id).all()
    assert len(rows) == 1
    # Last entry wins: it is the most recently touched cell, i.e. where the
    # user just dragged the element to. Keeping the first would snap it back.
    assert (rows[0].position_x, rows[0].position_y) == (400, 200)


def test_duplicate_relationship_id_saves_one_row(scene, client, login_as):
    """saved_diagram_relationships has the same unique constraint."""
    diagram = scene["diagram"]
    rel_id = scene["relationship"].id
    login_as(client, scene["user"])

    resp = client.put(
        URL.format(diagram.id),
        json={
            "elements": [],
            "relationships": [
                {"relationship_id": rel_id, "routing_style": "manhattan"},
                {"relationship_id": rel_id, "routing_style": "smooth"},
            ],
        },
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    rows = SavedDiagramRelationship.query.filter_by(diagram_id=diagram.id).all()
    assert len(rows) == 1
    assert rows[0].routing_style == "smooth"


def test_unknown_element_id_is_a_clean_400_and_leaves_the_session_usable(
    scene, client, login_as
):
    """An id with no row must be named in a 400, never crash the request."""
    diagram_id = scene["diagram"].id
    login_as(client, scene["user"])

    resp = client.put(
        URL.format(diagram_id),
        json={
            "name": "Autosaved",
            "elements": [{"element_id": 99999999, "x": 10, "y": 10}],
            "relationships": [],
        },
    )

    assert resp.status_code == 400, resp.get_data(as_text=True)
    error = resp.get_json()["error"]
    assert "element_id" in error
    assert "99999999" in error

    # The rollback happened, so the session is not poisoned. Without it this
    # raises InFailedSqlTransaction and every later query in the request 500s.
    assert db.session.execute(db.text("SELECT 1")).scalar() == 1
    assert SavedDiagramElement.query.filter_by(diagram_id=diagram_id).count() == 0


def test_element_id_from_another_org_is_refused(scene, make_org, client, login_as):
    """One org must not be able to pin another org's element onto its diagram."""
    other_org = make_org("ba01-other")
    stranger = _element(other_org, "Someone Else's Element")
    db.session.flush()
    login_as(client, scene["user"])

    resp = client.put(
        URL.format(scene["diagram"].id),
        json={
            "elements": [{"element_id": stranger.id, "x": 5, "y": 5}],
            "relationships": [],
        },
    )

    assert resp.status_code == 400, resp.get_data(as_text=True)
    assert str(stranger.id) in resp.get_json()["error"]
    assert (
        SavedDiagramElement.query.filter_by(element_id=stranger.id).count() == 0
    ), "a cross-org element must never be written into the diagram"


def test_happy_path_saves_elements_and_relationships(scene, client, login_as):
    """The ordinary save still round-trips everything it is given."""
    diagram = scene["diagram"]
    els = scene["elements"]
    rel = scene["relationship"]
    login_as(client, scene["user"])

    resp = client.put(
        URL.format(diagram.id),
        json={
            "name": "Target State",
            "elements": [
                {"element_id": els[0].id, "x": 10, "y": 20, "width": 200, "height": 80},
                {"element_id": els[1].id, "x": 300, "y": 40},
                {"element_id": els[2].id, "x": 500, "y": 60},
            ],
            "relationships": [
                {
                    "relationship_id": rel.id,
                    "waypoints": [{"x": 100, "y": 100}],
                    "routing_style": "smooth",
                },
            ],
        },
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["name"] == "Target State"
    assert body["element_count"] == 3
    assert body["relationship_count"] == 1

    saved = {
        row.element_id: row
        for row in SavedDiagramElement.query.filter_by(diagram_id=diagram.id).all()
    }
    assert set(saved) == {e.id for e in els}
    assert (saved[els[0].id].position_x, saved[els[0].id].position_y) == (10, 20)
    assert saved[els[0].id].width == 200

    rel_row = SavedDiagramRelationship.query.filter_by(diagram_id=diagram.id).one()
    assert rel_row.relationship_id == rel.id
    assert rel_row.routing_style == "smooth"
    assert '"x": 100' in rel_row.waypoints_json
