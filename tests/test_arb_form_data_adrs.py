"""E2E-H: ARB's "New Review" dropdown never listed a real ADR.

/arb/api/form-data's adrs list read ArchitectureDecisionRecord, a model
with 0 rows in production -- the real Decision Register a user reaches at
/architecture/decisions/new (arch_decisions.create_decision) writes
ArchitectureDecision instead. Same class of defect as the risk-rollup fix
this session (029f59a9): two models answering "what is an ADR", one live,
one dead, so a real, saved decision never appeared as a linkable option.

Confirmed live 7 Sep 2026: 0 ArchitectureDecisionRecord rows / 7
ArchitectureDecision rows in production before this fix -- nothing is
orphaned by switching the read side.

Deliberately not touched by this fix: arb_adapters.py's typed-cycle
subject resolution (TypedARBSubmissionAdapter, subject_type="adr") also
reads ArchitectureDecisionRecord, and its evidence-gate logic depends on
a review_status column that ArchitectureDecision does not have at all --
a real schema gap requiring a migration and lifecycle decision, not a
reference swap. See archie-arb-adr-two-systems-of-record.md.
"""
import pytest

from tests.test_ba_tenant_and_authz import _cleanup_ids, _login, _make_org_id, _make_user_id


@pytest.fixture(scope="module")
def app():
    from app import create_app, db

    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        db.create_all()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_a_real_saved_decision_appears_in_the_arb_new_review_dropdown(client, app):
    from app import db
    from app.models.architecture_decision import ArchitectureDecision
    from app.models.organization import Organization
    from app.models.user import User

    with app.app_context():
        org = _make_org_id(db, "ArbAdrDropdown")
        uid = _make_user_id(db, org, "ArbAdrUser", enterprise_role="arb_member")
        decision = ArchitectureDecision(
            title="Use managed Postgres over self-hosted",
            decision_id="AD-TEST-001",
            status="accepted",
            context="Operational overhead of self-hosting.",
            decision="Adopt managed Postgres.",
            organization_id=org,
        )
        db.session.add(decision)
        db.session.commit()
        decision_id = decision.id
    try:
        with app.app_context():
            _login(client, uid)
            resp = client.get("/arb/api/form-data")
            assert resp.status_code == 200
            payload = resp.get_json()
            adr_titles = [a["title"] for a in payload["adrs"]]
            assert "Use managed Postgres over self-hosted" in adr_titles, (
                "a real, saved decision did not appear in the ARB ADR "
                f"dropdown: {payload['adrs']}"
            )
            matched = next(a for a in payload["adrs"] if a["id"] == decision_id)
            assert matched["adr_number"] == "AD-TEST-001"
    finally:
        with app.app_context():
            _cleanup_ids(db, ArchitectureDecision, [decision_id])
            _cleanup_ids(db, User, [uid])
            _cleanup_ids(db, Organization, [org])
