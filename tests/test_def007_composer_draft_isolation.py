"""DEF-007, Capgemini dry-run: composer autosave drafts were not isolated
per user — `SavedDiagram` carried no owner, so `GET /archimate/api/
saved-viewpoints` listed every user's un-named "Unsaved diagram — ..."
autosave rows as composer tabs, and any of those users' PUT autosave could
overwrite another user's draft outright.

Fix: `SavedDiagram.created_by_id` (nullable FK, set on create); the list
endpoint hides another user's un-named draft rows; the PUT endpoint refuses
to update another user's draft. A deliberately-named saved viewpoint stays
visible and editable by anyone in the org, unchanged — this only isolates
drafts, not the collaborative diagramming feature.
"""

from __future__ import annotations

import pytest

from app import db
from app.models.archimate_core import SavedDiagram

URL_LIST = "/archimate/api/saved-viewpoints"
URL_ITEM = "/archimate/api/saved-viewpoints/{}"


def _user(org, label):
    from app.models.user import User

    user = User(
        email=f"def007-{label}-{org.id}@example.com",
        first_name="DEF007",
        last_name=label,
        organization_id=org.id,
        confirmed=True,
    )
    user.password = "TestPass123!"
    db.session.add(user)
    return user


@pytest.fixture
def scene(db_session, make_org):
    org = make_org("def007")
    user_a = _user(org, "a")
    user_b = _user(org, "b")
    db.session.flush()

    draft_a = SavedDiagram(
        name="Unsaved diagram — 1/1/2026, 1:00:00 AM",
        organization_id=org.id,
        created_by_id=user_a.id,
    )
    named = SavedDiagram(
        name="Team Target Architecture",
        organization_id=org.id,
        created_by_id=user_a.id,
    )
    db.session.add_all([draft_a, named])
    db.session.flush()
    return {"org": org, "user_a": user_a, "user_b": user_b, "draft_a": draft_a, "named": named}


def test_users_draft_not_visible_to_other_users(scene, client, login_as):
    login_as(client, scene["user_b"])
    resp = client.get(URL_LIST)
    assert resp.status_code == 200
    ids = [vp["id"] for vp in resp.get_json()["viewpoints"]]
    assert scene["draft_a"].id not in ids
    assert scene["named"].id in ids


def test_owner_still_sees_own_draft(scene, client, login_as):
    login_as(client, scene["user_a"])
    resp = client.get(URL_LIST)
    ids = [vp["id"] for vp in resp.get_json()["viewpoints"]]
    assert scene["draft_a"].id in ids


def test_other_user_cannot_overwrite_draft_via_put(scene, client, login_as):
    login_as(client, scene["user_b"])
    resp = client.put(
        URL_ITEM.format(scene["draft_a"].id),
        json={"elements": [], "relationships": []},
    )
    assert resp.status_code == 403


def test_owner_can_still_update_own_draft(scene, client, login_as):
    login_as(client, scene["user_a"])
    resp = client.put(
        URL_ITEM.format(scene["draft_a"].id),
        json={"elements": [], "relationships": []},
    )
    assert resp.status_code == 200


def test_named_viewpoint_remains_shared_and_editable(scene, client, login_as):
    """Only un-named autosave drafts are isolated — a deliberately-named save
    stays a collaborative, org-shared artifact."""
    login_as(client, scene["user_b"])
    resp = client.put(
        URL_ITEM.format(scene["named"].id),
        json={"elements": [], "relationships": []},
    )
    assert resp.status_code == 200
