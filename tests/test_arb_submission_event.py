"""Database contract for the immutable typed ARB submission event."""

from __future__ import annotations

import json
import uuid

import pytest

from app.models.mixins import TenantMixin
from tests.test_typed_arb_submission_service import (
    SUBJECT_TYPES,
    _insert_typed_graph,
    _install_typed_schema,
    _seed_org_user_model,
    _seed_subject_material,
)


def _event_model():
    from app.models.arb_submission_event import ARBSubmissionEvent

    return ARBSubmissionEvent


def test_submission_event_schema_is_tenant_scoped_typed_and_fenced():
    event = _event_model()
    columns = event.__table__.columns

    assert issubclass(event, TenantMixin)
    assert {
        "organization_id", "review_cycle_id", "review_item_id", "event_type",
        "subject_type", "subject_id", "decision_brief_id", "solution_id",
        "architecture_model_id", "adr_id", "decision_brief_version_id",
        "solution_evidence_snapshot_id", "subject_evidence_snapshot_id",
        "actor_id", "command_receipt_id", "command_generation", "created_at",
    } <= set(columns.keys())
    assert columns["review_cycle_id"].unique
    assert columns["review_item_id"].unique
    checks = " ".join(
        str(item.sqltext) for item in event.__table__.constraints
        if item.__class__.__name__ == "CheckConstraint"
    )
    assert all(subject_type in checks for subject_type in SUBJECT_TYPES)
    assert "command_generation > 0" in checks


def _insert_receipt(
    cursor,
    organization_id,
    user_id,
    *,
    subject,
    generation=1,
    status="in_progress",
    natural_key=None,
):
    token = uuid.uuid4().hex
    request_digest = "a" * 64
    natural_key = natural_key or (
        f"arb-submission:{organization_id}:{subject['subject_type']}:"
        f"{subject['subject_id']}"
    )
    cursor.execute(
        """
        INSERT INTO command_idempotency_records (
            organization_id, actor_id, operation, idempotency_key,
            request_digest, natural_key, status, lease_generation,
            claim_token, claimant_request_id, attempt_count, lease_expires_at
        ) VALUES (%s, %s, 'arb.submit', %s, %s, %s, %s, %s,
                  %s, %s, 1, clock_timestamp() + interval '10 minutes') RETURNING id
        """,
        (organization_id, user_id, token, request_digest, natural_key, status,
         generation, token, token),
    )
    return cursor.fetchone()[0], request_digest, natural_key


def _finalize_receipt(
    cursor,
    *,
    organization_id,
    actor_id,
    receipt_id,
    request_digest,
    natural_key,
    generation,
    cycle_id,
    review_id,
    evidence_id,
    object_ids=None,
):
    object_ids = object_ids or {
        "review_cycle_id": cycle_id,
        "review_item_id": review_id,
        "evidence_id": evidence_id,
    }
    cursor.execute(
        """
        INSERT INTO operation_results (
            organization_id, actor_id, operation, natural_key, request_digest,
            receipt_id, receipt_generation, object_ids, response_json
        ) VALUES (%s, %s, 'arb.submit', %s, %s, %s, %s, %s::json, '{}'::json)
        RETURNING id
        """,
        (
            organization_id, actor_id, natural_key, request_digest, receipt_id,
            generation, json.dumps(object_ids),
        ),
    )
    result_id = cursor.fetchone()[0]
    cursor.execute(
        """
        UPDATE command_idempotency_records
        SET status = 'succeeded', operation_result_id = %s,
            lease_expires_at = NULL, completed_at = clock_timestamp()
        WHERE id = %s
        """,
        (result_id, receipt_id),
    )


