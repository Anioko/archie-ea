"""PostgreSQL integration for the typed ARB condition lifecycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import uuid

import pytest


os.environ["TRANSFORMATION_COMMAND_CAPABILITY_SECRET"] = "74" * 32


@pytest.fixture
def db_session(app, _schema):
    """Committed setup visible to CommandService's independent sessions."""
    from app import db

    with app.app_context():
        db.session.remove()
        try:
            yield db.session
        finally:
            organization_ids = tuple(db.session.info.get("c3_cleanup_org_ids", ()))
            db.session.remove()
            if organization_ids:
                raw = db.engine.raw_connection()
                try:
                    with raw.cursor() as cursor:
                        cursor.execute("SHOW session_replication_role")
                        original_role = cursor.fetchone()[0]
                        cursor.execute("SET session_replication_role = replica")
                        try:
                            for table in (
                                "arb_condition_events", "arb_canonical_conditions",
                                "arb_condition_evidence_records", "arb_decision_events",
                                "arb_submission_events", "operation_results",
                                "command_materialisations", "command_idempotency_records",
                                "arb_review_items", "arb_review_cycles",
                                "arb_subject_evidence_snapshots",
                                "architecture_decision_records", "users",
                            ):
                                cursor.execute(
                                    f'DELETE FROM "{table}" WHERE organization_id = ANY(%s)',
                                    (list(organization_ids),),
                                )
                            cursor.execute(
                                "DELETE FROM organizations WHERE id = ANY(%s)",
                                (list(organization_ids),),
                            )
                        except Exception:
                            raw.rollback()
                            cursor.execute(
                                f"SET session_replication_role = {original_role}"
                            )
                            raw.commit()
                            raise
                        cursor.execute(
                            f"SET session_replication_role = {original_role}"
                        )
                        raw.commit()
                finally:
                    raw.close()


