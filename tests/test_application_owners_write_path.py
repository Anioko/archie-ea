"""application_owners' first production write path: the Owners section on the
application record adds and removes a person per role, through the existing
organisation-scoped user list and a recorded primary-owner/admin permission
rule, with the model behind the standard tenant fence.

Users are built inline as in tests/test_arb_ea_tenant_isolation.py:24-37
(plain ``User(...)`` + ``db_session.add``/``flush``), with one addition: a
few routes exercised here (``application_edit``) are gated by
``require_roles("admin", "architect")``, a different check from this
feature's own ``is_org_admin`` / primary-owner rule, so every user here also
carries the "Administrator" RBAC role -- the same construction
tests/test_admin_org_member_idor.py:92-118 uses for the same reason. Setting
it universally does not weaken the ``is_org_admin`` / primary-owner
assertions below: they exercise a second, independent permission check this
task adds, not the RBAC role.
"""

from __future__ import annotations

import uuid

import pytest
from flask import g, render_template
from flask_login import login_user

pytestmark = pytest.mark.usefixtures("db_session")


def _make_user(db_session, org, *, is_org_admin=False, label="user"):
    from app.models.user import Role, User

    admin_role = Role.query.filter_by(name="Administrator").first()
    if admin_role is None:
        Role.insert_roles()
        admin_role = Role.query.filter_by(name="Administrator").first()

    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"owners-{label}-{suffix}@example.com",
        first_name="Owners",
        last_name=label,
        organization_id=org.id,
        role=admin_role,
        is_org_admin=is_org_admin,
        confirmed=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_app(db_session, org, name="Owners Target", **extra):
    from app.models.application_portfolio import ApplicationComponent

    row = ApplicationComponent(
        name=f"{name} {uuid.uuid4().hex[:6]}",
        organization_id=org.id,
        **extra,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _make_owner_row(db_session, app_row, user, ownership_type, **extra):
    from app.models.application_owner import ApplicationOwner

    row = ApplicationOwner(
        application_id=app_row.id,
        user_id=user.id,
        organization_id=app_row.organization_id,
        ownership_type=ownership_type,
        **extra,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _render_owners_section(app, app_row, viewer):
    """Render the Owners partial as ``viewer`` would see it.

    Decision C's per-role list, "Recorded as text" line and confirm control
    are all rendered server-side (not by client JS), which is what makes
    them directly assertable here without a browser.
    """
    with app.test_request_context("/"):
        login_user(viewer)
        g.current_org_id = viewer.organization_id
        return render_template(
            "application_mgmt/partials/_owners_section.html", app=app_row
        )


# ─────────────────────────────────────────────────────── decision A: the model


def test_model_is_tenant_mixin_with_no_explicit_org_column():
    from app.models.application_owner import ApplicationOwner
    from app.models.mixins import TenantMixin

    assert issubclass(ApplicationOwner, TenantMixin)
    # The mixin's declared_attr organization_id must be the only source of
    # the column -- no shadowing explicit db.Column left behind.
    assert "organization_id" in ApplicationOwner.__table__.columns


# ───────────────────────────────────────────────────── decision B: add owner


def test_add_owner_by_admin(db_session, make_org, client, login_as):
    from app.models.application_owner import ApplicationOwner

    org = make_org("add-admin")
    admin = _make_user(db_session, org, is_org_admin=True, label="admin")
    target = _make_user(db_session, org, label="target")
    app_row = _make_app(db_session, org)
    db_session.commit()

    login_as(client, admin)
    resp = client.post(
        f"/applications/{app_row.id}/owners",
        data={"user_id": target.id, "ownership_type": "technical"},
    )
    assert resp.status_code == 302

    db_session.expire_all()
    row = ApplicationOwner.query.filter_by(
        application_id=app_row.id, ownership_type="technical"
    ).first()
    assert row is not None
    assert row.user_id == target.id
    assert row.assigned_by == admin.id


def test_add_owner_by_primary_owner(db_session, make_org, client, login_as):
    from app.models.application_owner import ApplicationOwner

    org = make_org("add-primary")
    primary = _make_user(db_session, org, label="primary")
    target = _make_user(db_session, org, label="target2")
    app_row = _make_app(db_session, org)
    _make_owner_row(db_session, app_row, primary, "primary", assigned_by=primary.id)
    db_session.commit()

    login_as(client, primary)
    resp = client.post(
        f"/applications/{app_row.id}/owners",
        data={"user_id": target.id, "ownership_type": "backup"},
    )
    assert resp.status_code == 302

    db_session.expire_all()
    row = ApplicationOwner.query.filter_by(
        application_id=app_row.id, ownership_type="backup"
    ).first()
    assert row is not None
    assert row.user_id == target.id


def test_add_owner_refused_for_ordinary_user(db_session, make_org, client, login_as):
    from app.models.application_owner import ApplicationOwner

    org = make_org("add-refused")
    ordinary = _make_user(db_session, org, label="ordinary")
    target = _make_user(db_session, org, label="target3")
    app_row = _make_app(db_session, org)
    db_session.commit()

    login_as(client, ordinary)
    resp = client.post(
        f"/applications/{app_row.id}/owners",
        data={"user_id": target.id, "ownership_type": "technical"},
    )
    assert resp.status_code == 403

    db_session.expire_all()
    assert ApplicationOwner.query.filter_by(application_id=app_row.id).first() is None


def test_add_owner_from_another_org_is_404_no_row(db_session, make_org, client, login_as):
    from app.models.application_owner import ApplicationOwner

    org_a = make_org("add-cross-a")
    org_b = make_org("add-cross-b")
    admin_a = _make_user(db_session, org_a, is_org_admin=True, label="admin-a")
    outsider = _make_user(db_session, org_b, label="outsider")
    app_row = _make_app(db_session, org_a)
    db_session.commit()

    login_as(client, admin_a)
    resp = client.post(
        f"/applications/{app_row.id}/owners",
        data={"user_id": outsider.id, "ownership_type": "technical"},
    )
    assert resp.status_code == 404

    db_session.expire_all()
    assert ApplicationOwner.query.filter_by(application_id=app_row.id).first() is None


def test_add_owner_duplicate_is_a_flash_not_a_500(db_session, make_org, client, login_as):
    from app.models.application_owner import ApplicationOwner

    org = make_org("add-dup")
    admin = _make_user(db_session, org, is_org_admin=True, label="admin-dup")
    target = _make_user(db_session, org, label="target-dup")
    app_row = _make_app(db_session, org)
    _make_owner_row(db_session, app_row, target, "technical", assigned_by=admin.id)
    db_session.commit()

    login_as(client, admin)
    resp = client.post(
        f"/applications/{app_row.id}/owners",
        data={"user_id": target.id, "ownership_type": "technical"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"already recorded" in resp.data

    db_session.expire_all()
    rows = ApplicationOwner.query.filter_by(
        application_id=app_row.id, ownership_type="technical"
    ).all()
    assert len(rows) == 1


def test_add_owner_without_explicit_org_id_carries_acting_org(db_session, make_org, client, login_as):
    """The add route never sets organization_id itself (fact/decision B) --
    TenantMixin's before_flush listener must stamp it from the request."""
    from app.models.application_owner import ApplicationOwner

    org = make_org("stamp")
    admin = _make_user(db_session, org, is_org_admin=True, label="stamp-admin")
    target = _make_user(db_session, org, label="stamp-target")
    app_row = _make_app(db_session, org)
    db_session.commit()

    login_as(client, admin)
    resp = client.post(
        f"/applications/{app_row.id}/owners",
        data={"user_id": target.id, "ownership_type": "backup"},
    )
    assert resp.status_code == 302

    db_session.expire_all()
    row = ApplicationOwner.query.filter_by(
        application_id=app_row.id, ownership_type="backup"
    ).first()
    assert row is not None
    assert row.organization_id == org.id


# ────────────────────────────────────────────────── decision B: remove owner


def test_remove_owner(db_session, make_org, client, login_as):
    from app.models.application_owner import ApplicationOwner

    org = make_org("remove")
    admin = _make_user(db_session, org, is_org_admin=True, label="remove-admin")
    target = _make_user(db_session, org, label="remove-target")
    app_row = _make_app(db_session, org)
    owner_row = _make_owner_row(db_session, app_row, target, "technical", assigned_by=admin.id)
    owner_id = owner_row.id
    db_session.commit()

    login_as(client, admin)
    resp = client.post(f"/applications/{app_row.id}/owners/{owner_id}/remove")
    assert resp.status_code == 302

    db_session.expire_all()
    assert db_session.get(ApplicationOwner, owner_id) is None


def test_remove_owner_refused_for_ordinary_user(db_session, make_org, client, login_as):
    from app.models.application_owner import ApplicationOwner

    org = make_org("remove-refused")
    ordinary = _make_user(db_session, org, label="remove-ordinary")
    target = _make_user(db_session, org, label="remove-target2")
    app_row = _make_app(db_session, org)
    owner_row = _make_owner_row(db_session, app_row, target, "technical")
    owner_id = owner_row.id
    db_session.commit()

    login_as(client, ordinary)
    resp = client.post(f"/applications/{app_row.id}/owners/{owner_id}/remove")
    assert resp.status_code == 403

    db_session.expire_all()
    assert db_session.get(ApplicationOwner, owner_id) is not None


def test_remove_owner_cross_tenant_row_is_404(db_session, make_org, client, login_as):
    from app.models.application_owner import ApplicationOwner

    org_a = make_org("remove-cross-a")
    org_b = make_org("remove-cross-b")
    admin_a = _make_user(db_session, org_a, is_org_admin=True, label="remove-admin-a")
    user_b = _make_user(db_session, org_b, label="remove-user-b")
    app_a = _make_app(db_session, org_a)
    app_b = _make_app(db_session, org_b)
    owner_row_b = _make_owner_row(db_session, app_b, user_b, "technical")
    owner_id_b = owner_row_b.id
    db_session.commit()

    login_as(client, admin_a)
    resp = client.post(f"/applications/{app_a.id}/owners/{owner_id_b}/remove")
    assert resp.status_code == 404

    db_session.expire_all()
    assert db_session.get(ApplicationOwner, owner_id_b) is not None


# ───────────────────────────────────────── the tenant fence, positive control


def test_cross_tenant_select_returns_only_tenant_rows(db_session, make_org, tenant_ctx):
    from app.models.application_owner import ApplicationOwner

    org_a = make_org("select-a")
    org_b = make_org("select-b")
    user_a = _make_user(db_session, org_a, label="select-user-a")
    user_b = _make_user(db_session, org_b, label="select-user-b")
    app_a = _make_app(db_session, org_a)
    app_b = _make_app(db_session, org_b)
    row_a = _make_owner_row(db_session, app_a, user_a, "primary")
    row_b = _make_owner_row(db_session, app_b, user_b, "primary")
    db_session.commit()

    with tenant_ctx(org_a.id):
        visible = ApplicationOwner.query.all()
        visible_ids = {row.id for row in visible}

    assert row_a.id in visible_ids, "org A's own ownership row must be visible in its own context"
    assert row_b.id not in visible_ids, (
        "TENANT LEAK: org A's request returned org B's ApplicationOwner row"
    )
    assert all(row.organization_id == org_a.id for row in visible)


# ──────────────────────────────────────────────────── decision D: edit form


def test_edit_form_person_chosen_writes_row_leaves_text_untouched(db_session, make_org, client, login_as):
    from app.models.application_owner import ApplicationOwner

    org = make_org("edit-form")
    editor = _make_user(db_session, org, is_org_admin=True, label="edit-admin")
    target = _make_user(db_session, org, label="edit-target")
    app_row = _make_app(db_session, org, business_owner="Old Text Owner")
    db_session.commit()

    login_as(client, editor)
    resp = client.post(
        f"/applications/{app_row.id}/edit",
        data={
            "name": app_row.name,
            "business_owner_user_id": str(target.id),
        },
    )
    assert resp.status_code == 302, resp.get_data(as_text=True)

    db_session.expire_all()
    row = ApplicationOwner.query.filter_by(
        application_id=app_row.id, ownership_type="business"
    ).first()
    assert row is not None
    assert row.user_id == target.id
    assert app_row.business_owner == "Old Text Owner", (
        "the text column must never be written by this form"
    )


# ───────────────────────────────────────────── decision C: text-owner confirm


def test_text_owner_unique_match_renders_confirm_and_confirm_writes_row(
    db_session, make_org, client, login_as, app
):
    from app.models.application_owner import ApplicationOwner

    org = make_org("text-match")
    admin = _make_user(db_session, org, is_org_admin=True, label="text-admin")
    match_user = _make_user(db_session, org, label="text-match-user")
    match_user.first_name, match_user.last_name = "Jane", "Smith"
    app_row = _make_app(db_session, org, business_owner="Jane Smith")
    db_session.commit()

    html = _render_owners_section(app, app_row, admin)
    assert "Recorded as text: Jane Smith" in html
    assert "Confirm Jane Smith as Business Owner" in html

    login_as(client, admin)
    resp = client.post(
        f"/applications/{app_row.id}/owners",
        data={"user_id": match_user.id, "ownership_type": "business"},
    )
    assert resp.status_code == 302

    db_session.expire_all()
    row = ApplicationOwner.query.filter_by(
        application_id=app_row.id, ownership_type="business"
    ).first()
    assert row is not None
    assert row.user_id == match_user.id
    assert app_row.business_owner == "Jane Smith"


def test_rendering_the_section_never_writes_a_row(db_session, make_org, app):
    """Decision E: the match is a suggestion computed at render time. Viewing
    the page must never itself create an ApplicationOwner row (no automatic
    backfill anywhere)."""
    from app.models.application_owner import ApplicationOwner

    org = make_org("no-backfill")
    admin = _make_user(db_session, org, is_org_admin=True, label="no-backfill-admin")
    match_user = _make_user(db_session, org, label="no-backfill-match")
    match_user.first_name, match_user.last_name = "Sam", "Rivera"
    app_row = _make_app(db_session, org, business_owner="Sam Rivera")
    db_session.commit()

    before = ApplicationOwner.query.filter_by(application_id=app_row.id).count()
    html = _render_owners_section(app, app_row, admin)
    assert "Confirm Sam Rivera as Business Owner" in html

    db_session.expire_all()
    after = ApplicationOwner.query.filter_by(application_id=app_row.id).count()
    assert after == before == 0


# ───────────────────────────────────────────────── decision fact 9: deletion


def test_deleting_user_removes_row_and_section_shows_not_recorded(db_session, make_org, app):
    from app.models.application_owner import ApplicationOwner
    from app.models.user import User

    org = make_org("delete-user")
    admin = _make_user(db_session, org, is_org_admin=True, label="delete-admin")
    target = _make_user(db_session, org, label="delete-target")
    app_row = _make_app(db_session, org)
    owner_row = _make_owner_row(db_session, app_row, target, "technical", assigned_by=admin.id)
    owner_id = owner_row.id
    admin_id = admin.id
    target_id = target.id
    app_row_id = app_row.id
    db_session.commit()

    # Matches how admin_user_service.delete_user actually runs in production:
    # the user is the only object this session has loaded when it is
    # deleted, so nothing here asks the ORM to manage the ApplicationOwner
    # relationship -- the FK's ondelete=CASCADE does the work, entirely in
    # the database, exactly as fact 9 describes. (With the ownership row
    # already identity-mapped in the same session, as it is a few lines
    # above, SQLAlchemy instead tries to null out application_owners.user_id
    # before the delete, which the NOT NULL constraint correctly rejects --
    # a pre-existing session-shape hazard this task's model change did not
    # introduce and does not touch; noted in the build report.)
    db_session.expunge_all()
    fresh_target = db_session.get(User, target_id)
    db_session.delete(fresh_target)
    db_session.commit()

    db_session.expire_all()
    assert db_session.get(ApplicationOwner, owner_id) is None, (
        "the FK's ondelete=CASCADE must remove the ownership row with the user"
    )

    from app.models.application_portfolio import ApplicationComponent

    fresh_app_row = db_session.get(ApplicationComponent, app_row_id)
    fresh_admin = db_session.get(User, admin_id)
    html = _render_owners_section(app, fresh_app_row, fresh_admin)
    assert "Not recorded" in html


# ────────────────────────────────────────── existing reader: portfolio banner


def test_has_assigned_owner_counts_the_new_row(db_session, make_org):
    from app.models.application_portfolio import ApplicationComponent
    from app.modules.my_applications.services import has_assigned_owner

    org = make_org("banner")
    admin = _make_user(db_session, org, is_org_admin=True, label="banner-admin")
    target = _make_user(db_session, org, label="banner-target")
    unowned = _make_app(db_session, org, name="Unowned App")
    owned = _make_app(db_session, org, name="Owned App")
    _make_owner_row(db_session, owned, target, "technical", assigned_by=admin.id)
    db_session.commit()

    count = (
        ApplicationComponent.query.filter(
            ApplicationComponent.id.in_([unowned.id, owned.id])
        )
        .filter(has_assigned_owner(org.id))
        .count()
    )
    assert count == 1
