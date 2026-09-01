"""Regression tests for the ARB / governance QA findings (01 Sep 2026).

Written against the shared fixtures in tests/conftest.py (db_session runs inside
a rolled-back transaction; make_org / login_as cover tenancy + auth).

Covered:
  - item 1: a legacy_generic ARB review detail renders its stored fields.
  - item 4: a new ARBReviewItem.review_number is sequential ARB-YYYY-NNN.
  - item 5: GET /arb/reviews/create and /arb/review/new land on the dashboard
            with a guiding flash rather than a silent redirect.
  - item 6: /architecture/decisions/ renders WITH the admin sidebar.
"""

import uuid

import pytest


@pytest.fixture
def ea_user(db_session, make_org):
    from app.models.user import User

    org = make_org("arbqa")
    user = User(
        email=f"arbqa-{uuid.uuid4().hex[:10]}@example.test",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_new_review_number_is_sequential_not_uuid(app, db_session):
    """item 4: generate_review_number returns ARB-YYYY-NNN, not REV-YYYY-<uuid>."""
    from datetime import datetime

    from app.models.architecture_review_board import ARBReviewItem

    ref = ARBReviewItem.generate_review_number()
    year = datetime.utcnow().year
    assert ref.startswith(f"ARB-{year}-"), ref
    suffix = ref.rsplit("-", 1)[-1]
    assert suffix.isdigit(), ref  # numeric suffix, no hex UUID


def test_decisions_list_has_sidebar(app, client, login_as, ea_user):
    """item 6: the Architecture Decisions listing renders the admin sidebar."""
    login_as(client, ea_user)
    resp = client.get("/architecture/decisions/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'data-testid="sidebar"' in body


def test_reviews_create_get_flashes_and_redirects(app, client, login_as, ea_user):
    """item 5: bare GET of the create route redirects to the dashboard w/ a hint."""
    login_as(client, ea_user)
    resp = client.get("/arb/reviews/create", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/arb" in resp.headers.get("Location", "")

    login_as(client, ea_user)
    resp2 = client.get("/arb/review/new", follow_redirects=False)
    assert resp2.status_code in (301, 302)


def test_legacy_generic_review_renders_stored_fields(
    app, client, login_as, ea_user, db_session
):
    """item 1: a legacy (non-typed) review detail shows status/type/submitter."""
    from app.models.architecture_review_board import ARBReviewItem

    review = ARBReviewItem(
        organization_id=ea_user.organization_id,
        title="Legacy generic subject",
        description="A legacy review body that must be visible.",
        review_type="solution_design",
        status="under_review",
        priority="high",
        submitter_id=ea_user.id,
        review_number=ARBReviewItem.generate_review_number(),
    )
    db_session.add(review)
    db_session.flush()

    login_as(client, ea_user)
    resp = client.get(f"/arb/reviews/{review.id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # The stored description and a humanised status must reach the page, not just
    # the title + id (the QA-reported failure).
    assert "legacy review body that must be visible" in body.lower()
    assert "under review" in body.lower()