def test_submit_verify_and_projection_commit_under_real_guards(
    app, db_session, make_org, monkeypatch
):
    from app.models.arb_condition_event import ensure_arb_condition_event_guards
    from app.models.arb_condition_evidence import ensure_arb_condition_evidence_guards
    from app.models.arb_decision_event import (
        ARBCondition,
        ARBDecisionEvent,
        ensure_arb_decision_guards,
    )
    from app.models.adr import ArchitectureDecisionRecord
    from app.models.architecture_review_board import (
        ARBReviewCycle,
        ARBReviewItem,
        ensure_arb_cycle_constraints,
    )
    from app.models.transformation_db_guards import ensure_transformation_db_guards
    from app.models.user import User
    from app.modules.transformation_room.arb_condition_evidence_service import (
        TypedARBConditionEvidenceService,
    )
    from app.modules.transformation_room.arb_condition_lifecycle_service import (
        TypedARBConditionLifecycleService,
    )
    from app.modules.transformation_room.arb_decision_service import (
        TypedARBDecisionService,
    )
    from app.modules.transformation_room.arb_submission_service import (
        TypedARBSubmissionService,
    )
    from app.modules.transformation_room.command_service import CommandService
    from app.modules.transformation_room.domain import ActorContext

    monkeypatch.setenv(
        "TRANSFORMATION_COMMAND_CAPABILITY_SECRET",
        "74" * 32,
    )
    connection = db_session.connection()
    ensure_transformation_db_guards(
        connection, capability_secrets=("74" * 32,)
    )
    ensure_arb_cycle_constraints(connection)
    ensure_arb_decision_guards(connection)
    ensure_arb_condition_evidence_guards(connection)
    ensure_arb_condition_event_guards(connection)

    org = make_org("c3-lifecycle")
    db_session.info.setdefault("c3_cleanup_org_ids", set()).add(org.id)
    suffix = uuid.uuid4().hex[:10]
    submitter = User(
        organization_id=org.id, email=f"c3-submit-{suffix}@example.test",
        enterprise_role="enterprise_architect", confirmed=True,
    )
    verifier = User(
        organization_id=org.id, email=f"c3-verify-{suffix}@example.test",
        enterprise_role="enterprise_architect", confirmed=True,
    )
    db_session.add_all((submitter, verifier))
    db_session.flush()
    adr = ArchitectureDecisionRecord(
        organization_id=org.id, adr_number=int(suffix[:7], 16),
        title=f"C3 lifecycle {suffix}", status="proposed",
        context="A governed choice needs evidence.",
        decision="Adopt the governed option.", rationale="It is testable.",
        consequences="Conditions must be verified.", created_by=submitter.email,
    )
    db_session.add(adr)
    db_session.commit()
    submitter_actor = ActorContext(
        submitter.id, org.id, frozenset(), f"c3-submit-{suffix}"
    )
    verifier_actor = ActorContext(
        verifier.id, org.id, frozenset(), f"c3-verify-{suffix}"
    )
    submission = TypedARBSubmissionService.submit(
        actor=submitter_actor, command_key=f"submit-{suffix}",
        subject_type="adr", subject_id=adr.id,
        assertions={"human_reviewed": True},
    )
    decision = TypedARBDecisionService.decide(
        actor=verifier_actor, command_key=f"decision-{suffix}",
        cycle_id=submission.object_ids["review_cycle_id"],
        outcome="approved_with_conditions", rationale="Approved with proof.",
        conditions=[
            {"code": "C-1", "text": "Provide deployment proof."},
            {"code": "C-2", "text": "Time-bound operational control."},
        ],
    )
    condition_id = decision.object_ids["condition_ids"][0]
    waiver_condition_id = decision.object_ids["condition_ids"][1]
    now = datetime.now(timezone.utc)
    evidence = TypedARBConditionEvidenceService.capture(
        actor=submitter_actor, command_key=f"capture-{suffix}",
        condition_id=condition_id,
        evidence={
            "source_identity": f"cmdb:{suffix}", "source_type": "cmdb",
            "source_version": "1", "source_checksum": "a" * 64,
            "value_json": {"verified": True},
            "observed_at": (now - timedelta(minutes=1)).isoformat(),
            "freshness_rule_version": "arb-condition-v1",
            "freshness_expires_at": (now + timedelta(days=1)).isoformat(),
        },
    )
    submitted = TypedARBConditionLifecycleService.submit_evidence(
        actor=submitter_actor, command_key=f"evidence-submit-{suffix}",
        condition_id=condition_id,
        condition_evidence_id=evidence.object_ids["condition_evidence_id"],
    )
    db_session.expire_all()
    cycle = db_session.get(ARBReviewCycle, submission.object_ids["review_cycle_id"])
    review = db_session.get(ARBReviewItem, submission.object_ids["review_item_id"])
    assert submitted.response["projection_status"] == "approved_with_conditions"
    assert cycle.status == review.status == "approved_with_conditions"
    assert cycle.terminal_outcome == review.decision == "approved_with_conditions"

    verified = TypedARBConditionLifecycleService.verify(
        actor=verifier_actor, command_key=f"verify-{suffix}",
        condition_id=condition_id,
        condition_evidence_id=evidence.object_ids["condition_evidence_id"],
    )
    replay = TypedARBConditionLifecycleService.verify(
        actor=verifier_actor, command_key=f"verify-{suffix}",
        condition_id=condition_id,
        condition_evidence_id=evidence.object_ids["condition_evidence_id"],
    )
    db_session.expire_all()
    condition = db_session.get(ARBCondition, condition_id)
    cycle = db_session.get(ARBReviewCycle, cycle.id)
    review = db_session.get(ARBReviewItem, review.id)
    assert verified.object_ids == replay.object_ids
    assert condition.status == "fulfilled"
    assert cycle.status == review.status == "approved_with_conditions"
    assert cycle.terminal_outcome == review.decision == "approved_with_conditions"
    assert db_session.query(ARBDecisionEvent).filter_by(
        organization_id=org.id
    ).count() == 1

    waiver_now = datetime(2026, 8, 27, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(
        CommandService, "_database_now", staticmethod(lambda session: waiver_now),
    )
    TypedARBConditionLifecycleService.waive(
        actor=verifier_actor, command_key=f"waive-{suffix}",
        condition_id=waiver_condition_id,
        reason="Temporary operational acceptance",
        expires_at=waiver_now + timedelta(days=1),
        scope={"release": "R1"},
        compensating_control="Daily operational review",
    )
    db_session.expire_all()
    cycle = db_session.get(ARBReviewCycle, cycle.id)
    assert cycle.status == "approved"
    assert cycle.terminal_outcome == "approved_with_conditions"

    monkeypatch.setitem(app.config, "ARB_CONDITION_EXPIRY_PRINCIPAL_ID", verifier.id)
    monkeypatch.setitem(app.config, "ARB_CONDITION_EXPIRY_ORGANIZATION_ID", org.id)
    monkeypatch.setitem(
        app.config, "ARB_CONDITION_EXPIRY_CAPABILITY", "c3-expiry-capability"
    )
    monkeypatch.setattr(
        CommandService, "_database_now",
        staticmethod(lambda session: waiver_now + timedelta(days=2)),
    )
    expired = TypedARBConditionLifecycleService.expire_waivers(
        capability="c3-expiry-capability", command_key=f"expiry-{suffix}",
        condition_id=waiver_condition_id,
    )
    db_session.expire_all()
    cycle = db_session.get(ARBReviewCycle, cycle.id)
    review = db_session.get(ARBReviewItem, review.id)
    assert expired.response["status"] == "pending"
    assert cycle.status == review.status == "approved_with_conditions"
    assert cycle.terminal_outcome == review.decision == "approved_with_conditions"