def _insert_event(cursor, *, organization_id, actor_id, receipt_id, generation,
                  subject, cycle_id, review_id, evidence_id):
    subject_type = subject["subject_type"]
    subject_column = {
        "decision_brief": "decision_brief_id",
        "solution": "solution_id",
        "architecture_model": "architecture_model_id",
        "adr": "adr_id",
    }[subject_type]
    evidence_column = {
        "decision_brief": "decision_brief_version_id",
        "solution": "solution_evidence_snapshot_id",
        "architecture_model": "subject_evidence_snapshot_id",
        "adr": "subject_evidence_snapshot_id",
    }[subject_type]
    cursor.execute(
        f"""
        INSERT INTO arb_submission_events (
            organization_id, review_cycle_id, review_item_id, event_type,
            subject_type, subject_id, {subject_column}, {evidence_column},
            actor_id, command_receipt_id, command_generation
        ) VALUES (%s, %s, %s, 'submitted', %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (organization_id, cycle_id, review_id, subject_type, subject["subject_id"],
         subject["subject_id"], evidence_id, actor_id, receipt_id, generation),
    )
    return cursor.fetchone()[0]


@pytest.mark.parametrize("subject_type", sorted(SUBJECT_TYPES))
def test_direct_sql_accepts_every_exact_typed_submission_shape(app, _schema, subject_type):
    connection = _install_typed_schema(app)
    try:
        cursor = connection.cursor()
        organization_id, user_id, _model_id = _seed_org_user_model(cursor, subject_type)
        subject = _seed_subject_material(cursor, subject_type, organization_id, user_id, subject_type)
        cycle_id, review_id, evidence_id = _insert_typed_graph(
            cursor, organization_id=organization_id, user_id=user_id, subject=subject
        )
        receipt_id, digest, natural_key = _insert_receipt(
            cursor, organization_id, user_id, subject=subject
        )
        _insert_event(
            cursor, organization_id=organization_id, actor_id=user_id,
            receipt_id=receipt_id, generation=1, subject=subject,
            cycle_id=cycle_id, review_id=review_id, evidence_id=evidence_id,
        )
        _finalize_receipt(
            cursor, organization_id=organization_id, actor_id=user_id,
            receipt_id=receipt_id, request_digest=digest, natural_key=natural_key,
            generation=1, cycle_id=cycle_id, review_id=review_id,
            evidence_id=evidence_id,
        )
        connection.commit()
    finally:
        connection.rollback()
        connection.close()


def test_submission_event_rejects_foreign_actor_and_stale_generation(app, _schema):
    connection = _install_typed_schema(app)
    try:
        cursor = connection.cursor()
        organization_id, user_id, _ = _seed_org_user_model(cursor, "event-fence")
        foreign_org_id, foreign_user_id, _ = _seed_org_user_model(cursor, "foreign")
        subject = _seed_subject_material(
            cursor, "architecture_model", organization_id, user_id, "event-fence"
        )
        cycle_id, review_id, evidence_id = _insert_typed_graph(
            cursor, organization_id=organization_id, user_id=user_id, subject=subject
        )
        receipt_id, _digest, _key = _insert_receipt(
            cursor, organization_id, user_id, subject=subject, generation=2
        )
        with pytest.raises(Exception, match="actor|tenant"):
            _insert_event(
                cursor, organization_id=organization_id, actor_id=foreign_user_id,
                receipt_id=receipt_id, generation=2, subject=subject,
                cycle_id=cycle_id, review_id=review_id, evidence_id=evidence_id,
            )
            connection.commit()
        connection.rollback()

        # The failed transaction rolled back all setup; prove generation fencing
        # independently with a fresh graph.
        organization_id, user_id, _ = _seed_org_user_model(cursor, "stale")
        subject = _seed_subject_material(
            cursor, "architecture_model", organization_id, user_id, "stale"
        )
        cycle_id, review_id, evidence_id = _insert_typed_graph(
            cursor, organization_id=organization_id, user_id=user_id, subject=subject
        )
        receipt_id, _digest, _key = _insert_receipt(
            cursor, organization_id, user_id, subject=subject, generation=2
        )
        with pytest.raises(Exception, match="generation|receipt"):
            _insert_event(
                cursor, organization_id=organization_id, actor_id=user_id,
                receipt_id=receipt_id, generation=1, subject=subject,
                cycle_id=cycle_id, review_id=review_id, evidence_id=evidence_id,
            )
            connection.commit()
    finally:
        connection.rollback()
        connection.close()


def test_submission_event_rejects_cycle_review_membership_mismatch(app, _schema):
    connection = _install_typed_schema(app)
    try:
        cursor = connection.cursor()
        organization_id, user_id, _ = _seed_org_user_model(cursor, "membership")
        first = _seed_subject_material(
            cursor, "architecture_model", organization_id, user_id, "first"
        )
        second = _seed_subject_material(
            cursor, "architecture_model", organization_id, user_id, "second"
        )
        first_cycle, _first_review, first_evidence = _insert_typed_graph(
            cursor, organization_id=organization_id, user_id=user_id, subject=first
        )
        _second_cycle, second_review, _second_evidence = _insert_typed_graph(
            cursor, organization_id=organization_id, user_id=user_id, subject=second
        )
        receipt_id, _digest, _key = _insert_receipt(
            cursor, organization_id, user_id, subject=first
        )
        with pytest.raises(Exception, match="membership"):
            _insert_event(
                cursor, organization_id=organization_id, actor_id=user_id,
                receipt_id=receipt_id, generation=1, subject=first,
                cycle_id=first_cycle, review_id=second_review,
                evidence_id=first_evidence,
            )
            connection.commit()
    finally:
        connection.rollback()
        connection.close()


@pytest.mark.parametrize(
    "provenance_case, expected",
    [
        ("wrong_subject_receipt", "natural key|receipt"),
        ("in_progress_without_result", "succeeded|result"),
        ("different_submitter", "submitter|actor"),
        ("mismatched_result_ids", "result|object"),
    ],
)
def test_submission_event_rejects_incomplete_or_forged_command_provenance(
    app, _schema, provenance_case, expected
):
    connection = _install_typed_schema(app)
    try:
        cursor = connection.cursor()
        organization_id, submitter_id, _ = _seed_org_user_model(cursor, provenance_case)
        subject = _seed_subject_material(
            cursor, "architecture_model", organization_id, submitter_id, provenance_case
        )
        cycle_id, review_id, evidence_id = _insert_typed_graph(
            cursor, organization_id=organization_id, user_id=submitter_id, subject=subject
        )
        actor_id = submitter_id
        if provenance_case == "different_submitter":
            token = uuid.uuid4().hex
            cursor.execute(
                "INSERT INTO users (organization_id, email, enterprise_role) "
                "VALUES (%s, %s, 'enterprise_architect') RETURNING id",
                (organization_id, f"event-other-{token}@example.test"),
            )
            actor_id = cursor.fetchone()[0]
        wrong_key = None
        if provenance_case == "wrong_subject_receipt":
            wrong_key = (
                f"arb-submission:{organization_id}:architecture_model:"
                f"{subject['subject_id'] + 999999}"
            )
        receipt_id, digest, natural_key = _insert_receipt(
            cursor,
            organization_id,
            actor_id,
            subject=subject,
            natural_key=wrong_key,
        )
        _insert_event(
            cursor, organization_id=organization_id, actor_id=actor_id,
            receipt_id=receipt_id, generation=1, subject=subject,
            cycle_id=cycle_id, review_id=review_id, evidence_id=evidence_id,
        )
        if provenance_case != "in_progress_without_result":
            result_ids = None
            if provenance_case == "mismatched_result_ids":
                result_ids = {
                    "review_cycle_id": cycle_id,
                    "review_item_id": review_id + 999999,
                    "evidence_id": evidence_id,
                }
            _finalize_receipt(
                cursor, organization_id=organization_id, actor_id=actor_id,
                receipt_id=receipt_id, request_digest=digest,
                natural_key=natural_key, generation=1, cycle_id=cycle_id,
                review_id=review_id, evidence_id=evidence_id,
                object_ids=result_ids,
            )
        with pytest.raises(Exception, match=expected):
            connection.commit()
    finally:
        connection.rollback()
        connection.close()


@pytest.mark.parametrize("receipt_status", ["retryable_failure", "failed_non_retryable"])
def test_submission_event_rejects_failed_receipt_states(
    app, _schema, receipt_status
):
    connection = _install_typed_schema(app)
    try:
        cursor = connection.cursor()
        organization_id, user_id, _ = _seed_org_user_model(cursor, receipt_status)
        subject = _seed_subject_material(
            cursor, "architecture_model", organization_id, user_id, receipt_status
        )
        cycle_id, review_id, evidence_id = _insert_typed_graph(
            cursor, organization_id=organization_id, user_id=user_id, subject=subject
        )
        receipt_id, _digest, _key = _insert_receipt(
            cursor, organization_id, user_id, subject=subject, status=receipt_status
        )
        _insert_event(
            cursor, organization_id=organization_id, actor_id=user_id,
            receipt_id=receipt_id, generation=1, subject=subject,
            cycle_id=cycle_id, review_id=review_id, evidence_id=evidence_id,
        )
        with pytest.raises(Exception, match="succeeded|result"):
            connection.commit()
    finally:
        connection.rollback()
        connection.close()


def test_submission_event_is_database_append_only(app, _schema):
    connection = _install_typed_schema(app)
    try:
        cursor = connection.cursor()
        organization_id, user_id, _ = _seed_org_user_model(cursor, "immutable-event")
        subject = _seed_subject_material(
            cursor, "architecture_model", organization_id, user_id, "immutable-event"
        )
        cycle_id, review_id, evidence_id = _insert_typed_graph(
            cursor, organization_id=organization_id, user_id=user_id, subject=subject
        )
        receipt_id, digest, natural_key = _insert_receipt(
            cursor, organization_id, user_id, subject=subject
        )
        event_id = _insert_event(
            cursor, organization_id=organization_id, actor_id=user_id,
            receipt_id=receipt_id, generation=1, subject=subject,
            cycle_id=cycle_id, review_id=review_id, evidence_id=evidence_id,
        )
        _finalize_receipt(
            cursor, organization_id=organization_id, actor_id=user_id,
            receipt_id=receipt_id, request_digest=digest, natural_key=natural_key,
            generation=1, cycle_id=cycle_id, review_id=review_id,
            evidence_id=evidence_id,
        )
        connection.commit()
        with pytest.raises(Exception, match="append-only"):
            cursor.execute(
                "UPDATE arb_submission_events SET event_type = 'changed' WHERE id = %s",
                (event_id,),
            )
        connection.rollback()
        with pytest.raises(Exception, match="append-only"):
            cursor.execute("DELETE FROM arb_submission_events WHERE id = %s", (event_id,))
    finally:
        connection.rollback()
        connection.close()


def test_reconcile_installs_submission_event_table_and_guards(app, _schema):
    connection = _install_typed_schema(app)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT to_regclass('arb_submission_events')")
        assert cursor.fetchone()[0] == "arb_submission_events"
        cursor.execute(
            "SELECT tgname FROM pg_trigger WHERE tgrelid = "
            "'arb_submission_events'::regclass AND NOT tgisinternal"
        )
        assert {row[0] for row in cursor.fetchall()} >= {
            "trg_arb_submission_event_membership",
            "trg_arb_submission_event_immutable",
        }
    finally:
        connection.rollback()
        connection.close()
