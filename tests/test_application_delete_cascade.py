"""Deleting an application must delete its mirror ArchiMate element (finding C-02).

Every ApplicationComponent gets an ArchiMateElement created for it by a
``before_insert`` listener, so the architecture repository mirrors the portfolio.
Before this fix the delete routes removed only the application row: the element
survived every deletion, the repository grew silently, and the response still
said "Successfully deleted N application(s)" as if nothing had been left behind.

Uses the shared fixtures in tests/conftest.py (db_session rolls back
automatically; app is session-scoped).
"""

import uuid

import pytest


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


@pytest.fixture
def admin_client(app, db_session, make_org):
    from app.models.user import Role, User

    # require_roles("admin") normalizes the "Administrator" role name to "admin".
    role = db_session.query(Role).filter(Role.name == "Administrator").first()
    if role is None:
        role = Role(name="Administrator", index="admin")
        db_session.add(role)
        db_session.flush()

    org = make_org("appdel")
    user = User(
        email=f"appdel-{uuid.uuid4().hex[:8]}@example.com",
        first_name="App",
        last_name="Deleter",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user)
    db_session.flush()
    # Set the role after the insert: User's insert-time default assigns the
    # "Architect" role, which is not enough for the admin-only bulk-delete.
    user.role_id = role.id
    db_session.flush()

    client = app.test_client()
    _login(client, user.id)
    return client, org.id, user.id


def _make_application(db_session, org_id, name):
    """Create an application and return (app_id, element_id)."""
    from app.models.application_portfolio import ApplicationComponent
    from app.models.archimate_core import ArchiMateElement

    # No request context here, so the tenant middleware cannot fill this in.
    component = ApplicationComponent(
        name=name, description="cascade test", organization_id=org_id
    )
    db_session.add(component)
    db_session.flush()

    # The before_insert listener mirrors it into the architecture repository.
    assert component.archimate_element_id is not None, "no mirror element created"
    element = db_session.get(ArchiMateElement, component.archimate_element_id)
    assert element is not None
    assert element.type == "ApplicationComponent"
    return component.id, component.archimate_element_id


def _post(client, user_id, url, payload):
    """POST as the logged-in user.

    Re-runs the login helper first: writing to db.session inside the test makes
    the tenant middleware read ``current_user``, which caches an *anonymous*
    identity on the app context ``g`` that the test client then reuses, so the
    request 401s. ``_login`` clears that cache — see the note in
    tests/test_ba_tenant_and_authz.py::_login.
    """
    _login(client, user_id)
    return client.post(url, json=payload)


def _element_exists(db_session, element_id):
    """True if the element is reachable through a normal ORM read.

    This goes through the same do_orm_execute path every real read path
    (composer palette, relationship matrix, OEF export, AI context) uses, so
    it is the right check for "is this mirror still visible" regardless of
    whether it was hard-deleted or soft-deleted.
    """
    from app.models.archimate_core import ArchiMateElement

    db_session.expire_all()
    return (
        db_session.query(ArchiMateElement)
        .filter(ArchiMateElement.id == element_id)
        .count()
        > 0
    )


def _element_row_physically_present(db_session, element_id):
    """True if the row is still in the table, bypassing the soft-delete filter.

    Used only to prove the bulk path *hides* rather than *destroys* the
    mirror — the recoverability 9cda379 was trying to buy.
    """
    from sqlalchemy import text

    row = db_session.execute(
        text("SELECT deleted_at FROM archimate_elements WHERE id = :id"),
        {"id": element_id},
    ).first()
    return row is not None, (row[0] if row else None)


def test_single_delete_removes_mirror_element(admin_client, db_session):
    client, org_id, user_id = admin_client
    app_id, element_id = _make_application(
        db_session, org_id, f"QA Del {uuid.uuid4().hex[:6]}"
    )
    assert _element_exists(db_session, element_id)

    resp = _post(client, user_id, f"/applications/{app_id}/delete", {})
    assert resp.status_code == 200, resp.data[:400]
    payload = resp.get_json()
    assert payload["success"] is True
    assert payload["elements_deleted"] == 1
    assert payload["errors"] == []

    assert not _element_exists(db_session, element_id)


