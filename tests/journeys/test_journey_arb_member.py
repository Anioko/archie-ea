"""Journey: can the arb_member persona decide a review?

Level 9, docs/TESTING_STANDARD.md. The persona exists to govern: take a
submitted review item and record an approve/reject decision that sticks and is
visible on the review afterwards.

Two invariants ride along, because both are enforced in application code rather
than by the schema and would therefore fail silently if they regressed:

* separation of duties -- the submitter of a review may not decide it
  (ARBGovernanceService raises SelfApprovalError);
* tenancy -- an ARB member in one organisation may not decide another
  organisation's review.
"""

import uuid
from datetime import datetime

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey


def _review(db, org_id, submitter_id, title):
    """A submitted, undecided review item awaiting an ARB decision."""
    from app.models.architecture_review_board import ARBReviewItem

    item = ARBReviewItem(
        organization_id=org_id,
        review_number="REV-JRN-%s" % uuid.uuid4().hex[:10].upper(),
        title=title,
        description="Raised by the arb_member journey test.",
        review_type="solution_design",
        status="submitted",
        submitter_id=submitter_id,
        submitted_at=datetime.utcnow(),
    )
    db.session.add(item)
    db.session.commit()
    return item.id


def test_arb_member_records_a_decision_and_it_sticks(app, client):
    """The persona's core write: a decision that persists and is visible."""
    from app import db
    from app.models.architecture_review_board import ARBReviewItem

    with app.app_context():
        org_id = make_org(db, "ARB")
        submitter_id = make_user(db, org_id, "sub", enterprise_role="solution_architect",
                                 role_name="Architect")
        member_id = make_user(db, org_id, "arb", enterprise_role="arb_member",
                              role_name="Architect")
        title = "Journey Review %s" % uuid.uuid4().hex[:8]
        review_id = _review(db, org_id, submitter_id, title)

    login(client, member_id)
    response = client.post(
        "/arb/reviews/%d/decision" % review_id,
        data={
            "decision": "approved_with_conditions",
            "rationale": "Approved subject to the conditions below.",
            "conditions": "Publish the data-retention note before go-live.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200, response.status_code

    # PERSISTED -- read the database, not the identity map.
    with app.app_context():
        db.session.expunge_all()
        item = db.session.execute(
            db.select(ARBReviewItem).filter_by(id=review_id)
        ).scalar_one()
        assert item.decision == "approved_with_conditions"
        assert item.decided_by_id == member_id
        assert item.decision_date is not None
        # A decision with no rationale is an unauditable decision.
        assert item.decision_rationale

    # VISIBLE -- the decision shows on the review the member looks at next.
    page = client.get("/arb/reviews/%d" % review_id)
    assert page.status_code == 200, page.status_code
    body = page.get_data(as_text=True)
    # The outcome, the approver and the rationale must all be on the page. Any
    # one of them missing means the governance record is not readable where the
    # board looks -- which is how this page shipped: it rendered the decision
    # form until a decision existed and then showed nothing at all.
    assert "Approved With Conditions" in body
    assert "Publish the data-retention note before go-live." in body
    assert "Approved subject to the conditions below." in body


def test_the_submitter_of_a_review_cannot_decide_it(app, client):
    """Separation of duties is a server-side block, not a UI hint."""
    from app import db
    from app.models.architecture_review_board import ARBReviewItem

    with app.app_context():
        org_id = make_org(db, "ARBSoD")
        submitter_id = make_user(db, org_id, "selfsub", enterprise_role="arb_member",
                                 role_name="Architect")
        title = "Self Approval %s" % uuid.uuid4().hex[:8]
        review_id = _review(db, org_id, submitter_id, title)

    login(client, submitter_id)
    response = client.post(
        "/arb/reviews/%d/decision" % review_id,
        data={"decision": "approved", "rationale": "Looks fine to me."},
        follow_redirects=False,
    )
    assert response.status_code == 403, response.status_code

    with app.app_context():
        db.session.expunge_all()
        item = db.session.execute(
            db.select(ARBReviewItem).filter_by(id=review_id)
        ).scalar_one()
        assert item.decision is None
        assert item.decided_by_id is None


def test_an_arb_member_cannot_decide_another_orgs_review(app, client):
    """Governance does not cross tenants."""
    from app import db
    from app.models.architecture_review_board import ARBReviewItem

    with app.app_context():
        org_a = make_org(db, "ARBOrgA")
        org_b = make_org(db, "ARBOrgB")
        submitter_id = make_user(db, org_b, "subB", enterprise_role="solution_architect",
                                 role_name="Architect")
        member_a = make_user(db, org_a, "arbA", enterprise_role="arb_member",
                             role_name="Architect")
        title = "Foreign Review %s" % uuid.uuid4().hex[:8]
        review_id = _review(db, org_b, submitter_id, title)

    login(client, member_a)
    response = client.post(
        "/arb/reviews/%d/decision" % review_id,
        data={"decision": "approved", "rationale": "Not mine to approve."},
        follow_redirects=False,
    )
    assert response.status_code in (403, 404), response.status_code

    with app.app_context():
        db.session.expunge_all()
        item = db.session.execute(
            db.select(ARBReviewItem).filter_by(id=review_id)
        ).scalar_one()
        assert item.decision is None
