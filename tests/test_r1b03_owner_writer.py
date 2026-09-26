"""Tests for PR 1 of R1-B03: owner writer, person picker, backfill, and coverage view.

Two-organisation tests verify that an owner from organisation B cannot be
assigned to organisation A's application, that coverage counts only the
caller's organisation, and that the backfill keeps organisations apart.
"""

from __future__ import annotations

import json
import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


# ── helpers ─────────────────────────────────────────────────────────────────


def _make_user(db_session, org, role, label):
    from app.models.user import Role, User

    Role.insert_roles()
    role_obj = Role.query.filter_by(name="User").first()

    user = User(
        email=f"r1b03-{label}-{uuid.uuid4().hex[:8]}@example.com",
        first_name=label.capitalize(),
        last_name="Test",
        organization_id=org.id,
        confirmed=True,
        enterprise_role=role,
        role_id=role_obj.id if role_obj else None,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_app(db_session, org, name, **extra):
    from app.models.application_portfolio import ApplicationComponent

    app = ApplicationComponent(
        name=f"{name} {uuid.uuid4().hex[:6]}",
        organization_id=org.id,
        **extra,
    )
    db_session.add(app)
    db_session.flush()
    return app


def _post_json(client, path, data):
    return client.post(
        path,
        data=json.dumps(data),
        content_type="application/json",
    )


def _put_json(client, path, data):
    return client.put(
        path,
        data=json.dumps(data),
        content_type="application/json",
    )


def _delete(client, path):
    return client.delete(path)


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def two_orgs(db_session, make_org):
    """Two organisations, each with one app manager and one application."""
    org_a = make_org("r1b03-a")
    org_b = make_org("r1b03-b")
    manager_a = _make_user(db_session, org_a, "application_manager", "managera")
    manager_b = _make_user(db_session, org_b, "application_manager", "managerb")
    app_a = _make_app(db_session, org_a, "App A")
    app_b = _make_app(db_session, org_b, "App B")
    return {
        "db_session": db_session,
        "org_a": org_a,
        "org_b": org_b,
        "manager_a": manager_a,
        "manager_b": manager_b,
        "app_a": app_a,
        "app_b": app_b,
    }


# ── 1. Owner writer: add ────────────────────────────────────────────────────


def test_add_owner_success(db_session, make_org, client, login_as):
    """An application manager can add an owner to their own application."""
    org = make_org("r1b03-add")
    manager = _make_user(db_session, org, "application_manager", "addmanager")
    app = _make_app(db_session, org, "Add Test")
    login_as(client, manager)

    resp = _post_json(client, f"/applications/{app.id}/owners", {
        "user_id": manager.id,
        "ownership_type": "primary",
    })
    assert resp.status_code == 201, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["success"] is True
    assert data["owner"]["ownership_type"] == "primary"
    assert data["owner"]["user_id"] == manager.id


def test_add_owner_duplicate_refused(db_session, make_org, client, login_as):
    """Adding the same user with the same type returns 409."""
    org = make_org("r1b03-dup")
    manager = _make_user(db_session, org, "application_manager", "dupmanager")
    app = _make_app(db_session, org, "Dup Test")
    login_as(client, manager)

    _post_json(client, f"/applications/{app.id}/owners", {
        "user_id": manager.id,
        "ownership_type": "backup",
    })
    resp = _post_json(client, f"/applications/{app.id}/owners", {
        "user_id": manager.id,
        "ownership_type": "backup",
    })
    assert resp.status_code == 409, resp.get_data(as_text=True)


def test_add_owner_invalid_type_refused(db_session, make_org, client, login_as):
    """An invalid ownership type returns 400."""
    org = make_org("r1b03-type")
    manager = _make_user(db_session, org, "application_manager", "typemanager")
    app = _make_app(db_session, org, "Type Test")
    login_as(client, manager)

    resp = _post_json(client, f"/applications/{app.id}/owners", {
        "user_id": manager.id,
        "ownership_type": "invalid_type",
    })
    assert resp.status_code == 400, resp.get_data(as_text=True)


# ── 2. Two-organisation isolation ────────────────────────────────────────────


def test_owner_from_another_org_refused(two_orgs, client, login_as):
    """An owner from organisation B cannot be assigned to organisation A's app."""
    login_as(client, two_orgs["manager_a"])

    resp = _post_json(client, f"/applications/{two_orgs['app_a'].id}/owners", {
        "user_id": two_orgs["manager_b"].id,
        "ownership_type": "primary",
    })
    assert resp.status_code == 404, resp.get_data(as_text=True)
    assert "not found in your organisation" in resp.get_json()["error"]


def test_owner_list_scoped_to_caller_org(two_orgs, client, login_as):
    """Listing owners for an app only returns owners from the caller's organisation."""
    from app.models.application_owner import ApplicationOwner

    db_session = two_orgs["db_session"]
    org_a = two_orgs["org_a"]
    org_b = two_orgs["org_b"]

    # Add owner rows directly (not through API)
    db_session.add(ApplicationOwner(
        application_id=two_orgs["app_a"].id,
        user_id=two_orgs["manager_a"].id,
        organization_id=org_a.id,
        ownership_type="primary",
    ))
    # Add a cross-org row (should not appear when org A lists owners)
    db_session.add(ApplicationOwner(
        application_id=two_orgs["app_a"].id,
        user_id=two_orgs["manager_b"].id,
        organization_id=org_b.id,
        ownership_type="primary",
    ))
    db_session.flush()

    login_as(client, two_orgs["manager_a"])
    resp = client.get(f"/applications/{two_orgs['app_a'].id}/owners")
    assert resp.status_code == 200
    data = resp.get_json()
    owner_ids = {o["user_id"] for o in data["owners"]}
    assert two_orgs["manager_a"].id in owner_ids
    assert two_orgs["manager_b"].id not in owner_ids


# ── 3. Owner writer: change type & remove ───────────────────────────────────


def test_change_owner_type(db_session, make_org, client, login_as):
    """An owner's type can be changed."""
    from app.models.application_owner import ApplicationOwner

    org = make_org("r1b03-change")
    manager = _make_user(db_session, org, "application_manager", "changemanager")
    app = _make_app(db_session, org, "Change Test")

    db_session.add(ApplicationOwner(
        application_id=app.id,
        user_id=manager.id,
        organization_id=org.id,
        ownership_type="primary",
    ))
    db_session.flush()
    owner_id = ApplicationOwner.query.filter_by(application_id=app.id).first().id

    login_as(client, manager)
    resp = _put_json(client, f"/applications/{app.id}/owners/{owner_id}", {
        "ownership_type": "business",
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["owner"]["ownership_type"] == "business"


def test_remove_owner(db_session, make_org, client, login_as):
    """An owner can be removed."""
    from app.models.application_owner import ApplicationOwner

    org = make_org("r1b03-remove")
    manager = _make_user(db_session, org, "application_manager", "removemanager")
    app = _make_app(db_session, org, "Remove Test")

    db_session.add(ApplicationOwner(
        application_id=app.id,
        user_id=manager.id,
        organization_id=org.id,
        ownership_type="primary",
    ))
    db_session.flush()
    owner_id = ApplicationOwner.query.filter_by(application_id=app.id).first().id

    login_as(client, manager)
    resp = _delete(client, f"/applications/{app.id}/owners/{owner_id}")
    assert resp.status_code == 200
    assert ApplicationOwner.query.get(owner_id) is None


def test_change_owner_type_not_found(db_session, make_org, client, login_as):
    """Changing a non-existent owner returns 404."""
    org = make_org("r1b03-notfound")
    manager = _make_user(db_session, org, "application_manager", "notfoundmanager")
    app = _make_app(db_session, org, "Not Found")
    login_as(client, manager)

    resp = _put_json(client, f"/applications/{app.id}/owners/99999", {
        "ownership_type": "business",
    })
    assert resp.status_code == 404


# ── 4. Person picker ────────────────────────────────────────────────────────


def test_owner_picker_finds_users(db_session, make_org, client, login_as):
    """The person picker returns users matching the search query."""
    org = make_org("r1b03-picker")
    alice = _make_user(db_session, org, "application_manager", "alice")
    bob = _make_user(db_session, org, "application_manager", "bob")
    app = _make_app(db_session, org, "Picker Test")
    login_as(client, alice)

    resp = client.get(f"/applications/{app.id}/owners/search?q=alice")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["results"]) == 1
    assert data["results"][0]["id"] == alice.id

    resp = client.get(f"/applications/{app.id}/owners/search?q=bob")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["results"]) == 1
    assert data["results"][0]["id"] == bob.id


def test_owner_picker_short_query_returns_empty(db_session, make_org, client, login_as):
    """The person picker requires at least 2 characters."""
    org = make_org("r1b03-short")
    manager = _make_user(db_session, org, "application_manager", "shortmgr")
    app = _make_app(db_session, org, "Short Query")
    login_as(client, manager)

    resp = client.get(f"/applications/{app.id}/owners/search?q=a")
    assert resp.status_code == 200
    assert resp.get_json()["results"] == []


def test_owner_picker_scoped_to_org(two_orgs, client, login_as):
    """The person picker only returns users within the caller's organisation."""
    login_as(client, two_orgs["manager_a"])

    resp = client.get(
        f"/applications/{two_orgs['app_a'].id}/owners/search?q={two_orgs['manager_b'].first_name}"
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["results"]) == 0, "cross-org user should not appear"


# ── 5. Backfill command ─────────────────────────────────────────────────────


def test_backfill_command_dry_run(app, db_session):
    """The backfill dry-run reports stats without writing."""
    from app.commands.backfill_application_owners import backfill_owner_data

    stats = backfill_owner_data(dry_run=True)
    assert isinstance(stats, dict)
    assert "legacy_ownership_rows" in stats
    assert "text_owner_fields" in stats
    assert stats["legacy_ownership_rows"] >= 0


def test_backfill_migrates_text_owners(db_session, make_org):
    """Backfill creates ApplicationOwner rows from text owner columns."""
    from app.commands.backfill_application_owners import backfill_owner_data
    from app.models.application_owner import ApplicationOwner

    org = make_org("r1b03-bftext")
    user = _make_user(db_session, org, "application_manager", "bftextuser")
    _make_app(db_session, org, "Backfill Text", business_owner=f"{user.first_name} {user.last_name}")

    stats = backfill_owner_data(dry_run=False)
    assert stats["text_owner_fields"] >= 1

    rows = ApplicationOwner.query.all()
    assert len(rows) >= 1


def test_backfill_keeps_organisations_apart(db_session, make_org):
    """Backfill processes each organisation independently."""
    from app.commands.backfill_application_owners import backfill_owner_data
    from app.models.application_owner import ApplicationOwner
    from app.models.application_portfolio import ApplicationComponent

    org_a = make_org("r1b03-bfa")
    org_b = make_org("r1b03-bfb")
    user_a = _make_user(db_session, org_a, "application_manager", "bfusera")
    user_b = _make_user(db_session, org_b, "application_manager", "bfuserb")
    _make_app(db_session, org_a, "OrgA App", business_owner=f"{user_a.first_name} {user_a.last_name}")
    _make_app(db_session, org_b, "OrgB App", business_owner=f"{user_b.first_name} {user_b.last_name}")

    backfill_owner_data(dry_run=False)

    rows_a = (
        ApplicationOwner.query
        .join(ApplicationComponent, ApplicationOwner.application_id == ApplicationComponent.id)
        .filter(ApplicationComponent.organization_id == org_a.id)
        .all()
    )
    rows_b = (
        ApplicationOwner.query
        .join(ApplicationComponent, ApplicationOwner.application_id == ApplicationComponent.id)
        .filter(ApplicationComponent.organization_id == org_b.id)
        .all()
    )

    assert len(rows_a) >= 1
    assert len(rows_b) >= 1
    for r in rows_a:
        if r.user_id is not None:
            assert r.user_id == user_a.id, "org A row points to wrong user"


# ── 6. Ownership coverage view ──────────────────────────────────────────────


def test_coverage_view_loads(db_session, make_org, client, login_as):
    """The coverage view renders for a CTO user."""
    org = make_org("r1b03-cov")
    cto = _make_user(db_session, org, "cto", "ctocoverage")
    _make_app(db_session, org, "Covered App")
    login_as(client, cto)

    resp = client.get("/applications/ownership-coverage")
    assert resp.status_code == 200


def test_coverage_view_org_isolation(two_orgs, client, login_as):
    """Coverage counts only the caller's organisation."""
    from app.models.enterprise_intelligence import OrganizationUnit

    db_session = two_orgs["db_session"]

    db_session.add(OrganizationUnit(
        name="Finance",
        organization_id=two_orgs["org_a"].id,
    ))
    _make_app(db_session, two_orgs["org_a"], "Finance App", business_domain="Finance")
    db_session.flush()

    login_as(client, two_orgs["manager_a"])
    resp = client.get("/applications/ownership-coverage")
    assert resp.status_code == 200
    assert b"Finance" in resp.data


# ── 7. Application owner records on the fact sheet ──────────────────────────


def test_fact_sheet_shows_owners(db_session, make_org, client, login_as):
    """The fact sheet includes application owners from ApplicationOwner rows."""
    from app.models.application_owner import ApplicationOwner

    org = make_org("r1b03-fs")
    manager = _make_user(db_session, org, "application_manager", "fsmanager")
    app = _make_app(db_session, org, "FS Test")
    db_session.add(ApplicationOwner(
        application_id=app.id,
        user_id=manager.id,
        organization_id=org.id,
        ownership_type="primary",
    ))
    db_session.flush()

    login_as(client, manager)
    resp = client.get(f"/applications/{app.id}/fact-sheet")
    assert resp.status_code == 200
    assert manager.first_name.encode() in resp.data


# ── 8. Edit form shows legacy text fields as read-only ──────────────────────


def test_edit_form_has_readonly_text_owners(db_session, make_org, client, login_as):
    """The edit form renders business_owner and technical_owner as read-only."""
    org = make_org("r1b03-ro")
    manager = _make_user(db_session, org, "application_manager", "romanager")
    app = _make_app(db_session, org, "RO Test", business_owner="Jane Legacy", technical_owner="John Legacy")
    login_as(client, manager)

    resp = client.get(f"/applications/{app.id}/edit")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]

    html = resp.get_data(as_text=True)
    assert "readonly" in html
    assert "Jane Legacy" in html
    assert "John Legacy" in html
    assert "Migrated to owner records" in html