def test_bulk_delete_hides_mirror_elements_and_reports_them(
    admin_client, db_session
):
    """Bulk-delete soft-deletes the application AND its mirror element.

    Regression test for the reopened C-02: 9cda379 changed bulk-delete from
    a hard delete to a soft delete (nullable deleted_at/deleted_by) for
    recoverability, but did not touch the ArchiMate mirror, so it stayed
    live and visible in the composer palette, relationship matrix, OEF
    export and AI context after the application was "deleted". The mirror
    must now be hidden (deleted_at set) rather than destroyed, so a restore
    can bring both back together — the same recoverability contract 9cda379
    established for the application row.
    """
    client, org_id, user_id = admin_client
    made = [
        _make_application(db_session, org_id, f"QA Bulk {uuid.uuid4().hex[:6]}")
        for _ in range(3)
    ]
    app_ids = [a for a, _ in made]
    element_ids = [e for _, e in made]
    assert all(_element_exists(db_session, e) for e in element_ids)

    resp = _post(
        client, user_id, "/applications/bulk-delete", {"ids": app_ids, "confirm": True}
    )
    assert resp.status_code == 200, resp.data[:400]
    payload = resp.get_json()
    assert payload["success"] is True
    assert payload["deleted"] == 3
    # The response must account for the architecture repository too, not just
    # the application table — that mismatch was the original C-02 defect,
    # and reporting elements_deleted: 0 while soft-deleting nothing was the
    # reopened version of it.
    assert payload["elements_deleted"] == 3
    assert "relationships_deleted" in payload
    assert payload["errors"] == []
    assert "ArchiMate element" in payload["message"]
    assert "3" in payload["message"]

    for element_id in element_ids:
        # Unreachable through any normal ORM read — composer palette,
        # relationship matrix, OEF export and AI context all query through
        # this same path, so this is the assertion that would fail if the
        # mirror became visible again.
        assert not _element_exists(db_session, element_id)
        # But the row itself still exists, hidden rather than destroyed —
        # proof the delete is reversible, matching what 9cda379 promised.
        present, deleted_at = _element_row_physically_present(
            db_session, element_id
        )
        assert present, "mirror element was hard-deleted, not hidden"
        assert deleted_at is not None, "mirror element deleted_at was not set"


def test_bulk_delete_mirror_element_reachable_after_restore(admin_client, db_session):
    """Restoring both deleted_at columns brings the mirror back, per the
    recovery contract documented on bulk_delete_applications."""
    from sqlalchemy import text

    client, org_id, user_id = admin_client
    app_id, element_id = _make_application(
        db_session, org_id, f"QA Restore {uuid.uuid4().hex[:6]}"
    )

    resp = _post(
        client, user_id, "/applications/bulk-delete", {"ids": [app_id], "confirm": True}
    )
    assert resp.status_code == 200, resp.data[:400]
    assert not _element_exists(db_session, element_id)

    db_session.execute(
        text(
            "UPDATE application_components SET deleted_at = NULL, "
            "deleted_by = NULL WHERE id = :id"
        ),
        {"id": app_id},
    )
    db_session.execute(
        text(
            "UPDATE archimate_elements SET deleted_at = NULL, "
            "deleted_by = NULL WHERE id = :id"
        ),
        {"id": element_id},
    )
    db_session.commit()

    assert _element_exists(db_session, element_id)


def test_delete_removes_relationships_of_the_mirror_element(
    admin_client, db_session
):
    from app.models.archimate_core import ArchiMateRelationship

    client, org_id, user_id = admin_client
    app_id, element_id = _make_application(
        db_session, org_id, f"QA Rel {uuid.uuid4().hex[:6]}"
    )
    _, other_element_id = _make_application(
        db_session, org_id, f"QA Peer {uuid.uuid4().hex[:6]}"
    )

    rel = ArchiMateRelationship(
        type="serving",
        source_id=element_id,
        target_id=other_element_id,
        organization_id=org_id,
    )
    db_session.add(rel)
    db_session.flush()
    rel_id = rel.id

    resp = _post(client, user_id, f"/applications/{app_id}/delete", {})
    assert resp.status_code == 200, resp.data[:400]
    payload = resp.get_json()
    assert payload["elements_deleted"] == 1
    assert payload["relationships_deleted"] == 1

    db_session.expire_all()
    assert (
        db_session.query(ArchiMateRelationship)
        .filter(ArchiMateRelationship.id == rel_id)
        .count()
        == 0
    )
    # The peer element is untouched — the cascade is deliberately narrow.
    assert _element_exists(db_session, other_element_id)
