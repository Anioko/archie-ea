"""Journey: can the platform_admin persona actually change enterprise roles?

Until now platform_admin had no journey test proving the persona can do its job.
The admin routes for user role management exist, but without a journey we cannot
know whether they work end‑to‑end, persist changes correctly, and respect tenant
isolation. A static reading of the code cannot tell you whether a platform_admin
can successfully assign a new enterprise role to another user and see that change
reflected where they would look next.

This test follows the Level 9 standard from docs/TESTING_STANDARD.md:
  1. Do the work (POST to update a user's enterprise role)
  2. Confirm it PERSISTED (re‑query the database)
  3. Confirm it is VISIBLE (follow the redirect and check the rendered HTML)

A second test ensures tenant isolation: a platform_admin in org A must not be
able to change the role of a user in org B. The handler filters by organization_id
and calls first_or_404, so a cross‑org attempt should yield 404 and leave the
target user's enterprise_role unchanged.
"""

import uuid

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey


def test_platform_admin_can_change_another_users_enterprise_role(app, client):
    """Platform admin changes a user's enterprise role and sees the change."""
    from app import db
    from app.models.user import User

    with app.app_context():
        org_id = make_org(db, "Admin")
        admin_id = make_user(
            db, org_id, "admin", enterprise_role="platform_admin"
        )
        subject_id = make_user(
            db, org_id, "subject", enterprise_role="business_architect"
        )

    login(client, admin_id)

    # Use url_for inside an app context
    with app.app_context():
        from flask import url_for
        update_url = url_for('user_role.update_user_role', user_id=subject_id)

    response = client.post(
        update_url,
        data={"enterprise_role": "solution_architect"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    # ASSERT PERSISTENCE: re‑query the subject User from the database
    with app.app_context():
        # Explicit query, not User.query.get(): per CLAUDE.md, .get() returns the
        # identity-map object without emitting SQL on a hit, so it can report the
        # value this process already had rather than the value the database holds.
        db.session.expunge_all()
        subject = db.session.execute(
            db.select(User).filter_by(id=subject_id)
        ).scalar_one()
        assert subject.enterprise_role == "solution_architect"

    # ASSERT VISIBILITY: the new role appears in the rendered HTML
    # The handler redirects to admin.user_info, which we already followed.
    # Check that the page contains a success message or the role text.
    assert b"solution_architect" in response.data


def test_platform_admin_cannot_change_role_of_user_in_another_org(app, client):
    """Tenant isolation: platform_admin in org A cannot affect a user in org B."""
    from app import db
    from app.models.user import User

    with app.app_context():
        org_a_id = make_org(db, "OrgA")
        org_b_id = make_org(db, "OrgB")

        admin_id = make_user(
            db, org_a_id, "adminA", enterprise_role="platform_admin"
        )
        subject_id = make_user(
            db, org_b_id, "subjectB", enterprise_role="business_architect"
        )

    login(client, admin_id)

    with app.app_context():
        from flask import url_for
        update_url = url_for('user_role.update_user_role', user_id=subject_id)

    response = client.post(
        update_url,
        data={"enterprise_role": "solution_architect"},
        follow_redirects=False,
    )
    # The handler filters by organization_id and calls first_or_404,
    # so a cross‑org request should yield 404.
    assert response.status_code == 404

    # ASSERT PERSISTENCE: the other org's user still has its original role
    with app.app_context():
        # This assertion is the whole point of the test, so it must read the
        # DATABASE. User.query.get() would serve the pre-request cached object and
        # report the original role even if the cross-org write had succeeded --
        # a false pass on exactly the leak being tested for.
        db.session.expunge_all()
        subject = db.session.execute(
            db.select(User).filter_by(id=subject_id)
        ).scalar_one()
        assert subject.enterprise_role == "business_architect"
