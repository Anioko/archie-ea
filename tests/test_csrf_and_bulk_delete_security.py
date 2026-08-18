"""Coverage for findings A-04/ARCH-051/C-10 (CSRF exemption audit + bulk-delete
recoverability) and ARCH-071 (name-field tag stripping).

The shared `app` fixture in tests/conftest.py sets WTF_CSRF_ENABLED = False for
the whole session, since most tests are not about CSRF. The tests here flip it
back on for the duration of a single `with app.test_request_context()`-free
client call, then restore it, so they do not leak the override into other
tests in the same session.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_user(db_session, org_id, role_name="Administrator"):
    from app.models.user import Role, User

    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"csrf-{suffix}@example.com",
        first_name="Csrf",
        last_name="Tester",
        organization_id=org_id,
        confirmed=True,
        enterprise_role="architect",
    )
    db_session.add(user)
    db_session.flush()

    role = Role.query.filter(Role.name.in_((role_name, "Administrator", "Admin", "admin"))).first()
    if role is None:
        role = Role(name=role_name)
        db_session.add(role)
        db_session.flush()
    user.role = role
    db_session.commit()
    return user


class TestApiV1CsrfEnforced:
    """A-04/ARCH-051/C-10: api_v1 authenticates via the browser session
    (@login_required everywhere, no Bearer-token path), so it must not be
    blanket CSRF-exempt. A token-less POST must be rejected."""

    def test_create_application_without_csrf_token_is_rejected(self, app, db_session, make_org, login_as):
        org = make_org("csrf")
        user = _make_user(db_session, org.id)

        client = app.test_client()
        login_as(client, user)

        app.config["WTF_CSRF_ENABLED"] = True
        try:
            resp = client.post(
                "/api/v1/applications/",
                json={"name": "CSRF probe " + uuid.uuid4().hex[:6]},
            )
            # Flask-WTF's CSRFProtect raises a 400 CSRFError by default; the
            # app's handler returns 400 for JSON/AJAX requests (see
            # app/_bootstrap/extensions.py::handle_csrf_error). Either 400 or
            # 403 is an acceptable "rejected", but 200/201 is the regression
            # this test exists to catch.
            assert resp.status_code in (400, 403), resp.get_data(as_text=True)
        finally:
            app.config["WTF_CSRF_ENABLED"] = False


class TestBulkDeleteRecoverable:
    """A-04/ARCH-051/C-10: bulk-delete requires explicit confirmation and
    soft-deletes rather than destroying rows outright."""

    def _make_app_component(self, db_session, org_id, name):
        from app.models.application_portfolio import ApplicationComponent

        row = ApplicationComponent(name=name, organization_id=org_id)
        db_session.add(row)
        db_session.flush()
        return row

    def test_bulk_delete_without_confirm_is_rejected(self, app, db_session, make_org, login_as):
        org = make_org("bulkdel")
        user = _make_user(db_session, org.id)
        app_row = self._make_app_component(db_session, org.id, "BulkDel Target " + uuid.uuid4().hex[:6])

        client = app.test_client()
        login_as(client, user)

        resp = client.post(
            "/applications/bulk-delete",
            json={"ids": [app_row.id]},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["success"] is False

        from app.models.application_portfolio import ApplicationComponent
        refreshed = db_session.get(ApplicationComponent, app_row.id)
        assert refreshed is not None
        assert refreshed.deleted_at is None

    def test_bulk_delete_with_confirm_soft_deletes(self, app, db_session, make_org, login_as):
        org = make_org("bulkdel2")
        user = _make_user(db_session, org.id)
        app_row = self._make_app_component(db_session, org.id, "BulkDel Target2 " + uuid.uuid4().hex[:6])

        client = app.test_client()
        login_as(client, user)

        resp = client.post(
            "/applications/bulk-delete",
            json={"ids": [app_row.id], "confirm": True},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["success"] is True
        assert body["deleted_count"] == 1

        # The row still exists (recoverable) but is marked deleted.
        #
        # Read it with raw SQL, not the ORM: the unconditional soft-delete
        # filter in app/middleware/tenant_isolation.py — added to close this
        # commit's own KNOWN REGRESSION — hides deleted_at IS NOT NULL rows
        # from every ORM SELECT, which is the whole point. An ORM read here
        # therefore correctly returns None and proves nothing about
        # recoverability; only a filter-bypassing read does.
        from sqlalchemy import text

        row = db_session.execute(
            text(
                "SELECT deleted_at FROM application_components "
                "WHERE id = :id AND organization_id = :org"
            ),
            {"id": app_row.id, "org": org.id},
        ).first()
        assert row is not None, "row was hard-deleted, not soft-deleted"
        assert row[0] is not None, "deleted_at was not set"

        # And it is genuinely invisible to ordinary application reads.
        from app.models.application_portfolio import ApplicationComponent

        assert ApplicationComponent.query.filter_by(id=app_row.id).first() is None


class TestApplicationNameTagStripping:
    """ARCH-071: name fields reject/strip HTML tags at the validation layer,
    rather than relying solely on render-time encoding."""

    def test_validate_application_name_strips_tags(self):
        from app.utils.validators import validate_application_name

        is_valid, cleaned, error = validate_application_name(
            "QA-TEST <script>alert(1)</script>"
        )
        assert is_valid is True
        assert "<script>" not in cleaned
        assert "</script>" not in cleaned
        assert "QA-TEST" in cleaned
