"""E2E-H (typed-cycle half): a decision created through the real, working
Decision Register (/architecture/decisions/new) must be submittable through
the typed ARB governance loop end to end.

Confirmed live 7 Sep 2026: this previously failed at the very first step --
TypedARBSubmissionService.submit(subject_type="adr", ...) resolved subject_id
against ArchitectureDecisionRecord (0 rows in production), and 12 separate
database-level foreign key constraints across the whole typed-ARB subsystem
(arb_subject_evidence_snapshots, arb_review_cycles, arb_review_items,
arb_submission_events, arb_decision_events, arb_condition_evidence_records)
pointed at that same dead table, so no row created via the real Decision
Register could ever be referenced by an ARB governance object. Both halves
are fixed together here: the adapter now resolves ArchitectureDecision, and
ensure_arb_cycle_constraints (app/models/architecture_review_board.py) self-
heals the FK targets, including dropping the stale ORM-auto-named
constraints create_all() left behind pointing at the old table.
"""
import uuid

import pytest


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


def test_a_decision_from_the_real_register_can_be_submitted_to_typed_arb(app, client):
    from app import db
    from app.models.architecture_decision import ArchitectureDecision
    from app.models.architecture_review_board import (
        ARBReviewItem,
        ensure_arb_cycle_constraints,
    )
    from app.models.organization import Organization
    from app.models.user import User
    from app.modules.transformation_room.arb_submission_service import (
        TypedARBSubmissionService,
    )
    from app.modules.transformation_room.domain import ActorContext
    from tests.test_ba_tenant_and_authz import _cleanup_ids, _make_org_id, _make_user_id

    with app.app_context():
        ensure_arb_cycle_constraints(db.session.connection())
        db.session.commit()

        org = _make_org_id(db, "TypedAdrLive")
        submitter_id = _make_user_id(db, org, "TypedAdrSubmit", enterprise_role="enterprise_architect")

        # This is exactly what /architecture/decisions/new
        # (arch_decisions.create_decision) writes -- the real Decision
        # Register a user actually reaches, not a test-only fixture shape.
        suffix = uuid.uuid4().hex[:8]
        decision = ArchitectureDecision(
            organization_id=org,
            decision_id=f"AD-{suffix}",
            title=f"Adopt managed Postgres {suffix}",
            status="proposed",
            context="Operational overhead of self-hosting is unsustainable.",
            decision="Adopt a managed Postgres offering.",
            rationale="Reduces on-call burden and patching risk.",
            consequences="Slightly higher monthly cost.",
            created_by_id=submitter_id,
        )
        db.session.add(decision)
        db.session.commit()
        decision_id = decision.id

        submission = TypedARBSubmissionService.submit(
            actor=ActorContext(submitter_id, org, frozenset(), f"typed-adr-live-{suffix}"),
            command_key=f"typed-adr-live-{suffix}",
            subject_type="adr",
            subject_id=decision_id,
            assertions={"human_reviewed": True},
        )
        review_item_id = submission.object_ids["review_item_id"]

        db.session.expunge_all()
        review = db.session.get(ARBReviewItem, review_item_id)
        assert review is not None
        assert review.adr_id == decision_id
        assert review.subject_type == "adr"

    try:
        pass
    finally:
        with app.app_context():
            _cleanup_ids(db, ARBReviewItem, [review_item_id])
            _cleanup_ids(db, ArchitectureDecision, [decision_id])
            _cleanup_ids(db, User, [submitter_id])
            _cleanup_ids(db, Organization, [org])