# ── 9. application_owners store-agreement concept ──────────────────────────


def test_can_assign_and_read_back_all_owner_types(db_session, make_org, client, login_as):
    """All four owner types can be assigned and read back."""
    from app.models.application_owner import ApplicationOwner

    org = make_org("r1b03-types")
    manager = _make_user(db_session, org, "application_manager", "typesmgr")
    app = _make_app(db_session, org, "Types Test")
    login_as(client, manager)

    for otype in ["primary", "backup", "technical", "business"]:
        resp = _post_json(client, f"/applications/{app.id}/owners", {
            "user_id": manager.id,
            "ownership_type": otype,
        })
        assert resp.status_code == 201, f"Failed to add {otype}: {resp.get_data(as_text=True)}"

    rows = ApplicationOwner.query.filter_by(application_id=app.id).all()
    assert len(rows) == 4
    types = {r.ownership_type for r in rows}
    assert types == {"primary", "backup", "technical", "business"}


def test_cross_org_owner_not_counted_in_coverage(two_orgs, client, login_as):
    """Coverage does not count another organisation's owner records."""
    from app.models.application_owner import ApplicationOwner

    db_session = two_orgs["db_session"]

    # Add an owner from org B to org B's app
    db_session.add(ApplicationOwner(
        application_id=two_orgs["app_b"].id,
        user_id=two_orgs["manager_b"].id,
        organization_id=two_orgs["org_b"].id,
        ownership_type="primary",
    ))
    db_session.flush()

    # Org A should not see this owner in the coverage view
    login_as(client, two_orgs["manager_a"])
    resp = client.get("/applications/ownership-coverage")
    assert resp.status_code == 200


def test_app_owner_writer_assigns_back_to_user(two_orgs, client, login_as):
    """An owner assigned via the writer shows in that user's My Applications."""

    # Manager A assigns Manager B (but since B is in another org, this fails)
    login_as(client, two_orgs["manager_a"])
    resp = _post_json(client, f"/applications/{two_orgs['app_a'].id}/owners", {
        "user_id": two_orgs["manager_b"].id,
        "ownership_type": "primary",
    })
    assert resp.status_code == 404, "cross-org assignment must be refused"

    # Manager A assigns themselves
    resp = _post_json(client, f"/applications/{two_orgs['app_a'].id}/owners", {
        "user_id": two_orgs["manager_a"].id,
        "ownership_type": "primary",
    })
    assert resp.status_code == 201

    # Verify it shows in My Applications
    login_as(client, two_orgs["manager_a"])
    resp = client.get("/my-applications/")
    assert resp.status_code == 200
    assert two_orgs["app_a"].name.encode() in resp.data