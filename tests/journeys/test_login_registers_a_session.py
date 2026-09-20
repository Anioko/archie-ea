"""A journey login must leave a live server-side session behind.

Every authenticated request checks a server-side session record keyed by the
``_sid`` in the signed cookie, and rejects the request as revoked when the
record is missing. Journey tests build their data inside
``with app.app_context():`` blocks, let those blocks close, and only then call
``login(client, user_id)``. No ambient app context is open at that point, so a
login helper that relies on one mints nothing and every later request in the
test is bounced with 401 (JSON clients) or a redirect to the login page (HTML
clients). These tests pin that condition and the behaviour that must hold in it.
"""

import pytest

from .conftest import cleanup, login, make_org, make_user

pytestmark = pytest.mark.journey


def test_login_outside_an_app_context_registers_a_live_session(app, client):
    """The login registers a session row and the next request is accepted."""
    from flask import has_app_context

    from app import db
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.user_session import UserSession

    with app.app_context():
        org_id = make_org(db, "SessionReg")
        user_id = make_user(
            db, org_id, "sessionreg", enterprise_role="enterprise_architect",
            role_name="Architect",
        )

    # The condition under which journey tests log in: nothing supplies a context.
    assert not has_app_context()

    try:
        login(client, user_id)

        with client.session_transaction() as sess:
            sid = sess.get("_sid")
        assert sid, "login left no _sid in the session"

        with app.app_context():
            row = db.session.get(UserSession, sid)
            assert row is not None, "no user_sessions row exists for the login"
            assert row.user_id == user_id
            assert row.revoked_at is None

        response = client.get("/risks/")
        assert response.status_code == 200
        assert "timeout=revoked" not in (response.headers.get("Location") or "")

        with client.session_transaction() as sess:
            assert sess.get("_user_id") == str(user_id)
            assert sess.get("_sid") == sid
    finally:
        with app.app_context():
            cleanup(db, User, [user_id])
            cleanup(db, Organization, [org_id])


def test_minting_a_session_with_no_context_and_no_app_is_an_error(app):
    """An unregistered session must never be produced silently."""
    from flask import has_app_context

    from tests._session_test_helpers import mint_test_sid

    assert not has_app_context()

    with pytest.raises(RuntimeError, match="no app context"):
        mint_test_sid(1)
